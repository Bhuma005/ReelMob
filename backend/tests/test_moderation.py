"""
test_moderation.py — Unit and integration tests for Content Moderation / Watermark Detection.
Verifies Pydantic Literal validation, frame extraction / AI vision parsing, heuristic fallbacks,
and async job polling endpoints.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app, MODERATION_JOBS
from backend.schemas import ModerationCheckRequest, ModerationResult, ModerationJobResponse
from backend.services.content_moderation import check_content_moderation, _analyze_frames_with_gemini_moderation

client = TestClient(app)


def test_moderation_schemas_validation():
    # Valid schema
    valid_res = ModerationResult(
        watermark_detected=True,
        confidence=0.92,
        severity="high",
        flagged_labels=["tiktok_watermark"],
        notes="TikTok watermark detected in bottom-right corner"
    )
    assert valid_res.watermark_detected is True
    assert valid_res.severity == "high"
    assert valid_res.confidence == 0.92

    # Invalid severity (not in Literal)
    with pytest.raises(ValidationError):
        ModerationResult(
            watermark_detected=True,
            confidence=0.92,
            severity="critical",  # Invalid! Must be none, low, medium, or high
            flagged_labels=[],
            notes="Invalid severity"
        )

    # Invalid confidence range
    with pytest.raises(ValidationError):
        ModerationResult(
            watermark_detected=False,
            confidence=1.5,  # Invalid! Must be <= 1.0
            severity="none",
            flagged_labels=[],
            notes="Invalid confidence"
        )


def test_moderation_request_path_traversal():
    # Path traversal rejected
    with pytest.raises(ValidationError):
        ModerationCheckRequest(video_path="../../etc/passwd")

    with pytest.raises(ValidationError):
        ModerationCheckRequest(video_path="video\0null.mp4")


def test_moderation_service_file_not_found():
    with pytest.raises(FileNotFoundError):
        check_content_moderation("nonexistent_video_12345.mp4")


@patch("backend.services.content_moderation.get_video_duration", return_value=15.0)
@patch("backend.services.content_moderation._extract_frame_at_time", return_value=True)
def test_moderation_service_heuristic_clean(mock_extract, mock_dur, tmp_path):
    test_video = tmp_path / "clean_sample.mp4"
    test_video.write_text("dummy video content")

    with patch("backend.services.content_moderation.GEMINI_API_KEY", None):
        result = check_content_moderation(str(test_video))
        assert result["watermark_detected"] is False
        assert result["severity"] == "none"
        assert result["confidence"] >= 0.70


@patch("backend.services.content_moderation.get_video_duration", return_value=20.0)
@patch("backend.services.content_moderation._extract_frame_at_time", return_value=True)
def test_moderation_service_heuristic_watermark_flagged(mock_extract, mock_dur, tmp_path):
    test_video = tmp_path / "tiktok_sample_with_watermark.mp4"
    test_video.write_text("dummy video content")

    with patch("backend.services.content_moderation.GEMINI_API_KEY", None):
        result = check_content_moderation(str(test_video))
        assert result["watermark_detected"] is True
        assert result["severity"] in ["low", "medium", "high"]
        assert "watermark_heuristic" in result["flagged_labels"]


@patch("backend.services.content_moderation.get_video_duration", return_value=12.0)
@patch("backend.services.content_moderation._extract_frame_at_time", return_value=True)
@patch("backend.services.content_moderation.sync_retry")
def test_moderation_service_gemini_vision(mock_retry, mock_extract, mock_dur, tmp_path):
    test_video = tmp_path / "branded_reel.mp4"
    test_video.write_text("dummy video content")

    mock_retry.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": '```json\n{"watermark_detected": true, "confidence": 0.88, "severity": "medium", "flagged_labels": ["instagram_watermark"], "notes": "Instagram Reels watermark visible"}\n```'
                }]
            }
        }]
    }

    with patch("backend.services.content_moderation.GEMINI_API_KEY", "dummy_key"):
        result = check_content_moderation(str(test_video))
        assert result["watermark_detected"] is True
        assert result["confidence"] == 0.88
        assert result["severity"] == "medium"
        assert "instagram_watermark" in result["flagged_labels"]


def test_moderation_api_job_lifecycle(tmp_path):
    test_video = tmp_path / "reel_to_moderate.mp4"
    test_video.write_text("dummy video content")

    with patch("backend.services.content_moderation.check_content_moderation") as mock_mod:
        mock_mod.return_value = {
            "watermark_detected": False,
            "confidence": 0.95,
            "severity": "none",
            "flagged_labels": [],
            "notes": "Video is clean."
        }

        # 1. Start Job
        create_res = client.post("/api/video/moderation-check", json={"video_path": str(test_video)})
        assert create_res.status_code == 200
        data = create_res.json()
        assert "job_id" in data
        assert data["status"] == "PENDING"
        job_id = data["job_id"]

        # Background task runs synchronously in TestClient or we can check status
        status_res = client.get(f"/api/video/moderation-check/status/{job_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] == "COMPLETED"
        assert status_data["result"]["watermark_detected"] is False
        assert status_data["result"]["severity"] == "none"


def test_moderation_api_unknown_job():
    res = client.get("/api/video/moderation-check/status/non-existent-uuid")
    assert res.status_code == 404
