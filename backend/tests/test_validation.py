"""
backend/tests/test_validation.py — Unit tests for validation, sanitization, and Pydantic schemas.
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.schemas import (
    validate_video_url,
    sanitize_filename_or_id,
    URLRequest,
    DownloadRequest,
    AnalyzeRequest,
    ConvertRequest,
    PaginationParams,
)


class TestURLValidation:
    """Test validate_video_url with various URL shapes."""

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/reel/DCXYZ123456/",
        "https://instagram.com/p/B_abcdef123/?utm_source=ig_web",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "http://youtube.com/shorts/abc12345678",
    ])
    def test_valid_urls_accepted(self, url: str):
        cleaned = validate_video_url(url)
        assert cleaned.startswith("http")
        assert len(cleaned) >= 10

    @pytest.mark.parametrize("url", [
        "",
        "   ",
        "https://tiktok.com/@user/video/1234567890",
        "https://twitter.com/i/status/123456789",
        "https://facebook.com/watch?v=123456789",
        "not_a_valid_url_at_all",
        "ftp://malicious.com/payload.exe",
    ])
    def test_invalid_urls_raise_400(self, url: str):
        with pytest.raises(HTTPException) as exc_info:
            validate_video_url(url)
        assert exc_info.value.status_code == 400
        assert "Invalid URL" in exc_info.value.detail or "cannot be empty" in exc_info.value.detail or "too short" in exc_info.value.detail


class TestPathAndIDSanitization:
    """Test sanitize_filename_or_id against path traversal attacks."""

    @pytest.mark.parametrize("malicious,expected", [
        ("../../../etc/passwd", "etcpasswd"),
        ("..\\..\\windows\\system32\\cmd.exe", "windowssystem32cmd.exe"),
        ("safe_video_id_123", "safe_video_id_123"),
        ("video\0nullbyte", "videonullbyte"),
        ("/var/downloads/123.mp4", "vardownloads123.mp4"),
        ("bestvideo+bestaudio/best", "bestvideo+bestaudiobest"),
    ])
    def test_path_traversal_sanitized(self, malicious: str, expected: str):
        sanitized = sanitize_filename_or_id(malicious)
        assert "/" not in sanitized
        assert "\\" not in sanitized
        assert "\0" not in sanitized
        assert ".." not in sanitized
        assert sanitized == expected


class TestPydanticSchemas:
    """Test Pydantic model bounds and validation rules."""

    def test_url_request_valid(self):
        req = URLRequest(url="https://youtube.com/shorts/dQw4w9WgXcQ")
        assert "youtube.com" in req.url

    def test_url_request_length_overflow(self):
        with pytest.raises(ValidationError):
            URLRequest(url="https://youtube.com/shorts/" + "a" * 2100)

    def test_download_request_format_id_sanitization(self):
        req = DownloadRequest(
            url="https://youtube.com/shorts/dQw4w9WgXcQ",
            format_id="bestvideo+bestaudio"
        )
        assert req.format_id == "bestvideo+bestaudio"

    def test_download_request_invalid_format_id(self):
        with pytest.raises(ValidationError):
            DownloadRequest(
                url="https://youtube.com/shorts/dQw4w9WgXcQ",
                format_id="/..//"  # stripped to empty
            )

    def test_analyze_request_traversal_blocked(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(
                title="Test Video",
                description="Test Description",
                video_path="../../malicious/file.mp4"
            )

    def test_convert_request_allowed_ratios(self):
        for ratio in ["9:16", "1:1", "4:5", "16:9"]:
            req = ConvertRequest(ratio=ratio)
            assert req.ratio == ratio

    def test_convert_request_invalid_ratio(self):
        with pytest.raises(ValidationError):
            ConvertRequest(ratio="3:2")

    def test_pagination_params_bounds(self):
        params = PaginationParams(page=1, limit=50)
        assert params.page == 1
        assert params.limit == 50

        # Out of bounds limit
        with pytest.raises(ValidationError):
            PaginationParams(page=1, limit=500)

        # Invalid zero page
        with pytest.raises(ValidationError):
            PaginationParams(page=0, limit=20)

    def test_production_cors_fail_fast(self, monkeypatch):
        import importlib
        import backend.config
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with pytest.raises(RuntimeError, match="CORS_ORIGINS must be set in production"):
            importlib.reload(backend.config)
        # Restore development
        monkeypatch.setenv("ENVIRONMENT", "development")
        importlib.reload(backend.config)

    def test_production_cors_configured(self, monkeypatch):
        import importlib
        import backend.config
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("CORS_ORIGINS", "https://app.reelsmob.com, https://reelsmob.com")
        cfg = importlib.reload(backend.config)
        assert cfg.CORS_ORIGINS == ["https://app.reelsmob.com", "https://reelsmob.com"]
        # Restore development
        monkeypatch.setenv("ENVIRONMENT", "development")
        importlib.reload(backend.config)
