"""
test_durable_jobs.py — Unit tests for JobStore durable PostgreSQL and in-memory caching layer.
Verifies read-through, write-through, in-place dictionary mutations, and graceful degradation.
"""

from unittest.mock import MagicMock, patch
import pytest
from backend.services.job_store import JobStore, TrackedJob


def test_job_store_in_memory_crud():
    """Verify in-memory dictionary-like CRUD operations work without database connection."""
    store = JobStore(default_type="test_job")
    assert len(store) == 0

    # 1. Create job
    job = store.create_job("job-101", initial_data={"url": "https://example.com/video.mp4"})
    assert isinstance(job, TrackedJob)
    assert job["status"] == "QUEUED"
    assert job["progress"] == 0
    assert job["url"] == "https://example.com/video.mp4"
    assert "job-101" in store
    assert len(store) == 1

    # 2. In-place mutations
    job["status"] = "PROCESSING"
    job["progress"] = 45
    job["current_step"] = "Transcoding audio"

    fetched = store.get("job-101")
    assert fetched["status"] == "PROCESSING"
    assert fetched["progress"] == 45
    assert fetched["current_step"] == "Transcoding audio"

    # 3. Direct assignment
    store["job-102"] = {"status": "COMPLETED", "progress": 100}
    assert "job-102" in store
    assert store["job-102"]["status"] == "COMPLETED"

    # 4. Iteration and clear
    keys = list(store.keys())
    assert set(keys) == {"job-101", "job-102"}
    store.clear()
    assert len(store) == 0


def test_job_store_read_through_from_database():
    """Verify that when a key is absent from memory, JobStore reads through to PostgreSQL."""
    store = JobStore(default_type="ai_analysis")

    mock_row = {
        "id": "job-db-777",
        "job_type": "ai_analysis",
        "status": "completed",
        "progress": 100,
        "current_step": "Optimization finished",
        "result_reference": {"title": "Viral Reel 2026"},
        "input_reference": {"raw_title": "Original Title"},
        "error_message": None,
        "created_at": "2026-09-20T12:00:00Z"
    }

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_limit = MagicMock()
    mock_eq.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[mock_row])

    with patch.object(store, "_get_supabase_client", return_value=mock_sb):
        assert "job-db-777" not in store._memory

        # Accessing triggers read-through
        assert "job-db-777" in store
        job = store["job-db-777"]

        assert job["job_id"] == "job-db-777"
        assert job["status"] == "COMPLETED"
        assert job["progress"] == 100
        assert job["result"]["title"] == "Viral Reel 2026"
        assert job["raw_title"] == "Original Title"

        # Now cached in memory
        assert "job-db-777" in store._memory


def test_job_store_write_through_to_database():
    """Verify that job creation and updates call Supabase upsert."""
    store = JobStore(default_type="highlight_detection")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_upsert = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value = MagicMock(data=[{}])

    with patch.object(store, "_get_supabase_client", return_value=mock_sb):
        job = store.create_job("job-hl-1", initial_data={"video_path": "/tmp/v.mp4"})
        assert mock_sb.table.called
        assert mock_table.upsert.called

        # Modify job
        job["status"] = "COMPLETED"
        job["progress"] = 100

        # Check upsert payload contains valid status mapping
        last_upsert_payload = mock_table.upsert.call_args[0][0]
        assert last_upsert_payload["id"] == "job-hl-1"
        assert last_upsert_payload["status"] == "completed"
        assert last_upsert_payload["progress"] == 100
        assert last_upsert_payload["completed_at"] is not None


def test_job_store_graceful_degradation_on_db_failure():
    """Verify that database errors do not crash job processing."""
    store = JobStore(default_type="content_moderation")

    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_table.upsert.side_effect = RuntimeError("Database connection timed out")

    with patch.object(store, "_get_supabase_client", return_value=mock_sb):
        # Should not raise exception
        job = store.create_job("job-failover", initial_data={"status": "PROCESSING"})
        job["progress"] = 50

        # Memory store maintains state perfectly
        assert store["job-failover"]["progress"] == 50
