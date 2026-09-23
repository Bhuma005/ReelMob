import pytest
from fastapi.testclient import TestClient
from backend.main import app, RATE_LIMIT_STORE, LOCAL_VIDEO_TAGS

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_rate_limit():
    RATE_LIMIT_STORE.clear()
    yield
    RATE_LIMIT_STORE.clear()

def test_search_empty_query():
    res = client.get("/api/dashboard/search?q=")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == ""
    assert data["results"] == []
    assert data["total"] == 0

def test_search_with_matching_tag():
    # Setup test video in LOCAL_VIDEO_TAGS
    LOCAL_VIDEO_TAGS["test-search-vid-1"] = ["fintech", "investing"]
    
    res = client.get("/api/dashboard/search?q=fintech")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "fintech"
    assert data["total"] >= 1
    found = any(r["id"] == "test-search-vid-1" for r in data["results"])
    assert found


def test_search_database_pushdown_query():
    from unittest.mock import MagicMock, patch
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_or = MagicMock()
    mock_select.or_.return_value = mock_or
    mock_limit = MagicMock()
    mock_or.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[{
        "id": "vid-db-pushdown",
        "title": "Machine Learning in 60s",
        "description": "Shorts tutorial",
        "tags": ["ml", "ai"],
        "status": "published"
    }])

    with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
        res = client.get("/api/dashboard/search?q=machine")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["results"][0]["id"] == "vid-db-pushdown"
        assert data["results"][0]["match_field"] == "title"
        # Verify .or_ filter was executed on table query
        assert mock_select.or_.called

