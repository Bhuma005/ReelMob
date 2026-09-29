"""
resource_limits.py — Global concurrency limiter for heavy video-processing jobs.

On Render Free tier (512 MB RAM, 0.1 vCPU), a single ffmpeg encode peaks at ~243 MB.
Combined with the Python process (~150 MB), two concurrent heavy jobs exceed the
container's 512 MB hard limit and trigger an OOM kill.

This module provides:
- A global asyncio.Semaphore that serializes heavy operations (default: 1 at a time).
- A configurable FFMPEG_THREADS env var (default: 1 for 0.1 vCPU).
- RSS memory logging before/after heavy operations.
"""

import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

# `resource` is Unix-only; gracefully degrade on Windows
try:
    import resource as _resource_mod
except ImportError:
    _resource_mod = None  # type: ignore[assignment]

logger = logging.getLogger("reelsmob.resource_limits")

# ---------------------------------------------------------------------------
# Configuration via environment variables
# ---------------------------------------------------------------------------
MAX_CONCURRENT_HEAVY_JOBS: int = int(os.getenv("MAX_CONCURRENT_HEAVY_JOBS", "1"))
FFMPEG_THREADS: str = os.getenv("FFMPEG_THREADS", "1")

# Global semaphore — created lazily on first access to ensure it binds to the
# running event loop (important for uvicorn's single-worker setup).
_heavy_job_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore so it attaches to the current event loop."""
    global _heavy_job_semaphore
    if _heavy_job_semaphore is None:
        _heavy_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HEAVY_JOBS)
        logger.info(
            f"Heavy-job semaphore initialised: max_concurrent={MAX_CONCURRENT_HEAVY_JOBS}"
        )
    return _heavy_job_semaphore


# ---------------------------------------------------------------------------
# RSS memory helpers (Linux / macOS only — returns 0 on Windows)
# ---------------------------------------------------------------------------
def _get_rss_mb() -> float:
    """Return current process RSS in megabytes (Linux: maxrss is in KB)."""
    if _resource_mod is None:
        return 0.0
    try:
        ru = _resource_mod.getrusage(_resource_mod.RUSAGE_SELF)
        # On Linux maxrss is in KB; on macOS it's in bytes.
        import platform
        if platform.system() == "Darwin":
            return ru.ru_maxrss / (1024 * 1024)
        return ru.ru_maxrss / 1024
    except Exception:
        return 0.0


def _get_children_rss_mb() -> float:
    """Return children aggregate peak RSS in megabytes."""
    if _resource_mod is None:
        return 0.0
    try:
        ru = _resource_mod.getrusage(_resource_mod.RUSAGE_CHILDREN)
        import platform
        if platform.system() == "Darwin":
            return ru.ru_maxrss / (1024 * 1024)
        return ru.ru_maxrss / 1024
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_current_rss_mb() -> float:
    """Return current process RSS in megabytes."""
    return _get_rss_mb()


def get_children_rss_mb() -> float:
    """Return peak children RSS in megabytes."""
    return _get_children_rss_mb()


def log_subprocess_peak_memory(label: str = "ffmpeg"):
    """
    Logs the peak RSS of child subprocesses (e.g. ffmpeg) using RUSAGE_CHILDREN.
    Safe on both Linux (Render) and Windows.
    """
    children_mb = _get_children_rss_mb()
    self_mb = _get_rss_mb()
    logger.info(
        f"[{label}] Subprocess peak memory — RSS(children): {children_mb:.1f} MB, RSS(self): {self_mb:.1f} MB"
    )


def is_heavy_job_busy() -> bool:
    """Return True if the semaphore is currently held by a running heavy job."""
    sem = _get_semaphore()
    return sem.locked()


@asynccontextmanager
async def heavy_job_gate(operation_name: str = "heavy_job", on_waiting=None):
    """
    Async context manager that:
    1. Acquires the global semaphore (blocks if another heavy job is running).
    2. Calls on_waiting() if the semaphore is currently locked so jobs can update their state.
    3. Logs RSS before and after the operation.
    4. Releases the semaphore when done.

    Usage::

        async with heavy_job_gate("fit_to_canvas"):
            result = await asyncio.to_thread(fit_to_canvas, ...)
    """
    sem = _get_semaphore()

    # Log and trigger callback if we're about to wait
    if sem.locked():
        logger.info(
            f"[{operation_name}] Queued — waiting for another heavy job to finish "
            f"(max_concurrent={MAX_CONCURRENT_HEAVY_JOBS})"
        )
        if on_waiting:
            try:
                on_waiting()
            except Exception as e:
                logger.debug(f"on_waiting callback failed: {e}")

    t0 = time.monotonic()
    rss_before = _get_rss_mb()

    async with sem:
        wait_time = time.monotonic() - t0
        if wait_time > 0.1:
            logger.info(f"[{operation_name}] Waited {wait_time:.1f}s for semaphore")

        logger.info(
            f"[{operation_name}] Starting heavy job — "
            f"RSS(self)={rss_before:.0f} MB, RSS(children)={_get_children_rss_mb():.0f} MB"
        )

        try:
            yield
        finally:
            rss_after = _get_rss_mb()
            children_after = _get_children_rss_mb()
            elapsed = time.monotonic() - t0
            logger.info(
                f"[{operation_name}] Finished in {elapsed:.1f}s — "
                f"RSS(self)={rss_after:.0f} MB, RSS(children)={children_after:.0f} MB"
            )


def get_ffmpeg_threads() -> str:
    """Return the configured FFMPEG_THREADS value (string, for direct use in cmd lists)."""
    return FFMPEG_THREADS

