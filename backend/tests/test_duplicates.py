"""
test_duplicates.py — Unit and API integration tests for Duplicate & Near-Duplicate Detection.
"""

import os
import subprocess
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.schemas import DuplicateCheckRequest
from backend.services.duplicate_detector import (
    compute_image_dhash,
    hamming_distance,
    compute_video_perceptual_hash,
    check_video_duplicate,
    register_video_hash,
    LOCAL_HASH_REGISTRY,
)
from backend.fit_to_canvas import get_ff_paths


@pytest.fixture(scope="module")
def sample_dup_video():
    """Generates a small 3-second sample MP4 for testing duplicate hashing."""
    os.makedirs("downloads", exist_ok=True)
    ffmpeg, _ = get_ff_paths()
    path = "downloads/test_dup_source.mp4"

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3:size=320x240:rate=25",
        "-c:v", "libx264",
        path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield path

    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def test_migration_005_exists():
    mig_path = os.path.join("cloud", "005_add_perceptual_hash.sql")
    assert os.path.exists(mig_path), "Migration 005_add_perceptual_hash.sql must exist"
    with open(mig_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "perceptual_hash" in content
    assert "video_library" in content
    assert "CREATE INDEX" in content


def test_dhash_and_hamming_distance():
    img1 = Image.new("RGB", (64, 64), color="blue")
    img2 = Image.new("RGB", (64, 64), color="blue")
    img3 = Image.new("RGB", (64, 64), color="red")

    h1 = compute_image_dhash(img1)
    h2 = compute_image_dhash(img2)
    assert h1 == h2
    assert len(h1) == 16
    assert hamming_distance(h1, h2) == 0

    # Gradient image to test bit difference
    grad = Image.new("L", (9, 8))
    grad.putdata([x * 25 for y in range(8) for x in range(9)])
    h_grad = compute_image_dhash(grad)
    assert isinstance(h_grad, str)
    assert len(h_grad) == 16


def test_check_video_duplicate_detection(sample_dup_video):
    # 1. Compute hash for sample video
    h = compute_video_perceptual_hash(sample_dup_video)
    assert len(h) == 16

    # 2. Register this hash into library
    register_video_hash("vid-test-101", "Existing Viral Reel", h)

    # 3. Check duplicate
    res = check_video_duplicate(sample_dup_video, threshold=5)
    assert res["is_duplicate"] is True
    assert res["hash"] == h
    assert len(res["matches"]) >= 1

    match = res["matches"][0]
    assert match["id"] == "vid-test-101"
    assert match["distance"] == 0
    assert match["similarity_pct"] == 100.0


@pytest.fixture
def client():
    from backend.main import RATE_LIMIT_STORE
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_duplicate_check_api_endpoint(client, sample_dup_video):
    # Valid request
    res = client.post("/api/video/check-duplicate", json={
        "video_path": os.path.basename(sample_dup_video),
        "threshold": 10
    })
    assert res.status_code == 200
    data = res.json()
    assert "is_duplicate" in data
    assert "hash" in data
    assert "matches" in data
    assert len(data["hash"]) == 16


def test_duplicate_check_api_validation_and_404(client):
    # Path traversal rejected with 422
    res = client.post("/api/video/check-duplicate", json={
        "video_path": "../../etc/shadow",
        "threshold": 10
    })
    assert res.status_code == 422

    # Non-existent file returns 404
    res = client.post("/api/video/check-duplicate", json={
        "video_path": "totally_non_existent_file_9999.mp4",
        "threshold": 10
    })
    assert res.status_code == 404

