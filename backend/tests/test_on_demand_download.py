"""
test_on_demand_download.py — Comprehensive tests for on-demand video downloading.
Verifies highlights, moderation, and duplicate detection when local file is missing,
simulating GitHub Actions offload and ephemeral filesystem restarts.
"""

import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.services.video_download import (
    ensure_video_downloaded,
    async_ensure_video_downloaded,
)
from backend.services.highlight_detector import detect_highlights
from backend.services.content_moderation import check_content_moderation
from backend.services.duplicate_detector import check_video_duplicate, compute_video_perceptual_hash
from backend.main import (
    app,
    HIGHLIGHT_JOBS,
    MODERATION_JOBS,
    execute_highlight_job,
    execute_moderation_job,
)


@pytest.fixture
def mock_local_video(tmp_path):
    """Creates a dummy valid video file for testing."""
    video_file = tmp_path / "mock_test_video.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 2048)
    return str(video_file)


class TestVideoDownloadHelper:
    """Verify ensure_video_downloaded behavior and fallbacks."""

    def test_empty_url_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot download video: URL is empty"):
            ensure_video_downloaded("")

        with pytest.raises(ValueError, match="Cannot download video: URL is empty"):
            ensure_video_downloaded("   ")

    def test_successful_download_returns_filepath(self, tmp_path):
        def _mock_ydl_init(opts):
            outtmpl = opts.get("outtmpl", "")
            if outtmpl:
                Path(outtmpl).write_bytes(b"dummy_video_content")
            mock = MagicMock()
            mock.download.return_value = 0
            mock.__enter__.return_value = mock
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=_mock_ydl_init):
            out_path = ensure_video_downloaded("https://youtube.com/shorts/test1", target_dir=str(tmp_path))

        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0
        if os.path.exists(out_path):
            os.remove(out_path)

    def test_failed_download_raises_runtime_error(self, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl.download.side_effect = Exception("yt-dlp network error")
        mock_ydl.__enter__.return_value = mock_ydl

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(RuntimeError, match="Download failed"):
                ensure_video_downloaded("https://youtube.com/shorts/badurl", target_dir=str(tmp_path))


class TestHighlightDetectionOnDemandDownload:
    """Verify highlight detector downloads on-demand when local file is missing."""

    def test_local_file_found_used_directly_no_download(self, mock_local_video):
        with patch("backend.services.video_download.ensure_video_downloaded") as mock_dl:
            with patch("backend.services.highlight_detector.get_video_duration", return_value=30.0):
                clips = detect_highlights(video_path=mock_local_video, url="https://youtube.com/shorts/xyz")

        assert len(clips) > 0
        mock_dl.assert_not_called()

    def test_local_file_missing_with_url_triggers_download(self, tmp_path):
        downloaded_file = tmp_path / "hl_download_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        with patch("backend.services.video_download.ensure_video_downloaded", return_value=str(downloaded_file)) as mock_dl:
            with patch("backend.services.highlight_detector.get_video_duration", return_value=25.0):
                clips = detect_highlights(
                    video_path="nonexistent_rendered_file.mp4",
                    url="https://youtube.com/shorts/sample1"
                )

        assert len(clips) > 0
        mock_dl.assert_called_once_with("https://youtube.com/shorts/sample1", prefix="hl_")
        # Confirms temporary downloaded file was cleaned up in finally block
        assert not os.path.exists(str(downloaded_file))

    def test_local_file_missing_without_url_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Video file not found"):
            detect_highlights(video_path="missing_file_completely.mp4", url=None)

    def test_execute_highlight_job_with_missing_local_file_succeeds_via_url(self, tmp_path):
        downloaded_file = tmp_path / "hl_job_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        job_id = "test_hl_job_1"
        HIGHLIGHT_JOBS[job_id] = {"job_id": job_id, "status": "PENDING"}

        with patch("backend.services.video_download.ensure_video_downloaded", return_value=str(downloaded_file)):
            with patch("backend.services.highlight_detector.get_video_duration", return_value=20.0):
                execute_highlight_job(
                    job_id=job_id,
                    video_path=None,
                    target_duration_min=15.0,
                    target_duration_max=60.0,
                    num_clips=2,
                    url="https://youtube.com/shorts/offloaded_job"
                )

        job = HIGHLIGHT_JOBS[job_id]
        assert job["status"] == "COMPLETED"
        assert len(job["highlights"]) > 0


class TestContentModerationOnDemandDownload:
    """Verify content moderation downloads on-demand when local file is missing."""

    def test_local_file_found_used_directly_no_download(self, mock_local_video):
        with patch("backend.services.video_download.ensure_video_downloaded") as mock_dl:
            with patch("backend.services.content_moderation.get_video_duration", return_value=20.0):
                result = check_content_moderation(video_path=mock_local_video, url="https://youtube.com/shorts/xyz")

        assert "watermark_detected" in result
        mock_dl.assert_not_called()

    def test_local_file_missing_with_url_triggers_download(self, tmp_path):
        downloaded_file = tmp_path / "mod_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        with patch("backend.services.video_download.ensure_video_downloaded", return_value=str(downloaded_file)) as mock_dl:
            with patch("backend.services.content_moderation.get_video_duration", return_value=15.0):
                result = check_content_moderation(
                    video_path="missing_mod_video.mp4",
                    url="https://youtube.com/shorts/moderation_url"
                )

        assert "watermark_detected" in result
        mock_dl.assert_called_once_with("https://youtube.com/shorts/moderation_url", prefix="mod_")
        assert not os.path.exists(str(downloaded_file))

    def test_local_file_missing_without_url_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Video file not found"):
            check_content_moderation(video_path="missing_everywhere.mp4", url=None)

    def test_execute_moderation_job_with_missing_local_file_succeeds_via_url(self, tmp_path):
        downloaded_file = tmp_path / "mod_job_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        job_id = "test_mod_job_1"
        MODERATION_JOBS[job_id] = {"job_id": job_id, "status": "PENDING"}

        with patch("backend.services.video_download.ensure_video_downloaded", return_value=str(downloaded_file)):
            with patch("backend.services.content_moderation.get_video_duration", return_value=15.0):
                execute_moderation_job(
                    job_id=job_id,
                    video_path=None,
                    url="https://youtube.com/shorts/mod_offloaded"
                )

        job = MODERATION_JOBS[job_id]
        assert job["status"] == "COMPLETED"
        assert "watermark_detected" in job["result"]


class TestDuplicateDetectionOnDemandDownload:
    """Verify duplicate detector downloads on-demand when local file is missing."""

    def test_local_file_found_used_directly_no_download(self, mock_local_video):
        with patch("backend.services.video_download.ensure_video_downloaded") as mock_dl:
            with patch("backend.services.duplicate_detector.compute_video_perceptual_hash", return_value="0123456789abcdef"):
                result = check_video_duplicate(video_path=mock_local_video, url="https://youtube.com/shorts/dup")

        assert "is_duplicate" in result
        mock_dl.assert_not_called()

    def test_local_file_missing_with_url_triggers_download(self, tmp_path):
        downloaded_file = tmp_path / "dup_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        with patch("backend.services.video_download.ensure_video_downloaded", return_value=str(downloaded_file)) as mock_dl:
            with patch("backend.services.duplicate_detector.get_video_duration", return_value=10.0):
                with patch("PIL.Image.open") as mock_img_open:
                    mock_img = MagicMock()
                    mock_img.convert.return_value = mock_img
                    mock_img.resize.return_value = mock_img
                    mock_img.getdata.return_value = [0] * 72
                    mock_img_open.return_value.__enter__.return_value = mock_img

                    # Also patch subprocess.run so ffmpeg extraction succeeds
                    with patch("subprocess.run", return_value=MagicMock()):
                        img_path = str(tmp_path / "frame.jpg")
                        with patch("tempfile.mktemp", return_value=img_path):
                            with open(img_path, "wb") as f:
                                f.write(b"img")
                            hash_val = compute_video_perceptual_hash(
                                video_path="missing_dup.mp4",
                                url="https://youtube.com/shorts/dup_url"
                            )

        assert len(hash_val) == 16
        mock_dl.assert_called_once_with("https://youtube.com/shorts/dup_url", prefix="dup_")
        assert not os.path.exists(str(downloaded_file))

    def test_local_file_missing_without_url_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Video file not found"):
            compute_video_perceptual_hash(video_path="missing_file.mp4", url=None)

    def test_duplicate_check_api_endpoint_with_url_succeeds_when_local_missing(self, tmp_path):
        client = TestClient(app)
        downloaded_file = tmp_path / "api_dup_temp.mp4"
        downloaded_file.write_bytes(b"\x00" * 1024)

        with patch("backend.services.duplicate_detector.compute_video_perceptual_hash", return_value="0123456789abcdef"):
            res = client.post("/api/video/check-duplicate", json={
                "video_path": "nonexistent_on_render.mp4",
                "url": "https://youtube.com/shorts/offloaded_dup",
                "threshold": 10
            })

        assert res.status_code == 200
        data = res.json()
        assert data["hash"] == "0123456789abcdef"
        assert "is_duplicate" in data


class TestPlatformSpecificDownloadOptions:
    """Verify Instagram and YouTube format configurations in ensure_video_downloaded."""

    def test_instagram_uses_best_format_without_youtube_extractor_args(self, tmp_path):
        captured_opts = {}

        def _mock_ydl_init(opts):
            nonlocal captured_opts
            captured_opts = opts
            outtmpl = opts.get("outtmpl", "")
            if outtmpl:
                Path(outtmpl).write_bytes(b"dummy_ig_content")
            mock = MagicMock()
            mock.download.return_value = 0
            mock.__enter__.return_value = mock
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=_mock_ydl_init):
            out = ensure_video_downloaded("https://www.instagram.com/reel/DdiG3IoKWGT/", target_dir=str(tmp_path))

        assert captured_opts.get("format") == "best"
        assert "extractor_args" not in captured_opts
        if os.path.exists(out):
            os.remove(out)

    def test_youtube_uses_compound_format_and_player_client_args(self, tmp_path):
        captured_opts = {}

        def _mock_ydl_init(opts):
            nonlocal captured_opts
            captured_opts = opts
            outtmpl = opts.get("outtmpl", "")
            if outtmpl:
                Path(outtmpl).write_bytes(b"dummy_yt_content")
            mock = MagicMock()
            mock.download.return_value = 0
            mock.__enter__.return_value = mock
            return mock

        with patch("yt_dlp.YoutubeDL", side_effect=_mock_ydl_init):
            out = ensure_video_downloaded("https://www.youtube.com/shorts/dQw4w9WgXcQ", target_dir=str(tmp_path))

        assert "bestvideo[ext=mp4]+bestaudio" in captured_opts.get("format", "")
        assert "extractor_args" in captured_opts
        assert "youtube" in captured_opts["extractor_args"]
        if os.path.exists(out):
            os.remove(out)


class TestAutomateEndpointsRouting:
    """Verify /automate and /api/automate routes are both active."""

    def test_automate_endpoint_available_at_both_prefixes(self):
        client = TestClient(app)

        # Sending invalid payload should yield 422 Unprocessable Entity, verifying route exists and is mounted
        res1 = client.post("/automate", json={})
        assert res1.status_code == 422

        res2 = client.post("/api/automate", json={})
        assert res2.status_code == 422

