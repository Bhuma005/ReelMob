"""
test_atomic_claim.py — Unit tests for atomic worker claiming and pre-upload idempotency in workflow_upload.py.
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import pytest
from cloud.workflow_upload import claim_video, process_pending_uploads


def test_claim_video_successful():
    """Verify that a pending video is claimed atomically by a worker."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq = MagicMock()
    mock_update.eq.return_value = mock_eq
    mock_in = MagicMock()
    mock_eq.in_.return_value = mock_in
    mock_in.execute.return_value = MagicMock(data=[{"id": "vid-123", "upload_status": "claimed"}])

    claimed = claim_video(mock_sb, "vid-123", "worker-A", lease_minutes=15)
    assert claimed is True
    assert mock_table.update.called
    update_data = mock_table.update.call_args[0][0]
    assert update_data["upload_status"] == "claimed"
    assert update_data["worker_id"] == "worker-A"
    assert "lease_expires_at" in update_data


def test_claim_video_concurrent_collision():
    """Verify that if another worker claimed it concurrently, claim_video returns False."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_sb.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq = MagicMock()
    mock_update.eq.return_value = mock_eq
    mock_in = MagicMock()
    mock_eq.in_.return_value = mock_in
    mock_in.execute.return_value = MagicMock(data=[])  # 0 rows updated

    claimed = claim_video(mock_sb, "vid-123", "worker-B", lease_minutes=15)
    assert claimed is False


def test_process_pending_uploads_idempotency_skip():
    """Verify pre-upload idempotency check skips YouTube upload if video was already published."""
    mock_sb = MagicMock()
    now_utc = datetime.now(timezone.utc).isoformat()

    # Scheduled videos query returns 1 pending video
    candidate = {
        "id": "q-1",
        "library_video_id": "lib-99",
        "title": "Idempotent Reel",
        "description": "Desc",
        "hashtags": ["#shorts"],
        "storage_path": "reels/v.mp4",
        "upload_status": "pending",
        "schedule_time": now_utc,
    }

    mock_sv_table = MagicMock()
    mock_lib_table = MagicMock()

    def table_router(table_name):
        if table_name == "scheduled_videos":
            return mock_sv_table
        elif table_name == "video_library":
            return mock_lib_table
        return MagicMock()

    mock_sb.table.side_effect = table_router

    # Candidate query
    mock_sv_select = MagicMock()
    mock_sv_table.select.return_value = mock_sv_select
    mock_sv_in = MagicMock()
    mock_sv_select.in_.return_value = mock_sv_in
    mock_sv_lte = MagicMock()
    mock_sv_in.lte.return_value = mock_sv_lte
    mock_sv_order = MagicMock()
    mock_sv_lte.order.return_value = mock_sv_order
    mock_sv_limit = MagicMock()
    mock_sv_order.limit.return_value = mock_sv_limit
    mock_sv_limit.execute.return_value = MagicMock(data=[candidate])

    # Claim update succeeds
    mock_update_chain = MagicMock()
    mock_sv_table.update.return_value = mock_update_chain
    mock_update_chain.eq.return_value = mock_update_chain
    mock_update_chain.in_.return_value = mock_update_chain
    mock_update_chain.execute.return_value = MagicMock(data=[candidate])

    # Library query shows already published with youtube_video_id
    mock_lib_select = MagicMock()
    mock_lib_table.select.return_value = mock_lib_select
    mock_lib_eq = MagicMock()
    mock_lib_select.eq.return_value = mock_lib_eq
    mock_lib_eq.execute.return_value = MagicMock(data=[{
        "id": "lib-99",
        "youtube_video_id": "yt-existing-abc",
        "status": "published"
    }])

    with patch("cloud.workflow_upload.get_supabase_client", return_value=mock_sb), \
         patch("cloud.workflow_upload.get_youtube_service") as mock_yt_svc:

        process_pending_uploads(worker_id="test-worker")

        # YouTube upload should NOT be initialized or called!
        assert not mock_yt_svc.called
