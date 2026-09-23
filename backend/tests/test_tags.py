"""
test_tags.py — Unit and API integration tests for Content Tagging & Performance-by-Tag.
"""

import os
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.main import app, RATE_LIMIT_STORE
from backend.schemas import UpdateVideoTagsRequest
from backend.services.analytics_trends import calculate_performance_by_tag


@pytest.fixture
def client():
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_migration_006_exists():
    mig_path = os.path.join("cloud", "006_add_video_tags.sql")
    assert os.path.exists(mig_path), "Migration 006_add_video_tags.sql must exist"
    with open(mig_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "tags text[]" in content
    assert "idx_video_library_tags" in content
    assert "GIN" in content


def test_update_video_tags_validation():
    # Valid tags are cleaned, trimmed, lowercased, and deduplicated
    req = UpdateVideoTagsRequest(tags=["Viral", "  Shorts ", "viral", "hook_1", "step-2"])
    assert req.tags == ["viral", "shorts", "hook_1", "step-2"]

    # Special characters blocked
    with pytest.raises(ValidationError):
        UpdateVideoTagsRequest(tags=["bad tag with spaces"])

    with pytest.raises(ValidationError):
        UpdateVideoTagsRequest(tags=["bad$char!"])

    # Overly long tag (> 30 chars) blocked
    with pytest.raises(ValidationError):
        UpdateVideoTagsRequest(tags=["a" * 31])

    # Too many tags (> 15) blocked
    with pytest.raises(ValidationError):
        UpdateVideoTagsRequest(tags=[f"tag{i}" for i in range(20)])


def test_update_video_tags_api_endpoint(client):
    res = client.patch("/api/dashboard/videos/vid-test-456/tags", json={
        "tags": ["trending", "behind_the_scenes", "hook"]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["id"] == "vid-test-456"
    assert data["tags"] == ["trending", "behind_the_scenes", "hook"]


def test_tag_performance_insufficient_data():
    data = calculate_performance_by_tag(days=30, records=[])
    assert data["status"] == "ANALYTICS_UNAVAILABLE"
    assert data["tags"] == []


def test_tag_performance_calculation_and_endpoint(client):
    mock_records = [
        {"id": "1", "title": "V1", "status": "published", "views": 1000, "likes": 50, "comments": 5, "tags": ["tech", "ai"]},
        {"id": "2", "title": "V2", "status": "published", "views": 2000, "likes": 100, "comments": 10, "tags": ["tech"]},
        {"id": "3", "title": "V3", "status": "published", "views": 3000, "likes": 150, "comments": 15, "tags": ["ai", "growth"]},
    ]
    data = calculate_performance_by_tag(days=30, records=mock_records)
    assert data["status"] == "READY"
    assert "tags" in data
    assert len(data["tags"]) > 0

    for item in data["tags"]:
        assert "tag" in item
        assert "video_count" in item
        assert "avg_views" in item
        assert "avg_likes" in item
        assert "avg_engagement_rate" in item
        assert item["benchmark_status"] in ["overperforming", "average", "underperforming"]

    # API endpoint returns 200 with tags list
    res = client.get("/api/dashboard/analytics/tags?days=30")
    assert res.status_code == 200
    res_data = res.json()
    assert "tags" in res_data
