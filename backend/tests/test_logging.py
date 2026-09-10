"""
backend/tests/test_logging.py — Unit tests for structured logging, credential redaction, and request ID tracking.
"""

import json
import logging
from backend.logging_config import (
    SecretRedactingFilter,
    RequestIDFilter,
    JSONFormatter,
    request_id_ctx_var,
    redact_sensitive_data,
)



class TestSecretRedaction:
    """Ensure sensitive credentials and tokens are redacted from all logs."""

    def setup_method(self):
        self.filter = SecretRedactingFilter()

    def test_redacts_groq_keys(self):
        raw = "Connecting with Groq API key: gsk_1234567890abcdef1234567890abcdef"
        redacted = self.filter.redact(raw) if hasattr(self.filter, "redact") else redact_sensitive_data(raw)
        assert "gsk_1234567890abcdef1234567890abcdef" not in redacted
        assert "••••••••" in redacted

    def test_redacts_google_keys(self):
        raw = "Auth using Google Key AIzaSyD1234567890abcdefghijklmnopqrstu"
        redacted = self.filter.redact(raw) if hasattr(self.filter, "redact") else redact_sensitive_data(raw)
        assert "AIzaSyD1234567890abcdefghijklmnopqrstu" not in redacted
        assert "••••••••" in redacted

    def test_redacts_youtube_aq_tokens(self):
        raw = "Using refresh token AQ.abc1234567890_XYZ"
        redacted = self.filter.redact(raw) if hasattr(self.filter, "redact") else redact_sensitive_data(raw)
        assert "AQ.abc1234567890_XYZ" not in redacted
        assert "••••••••" in redacted

    def test_redacts_jwt_tokens(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_leak_this_signature"
        raw = f"Bearer token received: {jwt}"
        redacted = self.filter.redact(raw) if hasattr(self.filter, "redact") else redact_sensitive_data(raw)
        assert jwt not in redacted
        assert "••••••••" in redacted

    def test_redacts_url_query_secrets(self):
        raw = "GET /api/test?api_key=supersecret123&sessionid=mysession999&format=json"
        redacted = self.filter.redact(raw) if hasattr(self.filter, "redact") else redact_sensitive_data(raw)
        assert "supersecret123" not in redacted
        assert "mysession999" not in redacted
        assert "api_key=••••••••" in redacted
        assert "sessionid=••••••••" in redacted
        assert "format=json" in redacted


    def test_filter_record_integration(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Sending request with key %s",
            args=("gsk_1234567890abcdef1234567890abcdef",),
            exc_info=None
        )
        self.filter.filter(record)
        assert "gsk_" not in str(record.args[0])
        assert "••••••••" in str(record.args[0])



class TestRequestIDTracking:
    """Ensure request_id is correctly propagated into log records."""

    def test_request_id_injected(self):
        token = request_id_ctx_var.set("req-test-999")
        try:
            filter_ = RequestIDFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="Processing video",
                args=(),
                exc_info=None
            )
            filter_.filter(record)
            assert getattr(record, "request_id", None) == "req-test-999"
        finally:
            request_id_ctx_var.reset(token)

    def test_request_id_default_when_not_set(self):
        # When context is empty
        filter_ = RequestIDFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Background task",
            args=(),
            exc_info=None
        )
        filter_.filter(record)
        assert getattr(record, "request_id", None) == "-"


class TestJSONFormatter:
    """Verify JSONFormatter outputs valid JSON with required schema fields."""

    def test_json_output_structure(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="reelsmob.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="Operation successful",
            args=(),
            exc_info=None
        )
        record.request_id = "req-abc-123"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "reelsmob.test"
        assert parsed["message"] == "Operation successful"
        assert parsed["request_id"] == "req-abc-123"
        assert "timestamp" in parsed
