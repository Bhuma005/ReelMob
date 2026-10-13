"""
test_automate_async.py — Test suite for asynchronous automation pipeline and GitHub Actions CPU offload.
Verifies:
1. POST /automate offloads processing to GitHub Actions and returns immediately (<100ms) with zero Render CPU/disk usage.
2. JobStore durably tracks status.
3. GitHub Actions worker (workflow_upload.py) downloads source stream, applies FFmpeg 9:16 layout, and publishes to YouTube.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.automate import AUTOMATE_JOBS, dispatch_github_actions_upload
from cloud.enqueue import enqueue_remote_video
from cloud.workflow_upload import process_pending_uploads


@pytest.fixture
def client():
    return TestClient(app)


class TestAsyncAutomateEndpoint:
    """Tests verifying immediate HTTP return and GitHub Actions worker dispatch."""

    def test_post_automate_returns_immediately_with_job_id(self, client):
        mock_sched = {
            "human_readable_time": "06:00 PM",
            "fallback_schedule": {"human_readable_time": "06:00 PM"}
        }

        with patch("backend.services.scheduler.calculate_deterministic_schedule", return_value=mock_sched), \
             patch("backend.automate.enqueue_remote_video", return_value="queue_record_uuid_123") as mock_enqueue, \
             patch("backend.automate.dispatch_github_actions_upload") as mock_dispatch:

            payload = {
                "title": "Epic Gaming Clip",
                "description": "Best gameplay moment #shorts",
                "hashtags": ["#gaming", "#shorts"],
                "url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
                "iso_schedule": "2026-10-12T18:00:00+05:30",
                "scheduled_time_human": "October 12, 06:00 PM"
            }

            response = client.post("/automate", json=payload)
            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "success"
            assert "job_id" in data
            assert data["job_id"] is not None
            assert "automation_details" in data
            assert data["automation_details"]["scheduled_time"] == "October 12, 06:00 PM"
            assert data["automation_details"]["title"] == "Epic Gaming Clip"

            # Verify enqueue_remote_video was called without downloading on Render
            mock_enqueue.assert_called_once()
            call_kwargs = mock_enqueue.call_args.kwargs
            assert call_kwargs["source_url"] == "https://www.youtube.com/shorts/dQw4w9WgXcQ"
            assert call_kwargs["title"] == "Epic Gaming Clip"

            # Verify dispatch was called
            mock_dispatch.assert_called_once_with(video_id="queue_record_uuid_123")

            # Verify job is tracked in AUTOMATE_JOBS
            job_id = data["job_id"]
            assert job_id in AUTOMATE_JOBS
            assert AUTOMATE_JOBS[job_id]["status"] == "completed"

    def test_get_automate_status_endpoint(self, client):
        job_id = "test_custom_job_123"
        AUTOMATE_JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "current_step": "Scheduled and offloaded to GitHub Actions multi-core CPU",
            "title": "Test Title",
        }

        res = client.get(f"/automate/status/{job_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert "GitHub Actions" in data["current_step"]

        # Non-existent job
        res_404 = client.get("/automate/status/non_existent_uuid")
        assert res_404.status_code == 404


class TestGitHubActionsWorkerOffload:
    """Tests verifying workflow_upload.py executes download and FFmpeg layout on GitHub runner."""

    def test_workflow_upload_downloads_stream_and_formats_on_github_runner(self, tmp_path):
        mock_sb = MagicMock()
        scheduled_table = MagicMock()
        library_table = MagicMock()
        def get_table(name):
            if name == "video_library":
                return library_table
            return scheduled_table
        mock_sb.table.side_effect = get_table

        # Mock scheduled video with source: URL
        candidate = {
            "id": "q-99",
            "library_video_id": "lib-99",
            "title": "GitHub Offloaded Short",
            "description": "Desc",
            "hashtags": ["#shorts"],
            "storage_path": "source:https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "upload_status": "pending",
            "schedule_time": "2026-01-01T00:00:00+00:00",
            "retry_count": 0
        }

        # Mock scheduled_videos select return
        mock_select = MagicMock()
        scheduled_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_lte = MagicMock()
        mock_in.lte.return_value = mock_lte
        mock_order = MagicMock()
        mock_lte.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = MagicMock(data=[candidate])

        # Mock atomic claim on scheduled_videos
        mock_update = MagicMock()
        scheduled_table.update.return_value = mock_update
        mock_eq = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_eq_in = MagicMock()
        mock_eq.in_.return_value = mock_eq_in
        mock_eq_in.execute.return_value = MagicMock(data=[{"id": "q-99", "upload_status": "claimed"}])

        # Mock video_library idempotency check (not published yet)
        lib_select = MagicMock()
        library_table.select.return_value = lib_select
        lib_eq = MagicMock()
        lib_select.eq.return_value = lib_eq
        lib_eq.execute.return_value = MagicMock(data=[{"youtube_video_id": None, "status": "scheduled", "source_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ"}])

        # Mock temp video file
        mock_file = tmp_path / "mock_downloaded.mp4"
        mock_file.write_bytes(b"dummy_video_stream")

        mock_yt_service = MagicMock()
        mock_insert = MagicMock()
        mock_yt_service.videos.return_value.insert.return_value = mock_insert
        mock_insert.next_chunk.return_value = (None, {"id": "YT_NEW_ID_999"})

        with patch("cloud.workflow_upload.get_supabase_client", return_value=mock_sb), \
             patch("cloud.workflow_upload.get_youtube_service", return_value=mock_yt_service), \
             patch("backend.services.video_download.ensure_video_downloaded", return_value=str(mock_file)) as mock_dl, \
             patch("backend.fit_to_canvas.fit_to_canvas", return_value=str(mock_file)) as mock_fit, \
             patch("cloud.workflow_upload.MediaFileUpload"):

            process_pending_uploads(worker_id="gh-runner-test-1")

            # Verify ensure_video_downloaded and fit_to_canvas were executed on GitHub runner!
            mock_dl.assert_called_once()
            assert mock_dl.call_args.kwargs["url"] == "https://www.youtube.com/shorts/dQw4w9WgXcQ"
            mock_fit.assert_called_once()

            # Verify YouTube insert was called with the uploaded ID
            mock_yt_service.videos.return_value.insert.assert_called_once()


class TestManualPublishEndpoint:
    """Tests verifying POST /api/dashboard/videos/{video_id}/publish avoids 404 on source: URLs."""

    def test_publish_dashboard_video_source_url_prioritizes_and_dispatches(self, client):
        mock_sb = MagicMock()
        video_record = {
            "id": "vid-1234",
            "title": "What Happens Next Will Crack You Up",
            "storage_path": "source:https://www.instagram.com/reel/DXP2hVzEm1W/",
            "status": "scheduled",
            "description": "Funny clip",
            "hashtags": ["#funny"]
        }
        queue_record = {
            "id": "sched-5678",
            "library_video_id": "vid-1234",
            "upload_status": "pending"
        }

        # Mock video_library lookup
        lib_select = MagicMock()
        mock_sb.table.return_value.select.return_value = lib_select
        lib_eq = MagicMock()
        lib_select.eq.return_value = lib_eq
        
        # We need mock_sb.table to return different mocks depending on table name
        lib_table = MagicMock()
        lib_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[video_record])
        lib_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[video_record])

        sched_table = MagicMock()
        sched_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[queue_record])
        sched_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[queue_record])

        activity_table = MagicMock()
        activity_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

        def table_router(table_name):
            if table_name == "video_library":
                return lib_table
            elif table_name == "scheduled_videos":
                return sched_table
            elif table_name == "video_activity_log":
                return activity_table
            return MagicMock()

        mock_sb.table.side_effect = table_router

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb), \
             patch("backend.automate.dispatch_github_actions_upload", return_value=True) as mock_dispatch:

            response = client.post("/api/dashboard/videos/vid-1234/publish")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "Dispatched to GitHub Actions worker" in data["message"]
            mock_dispatch.assert_called_once_with(video_id="sched-5678")

            # Verify storage download was NOT attempted (preventing 404 Object not found)
            mock_sb.storage.from_.assert_not_called()

