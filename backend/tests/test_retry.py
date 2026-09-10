"""
backend/tests/test_retry.py — Unit tests for transient error classification and exponential backoff retry logic.
"""

import socket
import urllib.error
import pytest
import asyncio
from backend.retry import is_transient_error, sync_retry, async_retry


class TestTransientErrorClassification:
    """Verify is_transient_error accurately distinguishes transient network failures from client errors."""

    def test_timeout_is_transient(self):
        assert is_transient_error(TimeoutError("Connection timed out")) is True
        assert is_transient_error(socket.timeout("Socket timed out")) is True

    def test_connection_errors_are_transient(self):
        assert is_transient_error(ConnectionResetError("Connection reset by peer")) is True
        assert is_transient_error(ConnectionRefusedError("Connection refused")) is True

    def test_http_transient_status_codes(self):
        # 429 Rate Limit
        err_429 = urllib.error.HTTPError(url="", code=429, msg="Too Many Requests", hdrs={}, fp=None)
        assert is_transient_error(err_429) is True

        # 502 Bad Gateway
        err_502 = urllib.error.HTTPError(url="", code=502, msg="Bad Gateway", hdrs={}, fp=None)
        assert is_transient_error(err_502) is True

        # 503 Service Unavailable
        err_503 = urllib.error.HTTPError(url="", code=503, msg="Service Unavailable", hdrs={}, fp=None)
        assert is_transient_error(err_503) is True

        # 504 Gateway Timeout
        err_504 = urllib.error.HTTPError(url="", code=504, msg="Gateway Timeout", hdrs={}, fp=None)
        assert is_transient_error(err_504) is True

    def test_http_client_errors_are_not_transient(self):
        # 400 Bad Request
        err_400 = urllib.error.HTTPError(url="", code=400, msg="Bad Request", hdrs={}, fp=None)
        assert is_transient_error(err_400) is False

        # 401 Unauthorized
        err_401 = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs={}, fp=None)
        assert is_transient_error(err_401) is False

        # 404 Not Found
        err_404 = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=None)
        assert is_transient_error(err_404) is False

    def test_programming_errors_are_not_transient(self):
        assert is_transient_error(ValueError("Invalid argument")) is False
        assert is_transient_error(KeyError("missing_key")) is False
        assert is_transient_error(TypeError("unsupported operand")) is False


class TestSyncRetry:
    """Test sync_retry execution semantics."""

    def test_success_on_first_try(self):
        calls = 0

        def fn():
            nonlocal calls
            calls += 1
            return "ok"

        res = sync_retry(fn, max_retries=3, retry_delay=0.01)
        assert res == "ok"
        assert calls == 1

    def test_success_after_transient_failure(self):
        calls = 0

        def fn():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("Temporary timeout")
            return "recovered"

        res = sync_retry(fn, max_retries=3, retry_delay=0.01)
        assert res == "recovered"
        assert calls == 2

    def test_exhaustion_raises_last_error(self):
        calls = 0

        def fn():
            nonlocal calls
            calls += 1
            raise TimeoutError(f"Persistent timeout {calls}")

        with pytest.raises(TimeoutError) as exc_info:
            sync_retry(fn, max_retries=3, retry_delay=0.01)
        assert "Persistent timeout 3" in str(exc_info.value)
        assert calls == 3

    def test_client_error_fails_immediately_without_retry(self):
        calls = 0

        def fn():
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=None)

        with pytest.raises(urllib.error.HTTPError):
            sync_retry(fn, max_retries=3, retry_delay=0.01)
        # Should NOT retry 404
        assert calls == 1


class TestAsyncRetry:
    """Test async_retry execution semantics."""

    @pytest.mark.asyncio
    async def test_async_success_after_failure(self):
        calls = 0

        async def coro():
            nonlocal calls
            calls += 1
            if calls < 2:
                raise ConnectionResetError("Reset")
            return "async_ok"

        res = await async_retry(coro, max_retries=3, retry_delay=0.01)
        assert res == "async_ok"
        assert calls == 2

    @pytest.mark.asyncio
    async def test_async_client_error_no_retry(self):
        calls = 0

        async def coro():
            nonlocal calls
            calls += 1
            raise urllib.error.HTTPError(url="", code=400, msg="Bad Request", hdrs={}, fp=None)

        with pytest.raises(urllib.error.HTTPError):
            await async_retry(coro, max_retries=3, retry_delay=0.01)
        assert calls == 1
