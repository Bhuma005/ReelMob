"""
backend/tests/test_api_mocked.py — Mocked integration tests for ReelsMob FastAPI endpoints.
Tests route behavior, error responses, headers, health checks, and backward compatibility.
"""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.main import app, RATE_LIMIT_STORE


@pytest.fixture
def client():
    # Clear rate limit store for clean test isolation
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


class TestRequestIDAndHeaders:
    """Verify X-Request-ID header propagation across endpoints."""

    def test_custom_request_id_propagated(self, client):
        custom_id = "custom-req-uuid-999"
        res = client.get("/api/health", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers.get("X-Request-ID") == custom_id

    def test_auto_generated_request_id(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        req_id = res.headers.get("X-Request-ID")
        assert req_id is not None
        assert len(req_id) >= 8


class TestHealthEndpoints:
    """Verify health endpoints return expected contract and dependency states."""

    def test_api_health_basic(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "timestamp" in data
        assert "services" in data
        services = data["services"]
        assert "backend" in services
        assert "database" in services
        assert "storage" in services
        assert "ollama" in services
        assert "youtube" in services
        assert "disk" in services
        assert "ffmpeg" in services

    def test_api_health_detailed(self, client):
        res = client.get("/api/health/detailed")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "uptime_seconds" in data
        assert "total_audit_latency_ms" in data
        assert "dependencies" in data
        deps = data["dependencies"]
        assert "database" in deps
        assert "storage" in deps
        assert "ai" in deps
        assert "disk" in deps
        assert "ffmpeg" in deps
        # Verify latency reporting
        assert "latency_ms" in deps["database"]
        assert "latency_ms" in deps["storage"]


class TestErrorResponsesShape:
    """Ensure HTTP exceptions return both 'detail' and structured 'error' dict for backwards compatibility."""

    def test_invalid_url_formats_error_shape(self, client):
        res = client.post("/formats", json={"url": "https://tiktok.com/@user/video/123"})
        assert res.status_code == 400
        data = res.json()
        # Both detail and structured error must exist
        assert "detail" in data
        assert "error" in data
        assert data["error"]["code"] == 400
        assert "request_id" in data["error"]

    def test_invalid_format_id_download_error_shape(self, client):
        res = client.post("/download", json={
            "url": "https://youtube.com/shorts/dQw4w9WgXcQ",
            "format_id": "/..//"
        })
        # Pydantic validation error or HTTP 400
        assert res.status_code in [400, 422]
        data = res.json()
        assert "error" in data
        assert "detail" in data


class TestMetadataContract:
    """Verify /metadata returns 200 with null values on invalid URL as expected by contract."""

    def test_metadata_invalid_url_returns_nulls(self, client):
        res = client.post("/metadata", json={"url": "invalid_url"})
        assert res.status_code == 200
        data = res.json()
        assert data["title"] is None
        assert data["description"] is None
        assert data["hashtags"] == []
        assert data["thumbnail_url"] is None

    def test_metadata_valid_mocked(self, client):
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "title": "Amazing Sunset Reel",
            "description": "Look at this view! #sunset #nature #viral",
            "thumbnail": "https://example.com/thumb.jpg",
            "view_count": 15000,
            "like_count": 1200,
            "comment_count": 45
        }

        with patch("backend.main.yt_dlp.YoutubeDL", return_value=mock_instance):
            res = client.post("/metadata", json={"url": "https://www.instagram.com/reel/DCXYZ123456/"})
            assert res.status_code == 200
            data = res.json()
            assert data["title"] == "Amazing Sunset Reel"
            assert "#sunset" in data["hashtags"]
            assert "#nature" in data["hashtags"]
            assert data["view_count"] == 15000


class TestMockedFormatsEndpoint:
    """Verify /formats correctly calculates aspect ratios and orders resolutions."""

    def test_formats_mocked(self, client):
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.extract_info.return_value = {
            "id": "vid123",
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "formats": [
                {
                    "format_id": "137",
                    "width": 1080,
                    "height": 1920,
                    "fps": 30,
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "ext": "mp4"
                },
                {
                    "format_id": "136",
                    "width": 720,
                    "height": 1280,
                    "fps": 30,
                    "vcodec": "avc1.4d401f",
                    "acodec": "mp4a.40.2",
                    "ext": "mp4"
                }
            ]
        }

        with patch("backend.main.yt_dlp.YoutubeDL", return_value=mock_instance):
            res = client.post("/formats", json={"url": "https://youtube.com/shorts/dQw4w9WgXcQ"})
            assert res.status_code == 200
            formats = res.json()
            assert isinstance(formats, list)
            assert len(formats) >= 2
            # First entry must be original
            assert formats[0]["is_original"] is True
            assert formats[0]["aspect_ratio"] == "9:16"



class TestRateLimiter:
    """Verify rate limiter blocks burst calls exceeding RATE_LIMIT_BURST."""

    def test_burst_rate_limit(self, client):
        RATE_LIMIT_STORE.clear()
        # Burst 10 requests rapidly
        responses = [client.get("/api/health") for _ in range(12)]
        status_codes = [r.status_code for r in responses]
        # At least one 429 should occur
        assert 429 in status_codes
        # Verify 429 body contract
        idx_429 = status_codes.index(429)
        res_429 = responses[idx_429].json()
        assert "Too many requests" in res_429["detail"]
