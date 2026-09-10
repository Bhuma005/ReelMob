"""
test_video_editor.py — Unit and API integration tests for the video editing engine.
"""

import os
import subprocess
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.video_editor import (
    _escape_drawtext,
    get_video_duration,
    process_video_edit,
)
from backend.fit_to_canvas import get_ff_paths


@pytest.fixture(scope="module")
def sample_video():
    """Generates a small 1-second 640x360 MP4 for testing."""
    os.makedirs("downloads", exist_ok=True)
    ffmpeg, _ = get_ff_paths()
    path = "downloads/test_edit_source.mp4"

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=640x360:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1",
        "-c:v", "libx264",
        "-c:a", "aac",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield path

    if os.path.exists(path):
        os.remove(path)


def test_escape_drawtext():
    assert _escape_drawtext("Hello World") == "Hello World"
    assert "\\:" in _escape_drawtext("Time: 12:00")
    assert "\\%" in _escape_drawtext("100% Viral")
    assert "\\\\" in _escape_drawtext("Path\\Test")


def test_process_video_edit_trim_and_filters(sample_video):
    out_path = "downloads/test_edit_output.mp4"
    try:
        res = process_video_edit(
            input_path=sample_video,
            output_path=out_path,
            trim={"start": 0.1, "end": 0.8},
            color={"brightness": 0.05, "contrast": 1.1, "saturation": 1.2},
            captions={"text": "Trending Now", "font_size": 24, "position": "bottom", "color": "yellow"},
            watermark={"text": "@ReelsMob", "position": "top-right", "opacity": 0.8},
            framing="blur_pad",
            target_width=1080,
            target_height=1920
        )
        assert os.path.exists(out_path)
        assert res["width"] == 1080
        assert res["height"] == 1920
        assert res["duration"] > 0
        assert res["size_bytes"] > 0
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_api_video_edit_endpoint_validation():
    client = TestClient(app)

    # 1. Path traversal rejected by schema validator
    res = client.post("/api/video/edit", json={"video_path": "../../etc/passwd"})
    assert res.status_code == 422 or res.status_code == 400

    # 2. Non-existent video returns 404
    res = client.post("/api/video/edit", json={"video_path": "non_existent_12345.mp4"})
    assert res.status_code == 404


def test_api_video_edit_endpoint_success(sample_video):
    client = TestClient(app)
    filename = os.path.basename(sample_video)

    payload = {
        "video_path": filename,
        "trim": {"start": 0.0, "end": 0.5},
        "color": {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0},
        "captions": {"text": "Hook Scene", "font_size": 20, "position": "center", "color": "white"},
        "framing": "crop"
    }

    res = client.post("/api/video/edit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "edited_" in data["video_path"]
    assert data["metadata"]["width"] == 1080
    assert data["metadata"]["height"] == 1920

    # Cleanup generated file
    full_path = data.get("full_path")
    if full_path and os.path.exists(full_path):
        os.remove(full_path)
