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


def test_calculate_channel_trends_structure_and_benchmarks():
    data = calculate_channel_trends(days=30)
    assert "summary" in data
    assert "trends" in data

    summary = data["summary"]
    assert summary["days"] == 30
    assert summary["total_videos"] > 0
    assert summary["rolling_avg_views"] > 0
    assert summary["rolling_avg_likes"] >= 0
    assert summary["rolling_avg_engagement_rate"] >= 0

    assert (
        summary["overperforming_count"]
        + summary["underperforming_count"]
        + summary["average_count"]
        == summary["total_videos"]
    )

    trends = data["trends"]
    assert len(trends) == summary["total_videos"]

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
    assert len(json_data["trends"]) > 0


def test_analytics_trends_api_custom_days(client):
    res = client.get("/api/dashboard/analytics/trends?days=7")
    assert res.status_code == 200
    json_data = res.json()
    assert json_data["summary"]["days"] == 7
