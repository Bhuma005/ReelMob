"""
backend/retry.py — Resilient retry execution with exponential backoff for ReelsMob.

Rules:
- 3 attempts maximum.
- Exponential backoff (e.g. 0.5s, 1.0s, 2.0s).
- Retries ONLY transient failures:
  - Network timeouts / connection reset / socket errors.
  - HTTP 429 (Rate limited) or HTTP 502/503/504 (Gateway / Service Unavailable).
- NEVER retries 4xx client errors (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found).
"""

import time
import asyncio
import logging
import urllib.error
from typing import Callable, TypeVar, Any

logger = logging.getLogger("reelsmob.retry")

T = TypeVar("T")


def is_transient_error(exc: Exception) -> bool:
    """Identifies whether an exception represents a temporary, recoverable outage."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    
    # urllib HTTP errors
    if isinstance(exc, urllib.error.HTTPError):
        # 429 Too Many Requests, or 502/503/504
        return exc.code in (429, 502, 503, 504)
        
    if isinstance(exc, urllib.error.URLError):
        # Network unreachable, name resolution failure
        return True

    exc_str = str(exc).lower()
    transient_indicators = [
        "timed out", "timeout", "connection reset", "connection refused",
        "remote end closed", "temporarily unavailable", "rate limit", "429", "503", "502"
    ]
    return any(indicator in exc_str for indicator in transient_indicators)


async def async_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    operation_name: str = "operation",
    **kwargs: Any
) -> Any:
    """Executes an async function with exponential backoff retries for transient errors."""
    delay = initial_delay
    last_exc: Exception = Exception("Unknown failure")

    for attempt in range(1, max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            else:
                return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if not is_transient_error(exc) or attempt == max_retries:
                logger.warning(
                    f"[{operation_name}] Permanent error or exhausted attempts ({attempt}/{max_retries}): {exc}"
                )
                raise
            
            logger.warning(
                f"[{operation_name}] Transient failure on attempt {attempt}/{max_retries}: {exc}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor

    raise last_exc


def sync_retry(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    operation_name: str = "operation",
    **kwargs: Any
) -> T:
    """Executes a synchronous function with exponential backoff retries for transient errors."""
    delay = initial_delay
    last_exc: Exception = Exception("Unknown failure")

    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if not is_transient_error(exc) or attempt == max_retries:
                logger.warning(
                    f"[{operation_name}] Permanent error or exhausted attempts ({attempt}/{max_retries}): {exc}"
                )
                raise
            
            logger.warning(
                f"[{operation_name}] Transient failure on attempt {attempt}/{max_retries}: {exc}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
            delay *= backoff_factor

    raise last_exc
