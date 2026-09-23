"""
test_analytics_trends.py — Unit and API integration tests for Analytics Trend Comparison.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app, RATE_LIMIT_STORE
from backend.services.analytics_trends import calculate_channel_trends


@pytest.fixture
def client():
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_calculate_channel_trends_insufficient_data():
    """Verify that when fewer than 3 records exist, no synthetic data is fabricated."""
    data = calculate_channel_trends(days=30, records=[])
    assert data["status"] == "ANALYTICS_UNAVAILABLE"
    assert data["summary"]["total_videos"] == 0
    assert data["summary"]["rolling_avg_views"] == 0.0
    assert len(data["trends"]) == 0


def test_calculate_channel_trends_with_records():
    """Verify mathematical calculation when sufficient real records exist."""
    mock_records = [
        {
            "id": "vid-1",
            "title": "Top Performing Reel",
            "status": "published",
            "views": 10000,
            "likes": 800,
            "comments": 50,
            "created_at": "2026-09-20T10:00:00Z"
        },
        {
            "id": "vid-2",
            "title": "Average Reel",
            "status": "published",
            "views": 5000,
            "likes": 300,
            "comments": 20,
            "created_at": "2026-09-21T10:00:00Z"
        },
        {
            "id": "vid-3",
            "title": "Underperforming Reel",
            "status": "published",
            "views": 2000,
            "likes": 80,
            "comments": 5,
            "created_at": "2026-09-22T10:00:00Z"
        }
    ]
    data = calculate_channel_trends(days=30, records=mock_records)
    assert data["status"] == "READY"
    summary = data["summary"]
    assert summary["days"] == 30
    assert summary["total_videos"] == 3
    # Average: (10000 + 5000 + 2000) / 3 = 5666.7
    assert round(summary["rolling_avg_views"]) == 5667
    assert summary["overperforming_count"] == 1  # 10000 is > 5666.7 * 1.15 (6516.7)
    assert summary["underperforming_count"] == 1 # 2000 is < 5666.7 * 0.85 (4816.7)
    assert summary["average_count"] == 1         # 5000 is between 4816.7 and 6516.7

    trends = data["trends"]
    assert len(trends) == 3

    for item in trends:
        assert "date" in item
        assert "iso_date" in item
        assert "video_id" in item
        assert "views" in item
        assert "rolling_avg_views" in item
        assert "diff_pct" in item
        assert item["performance"] in ["overperforming", "average", "underperforming"]

        # Mathematical verification of classification
        if item["diff_pct"] >= 15.0:
            assert item["performance"] == "overperforming"
        elif item["diff_pct"] <= -15.0:
            assert item["performance"] == "underperforming"
        else:
            assert item["performance"] == "average"


def test_analytics_trends_api_endpoint(client):
    res = client.get("/api/dashboard/analytics/trends?days=30")
    assert res.status_code == 200
    json_data = res.json()
    assert "summary" in json_data
    assert "trends" in json_data
    assert json_data["summary"]["days"] == 30


def test_analytics_trends_api_custom_days(client):
    res = client.get("/api/dashboard/analytics/trends?days=7")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["summary"]["days"] == 7

