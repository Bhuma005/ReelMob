"""
test_cleanup_permanence.py — Unit tests ensuring library permanence and storage soft-deletion.
Verifies that metadata rows in video_library are never deleted during user deletion or scheduled cleanup.
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app, RATE_LIMIT_STORE
from cloud.workflow_cleanup import process_cleanup


@pytest.fixture
def client():
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_delete_dashboard_video_permanently_retains_library_record(client):
    """Verify that deleting a video soft-deletes storage and marks status='cleaned' without deleting row."""
    mock_sb = MagicMock()
    mock_lib_table = MagicMock()
    mock_sv_table = MagicMock()
    mock_log_table = MagicMock()

    def table_router(table_name):
        if table_name == "video_library":
            return mock_lib_table
        elif table_name == "scheduled_videos":
            return mock_sv_table
        elif table_name == "video_activity_log":
            return mock_log_table
        return MagicMock()

    mock_sb.table.side_effect = table_router

    # Mock video lookup
    mock_select = MagicMock()
    mock_lib_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_eq.execute.return_value = MagicMock(data=[{
        "storage_path": "reels/test.mp4",
        "title": "Permanent Video"
    }])

    # Mock storage remove
    mock_storage = MagicMock()
    mock_bucket = MagicMock()
    mock_sb.storage.from_.return_value = mock_bucket

    # Mock update
    mock_update = MagicMock()
    mock_lib_table.update.return_value = mock_update
    mock_update_eq = MagicMock()
    mock_update.eq.return_value = mock_update_eq
    mock_update_eq.execute.return_value = MagicMock(data=[{}])

    # Clean up any local audit log before test
    if os.path.exists("reelgrab_audit.log"):
        os.remove("reelgrab_audit.log")

    with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
        res = client.delete("/api/dashboard/videos/vid-perm-123")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"

        # Verify storage was purged
        mock_bucket.remove.assert_called_with(["reels/test.mp4"])

        # Verify video_library was UPDATED, NEVER DELETED
        assert not mock_lib_table.delete.called
        assert mock_lib_table.update.called
        update_payload = mock_lib_table.update.call_args[0][0]
        assert update_payload["status"] == "cleaned"
        assert update_payload["storage_path"] is None
        assert "storage_deleted_at" in update_payload

        # Verify no local disk file logging
        assert not os.path.exists("reelgrab_audit.log")


def test_workflow_cleanup_retains_library_record():
    """Verify that workflow_cleanup.py updates video_library to 'cleaned' and does not delete it."""
    mock_sb = MagicMock()
    mock_lib_table = MagicMock()
    mock_sv_table = MagicMock()
    mock_audit_table = MagicMock()
    mock_log_table = MagicMock()

    def table_router(table_name):
        if table_name == "video_library":
            return mock_lib_table
        elif table_name == "scheduled_videos":
            return mock_sv_table
        elif table_name == "videos_audit_log":
            return mock_audit_table
        elif table_name == "video_activity_log":
            return mock_log_table
        return MagicMock()

    mock_sb.table.side_effect = table_router

    candidate = {
        "id": "q-cleanup-1",
        "library_video_id": "lib-cleanup-1",
        "title": "Cleanup Test Video",
        "youtube_video_id": "yt-cleaned-99",
        "storage_path": "reels/expired.mp4",
        "uploaded_at": "2026-09-18T10:00:00Z"
    }

    # Query for expired videos
    mock_select = MagicMock()
    mock_sv_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_lte = MagicMock()
    mock_eq.lte.return_value = mock_lte
    mock_order = MagicMock()
    mock_lte.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[candidate])

    # Storage remove mock
    mock_bucket = MagicMock()
    mock_sb.storage.from_.return_value = mock_bucket

    # Library update mock
    mock_update = MagicMock()
    mock_lib_table.update.return_value = mock_update
    mock_update.eq.return_value = mock_update
    mock_update.execute.return_value = MagicMock(data=[{}])

    with patch("cloud.workflow_cleanup.get_supabase_client", return_value=mock_sb):
        process_cleanup()

        # Storage remove called
        mock_bucket.remove.assert_called_with(["reels/expired.mp4"])

        # video_library NEVER deleted
        assert not mock_lib_table.delete.called
        assert mock_lib_table.update.called
        update_args = mock_lib_table.update.call_args[0][0]
        assert update_args["status"] == "cleaned"
        assert update_args["storage_path"] is None


def test_delete_dashboard_video_permanent_deletes_record(client):
    """Verify that deleting with permanent=True or when already cleaned deletes row from video_library."""
    mock_sb = MagicMock()
    mock_lib_table = MagicMock()
    mock_sv_table = MagicMock()

    def table_router(table_name):
        if table_name == "video_library":
            return mock_lib_table
        elif table_name == "scheduled_videos":
            return mock_sv_table
        return MagicMock()

    mock_sb.table.side_effect = table_router

    # Video lookup returns already-cleaned record
    mock_select = MagicMock()
    mock_lib_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_eq.execute.return_value = MagicMock(data=[{
        "storage_path": None,
        "title": "Cleaned Video",
        "status": "cleaned"
    }])

    # Delete mock
    mock_delete = MagicMock()
    mock_lib_table.delete.return_value = mock_delete
    mock_del_eq = MagicMock()
    mock_delete.eq.return_value = mock_del_eq
    mock_del_eq.execute.return_value = MagicMock(data=[{}])

    with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
        res = client.delete("/api/dashboard/videos/vid-perm-cleaned")
        assert res.status_code == 200
        assert "permanently deleted" in res.json()["message"]
        assert mock_lib_table.delete.called


def test_clear_all_cleaned_videos_endpoint(client):
    """Verify that POST /api/dashboard/videos/clear-cleaned deletes all cleaned records."""
    mock_sb = MagicMock()
    mock_lib_table = MagicMock()
    mock_sv_table = MagicMock()

    def table_router(table_name):
        if table_name == "video_library":
            return mock_lib_table
        elif table_name == "scheduled_videos":
            return mock_sv_table
        return MagicMock()

    mock_sb.table.side_effect = table_router

    # Lookup returns 3 cleaned video ids
    mock_select = MagicMock()
    mock_lib_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_eq.execute.return_value = MagicMock(data=[
        {"id": "id-1"}, {"id": "id-2"}, {"id": "id-3"}
    ])

    # Delete in mock
    mock_delete = MagicMock()
    mock_lib_table.delete.return_value = mock_delete
    mock_in = MagicMock()
    mock_delete.in_.return_value = mock_in
    mock_in.execute.return_value = MagicMock(data=[{}])

    with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
        res = client.post("/api/dashboard/videos/clear-cleaned")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 3


def test_clear_activity_logs_endpoint(client):
    """Verify that POST /api/dashboard/logs/clear clears activity logs."""
    mock_sb = MagicMock()
    mock_log_table = MagicMock()

    mock_sb.table.return_value = mock_log_table
    mock_delete = MagicMock()
    mock_log_table.delete.return_value = mock_delete
    mock_neq = MagicMock()
    mock_delete.neq.return_value = mock_neq
    mock_neq.execute.return_value = MagicMock(data=[{}])

    with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
        res = client.post("/api/dashboard/logs/clear")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

