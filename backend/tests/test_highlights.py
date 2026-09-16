"""
test_highlights.py — Unit and API integration tests for Multi-Clip Highlight Detection.
"""

import os
import time
import subprocess
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import HighlightRequest
from backend.services.highlight_detector import detect_highlights
from backend.fit_to_canvas import get_ff_paths


@pytest.fixture(scope="module")
def sample_video_path():
    """Generates a 6-second sample test video."""
    os.makedirs("downloads", exist_ok=True)
    ffmpeg, _ = get_ff_paths()
    path = "downloads/test_highlight_source.mp4"

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=6:size=640x360:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=6",
        "-c:v", "libx264",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield path

    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def test_highlight_request_validation():
    # Valid model
    req = HighlightRequest(video_path="sample.mp4", target_duration_min=15, target_duration_max=45, num_clips=3)
    assert req.video_path == "sample.mp4"
    assert req.num_clips == 3

    # Path traversal blocked
    with pytest.raises(ValidationError):
        HighlightRequest(video_path="../../etc/passwd")

    # Target duration bounds
    with pytest.raises(ValidationError):
        HighlightRequest(video_path="sample.mp4", target_duration_min=2.0)  # min ge 5.0

    # Num clips bounds
    with pytest.raises(ValidationError):
        HighlightRequest(video_path="sample.mp4", num_clips=10)  # le 5


def test_detect_highlights_fallback(sample_video_path):
    clips = detect_highlights(
        video_path=sample_video_path,
        target_duration_min=2.0,
        target_duration_max=5.0,
        num_clips=2
    )
    assert len(clips) >= 1
    for c in clips:
        assert "start" in c
        assert "end" in c
        assert "reason" in c
        assert "confidence" in c
        assert c["start"] >= 0.0
        assert c["end"] > c["start"]
        assert 0.0 <= c["confidence"] <= 1.0


@pytest.fixture
def client():
    from backend.main import RATE_LIMIT_STORE
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_highlights_api_job_lifecycle(client, sample_video_path):
    # 1. Create job
    res = client.post("/api/video/highlights", json={
        "video_path": os.path.basename(sample_video_path),
        "target_duration_min": 15.0,
        "target_duration_max": 45.0,
        "num_clips": 2
    })
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["status"] in ["PENDING", "PROCESSING", "COMPLETED"]

    job_id = data["job_id"]

    # 2. Poll status
    completed = False
    for _ in range(15):
        poll_res = client.get(f"/api/video/highlights/status/{job_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        if poll_data["status"] == "COMPLETED":
            assert isinstance(poll_data["highlights"], list)
            assert len(poll_data["highlights"]) > 0
            completed = True
            break
        elif poll_data["status"] == "FAILED":
            pytest.fail(f"Highlight job failed: {poll_data.get('error')}")
        time.sleep(0.3)

    assert completed, "Highlight job did not complete in time"


def test_highlights_api_404(client):
    res = client.get("/api/video/highlights/status/nonexistent-uuid-9999")
    assert res.status_code == 404
