"""
test_video_streaming_and_encoding.py
Unit & integration tests for:
1. Video encoding with standard H.264, yuv420p, and +faststart flag (fit_to_canvas).
2. Video stream proxy endpoint (/api/dashboard/videos/{video_id}/stream) supporting
   HTTP Range requests, 206 Partial Content, HEAD requests, and signed URL fallbacks.
"""

import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.fit_to_canvas import (
    fit_to_canvas,
    get_video_codec_and_format,
    resolve_ffmpeg_binary
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Section A: Encoding & Faststart Verification
# ============================================================================

class TestVideoEncodingAndFaststart:
    """Verifies that fit_to_canvas produces web-compatible MP4s with faststart."""

    def test_get_video_codec_and_format_fallback(self):
        """Non-existent or corrupted file safely returns (None, None)."""
        codec, pix_fmt = get_video_codec_and_format("non_existent_file.mp4")
        assert codec is None
        assert pix_fmt is None

    def test_fit_to_canvas_preserves_faststart_on_near_match(self, tmp_path):
        """A 9:16 H.264 video must have moov placed before mdat in the output."""
        ffmpeg = resolve_ffmpeg_binary()
        if not ffmpeg:
            pytest.skip("ffmpeg binary not available in test environment")

        input_path = str(tmp_path / "in_9_16.mp4")
        output_path = str(tmp_path / "out_9_16.mp4")

        # Generate a minimal 1-second 1080x1920 test video
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=1:size=1080x1920:rate=24",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            input_path
        ]
        proc = subprocess.run(cmd, capture_output=True)
        assert proc.returncode == 0, f"Failed to generate fixture: {proc.stderr}"

        # Run fit_to_canvas
        out = fit_to_canvas(input_path, output_path, canvas_w=1080, canvas_h=1920)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

        # Inspect MP4 box structure
        with open(out, "rb") as f:
            header = f.read(16384)

        assert b"ftyp" in header
        assert b"moov" in header
        # moov should occur before mdat in a +faststart file
        moov_pos = header.find(b"moov")
        mdat_pos = header.find(b"mdat")
        assert moov_pos != -1
        assert mdat_pos != -1
        assert moov_pos < mdat_pos, "moov atom must appear before mdat for faststart streaming"

    def test_fit_to_canvas_mismatch_produces_faststart(self, tmp_path):
        """A 16:9 landscape video fitted to 9:16 canvas must have moov before mdat."""
        ffmpeg = resolve_ffmpeg_binary()
        if not ffmpeg:
            pytest.skip("ffmpeg binary not available in test environment")

        input_path = str(tmp_path / "in_16_9.mp4")
        output_path = str(tmp_path / "out_16_9.mp4")

        # Generate a minimal 1-second 640x360 test video
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=1:size=640x360:rate=24",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            input_path
        ]
        proc = subprocess.run(cmd, capture_output=True)
        assert proc.returncode == 0

        out = fit_to_canvas(input_path, output_path, canvas_w=1080, canvas_h=1920)
        assert os.path.exists(out)

        with open(out, "rb") as f:
            header = f.read(16384)

        moov_pos = header.find(b"moov")
        mdat_pos = header.find(b"mdat")
        assert moov_pos != -1
        assert mdat_pos != -1
        assert moov_pos < mdat_pos, "moov atom must appear before mdat on blurred canvas output"


# ============================================================================
# Section B: Video Stream Proxy Endpoint Tests
# ============================================================================

class TestVideoStreamProxyEndpoint:
    """Verifies that /api/dashboard/videos/{video_id}/stream handles Range requests & fallbacks."""

    def test_stream_video_invalid_id_returns_400(self, client):
        res = client.get("/api/dashboard/videos/invalid..id//stream")
        # sanitize_filename_or_id returns stripped or empty or 400
        assert res.status_code in [400, 404]

    def test_stream_video_not_found_in_db_returns_404(self, client):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_sb.table.return_value = mock_table

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
            res = client.get("/api/dashboard/videos/nonexistent-id/stream")
            assert res.status_code == 404
            assert "Video not found" in res.json().get("detail", "")

    def test_stream_video_missing_storage_path_returns_404(self, client):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "vid-123", "storage_path": None}
        ]
        mock_sb.table.return_value = mock_table

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
            res = client.get("/api/dashboard/videos/vid-123/stream")
            assert res.status_code == 404
            assert "storage path" in res.json().get("detail", "").lower()

    def test_stream_video_with_range_request_returns_206_partial_content(self, client):
        """Simulates browser video playback sending Range: bytes=0-1023."""
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "vid-456", "storage_path": "videos/sample.mp4"}
        ]
        mock_sb.table.return_value = mock_table
        mock_sb.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://storage.supabase.co/sample.mp4?token=mocked"
        }

        # Mock httpx streaming response
        dummy_chunk = b"X" * 1024
        mock_httpx_resp = MagicMock()
        mock_httpx_resp.status_code = 206
        mock_httpx_resp.headers = {
            "content-type": "video/mp4",
            "content-range": "bytes 0-1023/5000000",
            "content-length": "1024",
            "accept-ranges": "bytes",
        }

        async def mock_aiter(chunk_size=65536):
            yield dummy_chunk

        mock_httpx_resp.aiter_bytes = mock_aiter
        mock_httpx_resp.aclose = AsyncMock()

        mock_client_inst = MagicMock()
        mock_client_inst.build_request.return_value = MagicMock()
        mock_client_inst.send = AsyncMock(return_value=mock_httpx_resp)
        mock_client_inst.aclose = AsyncMock()

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb), \
             patch("httpx.AsyncClient", return_value=mock_client_inst):

            res = client.get(
                "/api/dashboard/videos/vid-456/stream",
                headers={"Range": "bytes=0-1023"}
            )

            assert res.status_code == 206
            assert res.headers.get("Accept-Ranges") == "bytes"
            assert res.headers.get("Content-Range") == "bytes 0-1023/5000000"
            assert res.headers.get("Content-Length") == "1024"
            assert res.content == dummy_chunk

    def test_stream_video_head_request_returns_accept_ranges(self, client):
        """HEAD request returns 200 with Accept-Ranges and Content-Length."""
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "vid-789", "storage_path": "videos/sample.mp4"}
        ]
        mock_sb.table.return_value = mock_table
        mock_sb.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://storage.supabase.co/sample.mp4?token=mocked"
        }

        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 200
        mock_head_resp.headers = {
            "content-type": "video/mp4",
            "content-length": "12345678",
            "accept-ranges": "bytes",
        }

        mock_client_inst = MagicMock()
        mock_client_inst.head = AsyncMock(return_value=mock_head_resp)
        mock_client_inst.aclose = AsyncMock()

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb), \
             patch("httpx.AsyncClient", return_value=mock_client_inst):

            res = client.head("/api/dashboard/videos/vid-789/stream")
            assert res.status_code == 200
            assert res.headers.get("Accept-Ranges") == "bytes"
            assert res.headers.get("Content-Length") == "12345678"
            assert res.headers.get("Content-Type") == "video/mp4"

    def test_stream_video_explicit_redirect_param(self, client):
        """When ?redirect=true is passed without Range, returns 307 redirect."""
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "vid-red", "storage_path": "videos/sample.mp4"}
        ]
        mock_sb.table.return_value = mock_table
        mock_sb.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://storage.supabase.co/sample.mp4?token=mocked_redirect"
        }

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
            res = client.get("/api/dashboard/videos/vid-red/stream?redirect=true", follow_redirects=False)
            assert res.status_code == 307
            assert res.headers.get("Location") == "https://storage.supabase.co/sample.mp4?token=mocked_redirect"
