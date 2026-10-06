"""
test_instagram_cookies_and_download.py — Comprehensive tests for Instagram cookie injection and download robustness.
Verifies:
1. Cookie resolution from files and INSTAGRAM_COOKIES environment variable.
2. Injection of cookiefile into yt-dlp across download_video, ensure_video_downloaded, and metadata.
3. User-friendly error messaging when Instagram requires authentication.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import yt_dlp
from backend.services.video_download import (
    resolve_cookie_file,
    ensure_video_downloaded,
)
from backend.main import app


class TestCookieResolution:
    """Test resolution of cookies from paths, files, and environment variables."""

    def test_resolve_from_env_path(self, monkeypatch, tmp_path):
        cookie_file = tmp_path / "custom_cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\ninstagram.com\tTRUE\t/\tTRUE\t0\tsessionid\t123", encoding="utf-8")
        monkeypatch.setenv("YTDL_COOKIES_PATH", str(cookie_file))

        resolved = resolve_cookie_file()
        assert resolved == str(cookie_file.resolve())

    def test_resolve_from_raw_env_content(self, monkeypatch, tmp_path):
        monkeypatch.delenv("YTDL_COOKIES_PATH", raising=False)
        monkeypatch.delenv("COOKIES_FILE", raising=False)
        raw_content = "instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tabc_secret"
        monkeypatch.setenv("INSTAGRAM_COOKIES", raw_content)

        import backend.services.video_download as vd
        vd._RUNTIME_COOKIE_FILE = None

        resolved = resolve_cookie_file()
        assert resolved is not None
        assert os.path.exists(resolved)
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# Netscape HTTP Cookie File" in content
        assert "sessionid\tabc_secret" in content

    def test_resolve_with_escaped_newlines(self, monkeypatch):
        monkeypatch.delenv("YTDL_COOKIES_PATH", raising=False)
        monkeypatch.delenv("COOKIES_FILE", raising=False)
        raw_content = "# Netscape HTTP Cookie File\\n.instagram.com\\tTRUE\\t/\\tTRUE\\t0\\tsessionid\\txyz123"
        monkeypatch.setenv("INSTAGRAM_COOKIES", raw_content)

        import backend.services.video_download as vd
        vd._RUNTIME_COOKIE_FILE = None

        resolved = resolve_cookie_file()
        assert resolved is not None
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
        assert "\n.instagram.com" in content


class TestDownloadCookieInjection:
    """Test that cookiefile and headers are injected into yt-dlp."""

    def test_ensure_video_downloaded_passes_cookiefile(self, monkeypatch, tmp_path):
        dummy_cookies = tmp_path / "cookies.txt"
        dummy_cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        monkeypatch.setenv("YTDL_COOKIES_PATH", str(dummy_cookies))

        captured_opts = {}

        def _mock_ydl_init(opts):
            nonlocal captured_opts
            captured_opts = opts
            outtmpl = opts.get("outtmpl", "")
            if outtmpl:
                Path(outtmpl).write_bytes(b"dummy_video_bytes")
            mock = MagicMock()
            mock.download.return_value = 0
            mock.__enter__.return_value = mock
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=_mock_ydl_init):
            path = ensure_video_downloaded("https://www.instagram.com/reel/DeEoY3Qls9L/", target_dir=str(tmp_path))
            assert os.path.exists(path)
            assert captured_opts.get("cookiefile") == str(dummy_cookies.resolve())
            assert "User-Agent" in captured_opts.get("http_headers", {})

    def test_instagram_empty_media_response_error_message(self, monkeypatch, tmp_path):
        def _mock_ydl_init(opts):
            mock = MagicMock()
            mock.download.side_effect = yt_dlp.utils.DownloadError("ERROR: [Instagram] DeEoY3Qls9L: Instagram sent an empty media response.")
            mock.__enter__.return_value = mock
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=_mock_ydl_init):
            with pytest.raises(RuntimeError, match="Instagram requires authentication"):
                ensure_video_downloaded("https://www.instagram.com/reel/DeEoY3Qls9L/", target_dir=str(tmp_path))


class TestApiDownloadEndpointInstagramAuth:
    """Test /download endpoint error message formatting for Instagram."""

    def test_api_download_returns_helpful_instagram_error(self):
        client = TestClient(app)

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.side_effect = yt_dlp.utils.DownloadError(
            "ERROR: [Instagram] DeEoY3Qls9L: Instagram sent an empty media response. Check if this post is accessible in your browser without being logged-in."
        )

        with patch("backend.main.yt_dlp.YoutubeDL", return_value=mock_instance):
            res = client.post("/download", json={
                "url": "https://www.instagram.com/reel/DeEoY3Qls9L/",
                "format_id": "best"
            })
            assert res.status_code == 400
            data = res.json()
            assert "Instagram requires authentication" in data["detail"]
            assert "INSTAGRAM_COOKIES" in data["detail"]
