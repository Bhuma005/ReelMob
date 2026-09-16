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
