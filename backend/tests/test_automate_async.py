"""
test_automate_async.py — Test suite for asynchronous automation pipeline and JobStore tracking.
Verifies that POST /automate returns immediately (<1s) to prevent Render 100s proxy timeout,
and tracks progress durably via JobStore and GET /automate/status/{job_id}.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.automate import AUTOMATE_JOBS, _execute_automate_background_pipeline


@pytest.fixture
def client():
    return TestClient(app)


class TestAsyncAutomateEndpoint:
    """Tests verifying immediate HTTP return and background task dispatch."""

    def test_post_automate_returns_immediately_with_job_id(self, client):
        mock_sched = {
            "human_readable_time": "06:00 PM",
            "fallback_schedule": {"human_readable_time": "06:00 PM"}
        }

        with patch("backend.services.scheduler.calculate_deterministic_schedule", return_value=mock_sched), \
             patch("backend.automate._execute_automate_background_pipeline", new_callable=AsyncMock) as mock_worker:
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

            # Verify background worker was called with job_id
            mock_worker.assert_called_once()
            call_kwargs = mock_worker.call_args.kwargs
            assert call_kwargs["job_id"] == data["job_id"]
            assert call_kwargs["opt_title"] == "Epic Gaming Clip"

            # Verify job is tracked in AUTOMATE_JOBS
            job_id = data["job_id"]
            assert job_id in AUTOMATE_JOBS

    def test_get_automate_status_endpoint(self, client):
        job_id = "test_custom_job_123"
        AUTOMATE_JOBS[job_id] = {
            "status": "processing",
            "progress": 50,
            "current_step": "Applying 9:16 vertical layout...",
            "title": "Test Title",
        }

        res = client.get(f"/automate/status/{job_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processing"
        assert data["progress"] == 50
        assert data["current_step"] == "Applying 9:16 vertical layout..."

        # Non-existent job
        res_404 = client.get("/automate/status/non_existent_uuid")
        assert res_404.status_code == 404


@pytest.mark.asyncio
class TestAutomateBackgroundExecution:
    """Tests verifying the async background worker lifecycle."""

    async def test_background_pipeline_successful_run(self, tmp_path):
        job_id = "test_worker_job_success"
        AUTOMATE_JOBS[job_id] = {
            "status": "processing",
            "progress": 10,
            "current_step": "Initiated",
        }

        mock_temp_file = tmp_path / "mock_download.mp4"
        mock_temp_file.write_bytes(b"dummy_video_bytes")

        with patch("backend.automate.async_ensure_video_downloaded", new_callable=AsyncMock, return_value=str(mock_temp_file)), \
             patch("backend.automate.fit_to_canvas", return_value=str(mock_temp_file)), \
             patch("backend.automate.enqueue_video", return_value="queue_record_uuid_789"):

            await _execute_automate_background_pipeline(
                job_id=job_id,
                url="https://www.youtube.com/shorts/dQw4w9WgXcQ",
                format_id=None,
                thumbnail_url=None,
                opt_title="Test Title",
                opt_desc="Test Desc",
                opt_tags=["#test"],
                final_iso_schedule="2026-10-12T18:00:00+05:30",
            )

            job = AUTOMATE_JOBS[job_id]
            assert job["status"] == "completed"
            assert job["progress"] == 100
            assert job["result"]["queue_id"] == "queue_record_uuid_789"

    async def test_background_pipeline_error_handling(self):
        job_id = "test_worker_job_failure"
        AUTOMATE_JOBS[job_id] = {
            "status": "processing",
            "progress": 10,
            "current_step": "Initiated",
        }

        with patch("backend.automate.async_ensure_video_downloaded", new_callable=AsyncMock, side_effect=RuntimeError("Download network error")):
            await _execute_automate_background_pipeline(
                job_id=job_id,
                url="https://www.youtube.com/shorts/dQw4w9WgXcQ",
                format_id=None,
                thumbnail_url=None,
                opt_title="Test Title",
                opt_desc="Test Desc",
                opt_tags=["#test"],
                final_iso_schedule="2026-10-12T18:00:00+05:30",
            )

            job = AUTOMATE_JOBS[job_id]
            assert job["status"] == "failed"
            assert "Download network error" in job["error"]
