"""
test_resource_limits.py — Tests for the global heavy-job concurrency limiter.

Verifies:
1. The asyncio.Semaphore serializes concurrent heavy jobs (max 1 at a time).
2. get_ffmpeg_threads() returns the configured value.
3. heavy_job_gate logs and yields correctly.
"""

import asyncio
import os
import time
import pytest


def test_get_ffmpeg_threads_default():
    """FFMPEG_THREADS defaults to '1' when env var is not set."""
    # Clear any existing env var override
    original = os.environ.pop("FFMPEG_THREADS", None)
    try:
        # Re-import to pick up default
        import importlib
        import backend.services.resource_limits as rl
        importlib.reload(rl)
        assert rl.get_ffmpeg_threads() == "1"
    finally:
        if original is not None:
            os.environ["FFMPEG_THREADS"] = original


def test_get_ffmpeg_threads_custom():
    """FFMPEG_THREADS reads from environment variable."""
    original = os.environ.get("FFMPEG_THREADS")
    try:
        os.environ["FFMPEG_THREADS"] = "4"
        import importlib
        import backend.services.resource_limits as rl
        importlib.reload(rl)
        assert rl.get_ffmpeg_threads() == "4"
    finally:
        if original is not None:
            os.environ["FFMPEG_THREADS"] = original
        else:
            os.environ.pop("FFMPEG_THREADS", None)


@pytest.mark.asyncio
async def test_heavy_job_gate_serializes():
    """
    Two overlapping heavy jobs must run sequentially (not concurrently)
    when MAX_CONCURRENT_HEAVY_JOBS=1.

    Strategy:
    - Launch two tasks that each sleep for 0.2s inside heavy_job_gate.
    - Record start/end times.
    - If they ran concurrently, total would be ~0.2s. Sequential = ~0.4s.
    """
    import importlib
    import backend.services.resource_limits as rl

    # Force MAX_CONCURRENT_HEAVY_JOBS=1 and reset semaphore
    original_max = os.environ.get("MAX_CONCURRENT_HEAVY_JOBS")
    try:
        os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = "1"
        importlib.reload(rl)
        # Reset the lazily-created semaphore so it picks up the new value
        rl._heavy_job_semaphore = None

        timestamps = []

        async def heavy_task(label: str):
            async with rl.heavy_job_gate(label):
                timestamps.append((label, "start", time.monotonic()))
                await asyncio.sleep(0.2)
                timestamps.append((label, "end", time.monotonic()))

        t0 = time.monotonic()
        await asyncio.gather(
            heavy_task("job_A"),
            heavy_task("job_B"),
        )
        total_elapsed = time.monotonic() - t0

        # Sequential execution → total should be >= 0.35s (allowing for scheduling jitter)
        assert total_elapsed >= 0.35, (
            f"Jobs ran concurrently! Total elapsed={total_elapsed:.3f}s, "
            f"expected >= 0.35s for sequential execution"
        )

        # Verify no overlap: job_B start must be after job_A end (or vice versa)
        starts = {label: t for label, event, t in timestamps if event == "start"}
        ends = {label: t for label, event, t in timestamps if event == "end"}

        # One must finish before the other starts
        a_before_b = ends["job_A"] <= starts["job_B"] + 0.01
        b_before_a = ends["job_B"] <= starts["job_A"] + 0.01
        assert a_before_b or b_before_a, (
            f"Jobs overlapped! A: {starts['job_A']:.3f}-{ends['job_A']:.3f}, "
            f"B: {starts['job_B']:.3f}-{ends['job_B']:.3f}"
        )
    finally:
        if original_max is not None:
            os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = original_max
        else:
            os.environ.pop("MAX_CONCURRENT_HEAVY_JOBS", None)
        # Reset semaphore for other tests
        rl._heavy_job_semaphore = None


@pytest.mark.asyncio
async def test_heavy_job_gate_allows_parallel_when_configured():
    """
    When MAX_CONCURRENT_HEAVY_JOBS=2, two jobs should run concurrently.
    """
    import importlib
    import backend.services.resource_limits as rl

    original_max = os.environ.get("MAX_CONCURRENT_HEAVY_JOBS")
    try:
        os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = "2"
        importlib.reload(rl)
        rl._heavy_job_semaphore = None

        async def heavy_task():
            async with rl.heavy_job_gate("parallel_test"):
                await asyncio.sleep(0.2)

        t0 = time.monotonic()
        await asyncio.gather(heavy_task(), heavy_task())
        total_elapsed = time.monotonic() - t0

        # Concurrent execution → total should be ~0.2s (not ~0.4s)
        assert total_elapsed < 0.35, (
            f"Jobs ran sequentially even with MAX_CONCURRENT_HEAVY_JOBS=2! "
            f"Total elapsed={total_elapsed:.3f}s"
        )
    finally:
        if original_max is not None:
            os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = original_max
        else:
            os.environ.pop("MAX_CONCURRENT_HEAVY_JOBS", None)
        rl._heavy_job_semaphore = None


def test_rss_helpers_dont_crash():
    """RSS helpers should return floats and never raise, even on Windows."""
    from backend.services.resource_limits import _get_rss_mb, _get_children_rss_mb, log_subprocess_peak_memory
    rss = _get_rss_mb()
    children = _get_children_rss_mb()
    assert isinstance(rss, float)
    assert isinstance(children, float)
    assert rss >= 0.0
    assert children >= 0.0
    # Must not raise
    log_subprocess_peak_memory("test")


@pytest.mark.asyncio
async def test_heavy_job_gate_notifies_waiting():
    """When a job waits for the semaphore, its on_waiting callback is triggered."""
    import importlib
    import backend.services.resource_limits as rl

    original_max = os.environ.get("MAX_CONCURRENT_HEAVY_JOBS")
    try:
        os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = "1"
        importlib.reload(rl)
        rl._heavy_job_semaphore = None

        waiting_called = []
        started_event = asyncio.Event()

        async def first_job():
            async with rl.heavy_job_gate("first_job"):
                started_event.set()
                assert rl.is_heavy_job_busy() is True
                await asyncio.sleep(0.2)

        async def second_job():
            await started_event.wait()
            # first_job is running and holding the lock; second_job tries to enter
            async with rl.heavy_job_gate("second_job", on_waiting=lambda: waiting_called.append(True)):
                pass

        await asyncio.gather(first_job(), second_job())
        assert len(waiting_called) == 1
    finally:
        if original_max is not None:
            os.environ["MAX_CONCURRENT_HEAVY_JOBS"] = original_max
        else:
            os.environ.pop("MAX_CONCURRENT_HEAVY_JOBS", None)
        rl._heavy_job_semaphore = None

