"""
test_stuck_jobs_reaper.py — Tests for cloud/workflow_reap_stuck_jobs.py.

Verifies that jobs stuck in active states past the timeout window are properly reaped,
and expired worker leases are restored.
"""

from unittest.mock import MagicMock, patch
from cloud.workflow_reap_stuck_jobs import (
    reap_stuck_ai_analysis_jobs,
    reap_stuck_durable_jobs,
    reap_expired_worker_leases,
    run_reaper
)


class TestStuckJobsReaper:
    def test_reap_stuck_ai_analysis_jobs(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table

        # Setup select query chain
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_lte = MagicMock()
        mock_in.lte.return_value = mock_lte

        # Return one stuck job
        mock_lte.execute.return_value = MagicMock(
            data=[{"id": "job-stuck-123", "status": "ANALYZING"}]
        )

        # Setup update query chain
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        count = reap_stuck_ai_analysis_jobs(mock_sb, timeout_minutes=15)
        assert count == 1

        # Verify update payload
        mock_table.update.assert_called_once()
        update_args = mock_table.update.call_args[0][0]
        assert update_args["status"] == "FAILED"
        assert update_args["current_step"] == "Job execution timed out"
        assert "timed out on runner after exceeding 15 minutes" in update_args["error_message"]
        mock_update.eq.assert_called_with("id", "job-stuck-123")

    def test_reap_stuck_durable_jobs(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_lte = MagicMock()
        mock_in.lte.return_value = mock_lte

        mock_lte.execute.return_value = MagicMock(
            data=[{"id": "durable-job-456", "status": "running", "job_type": "ai_analysis"}]
        )

        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        count = reap_stuck_durable_jobs(mock_sb, timeout_minutes=15)
        assert count == 1

        mock_table.update.assert_called_once()
        update_args = mock_table.update.call_args[0][0]
        assert update_args["status"] == "failed"
        assert "timed out after exceeding 15 minutes" in update_args["error_message"]
        mock_update.eq.assert_called_with("id", "durable-job-456")

    def test_reap_expired_worker_leases(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_in = MagicMock()
        mock_select.in_.return_value = mock_in
        mock_lte = MagicMock()
        mock_in.lte.return_value = mock_lte

        mock_lte.execute.return_value = MagicMock(
            data=[{"id": "vid-expired-789", "title": "Stale Video", "worker_id": "worker-1"}]
        )

        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        count = reap_expired_worker_leases(mock_sb)
        assert count == 1

        mock_table.update.assert_called_once()
        update_args = mock_table.update.call_args[0][0]
        assert update_args["upload_status"] == "pending"
        assert update_args["claimed_at"] is None
        assert update_args["worker_id"] is None
        assert update_args["lease_expires_at"] is None
        mock_update.eq.assert_called_with("id", "vid-expired-789")

    def test_run_reaper_aggregates_summary(self):
        with patch("cloud.workflow_reap_stuck_jobs.get_supabase_client") as mock_get_sb:
            mock_sb = MagicMock()
            mock_get_sb.return_value = mock_sb
            with patch("cloud.workflow_reap_stuck_jobs.reap_stuck_ai_analysis_jobs", return_value=2):
                with patch("cloud.workflow_reap_stuck_jobs.reap_stuck_durable_jobs", return_value=1):
                    with patch("cloud.workflow_reap_stuck_jobs.reap_expired_worker_leases", return_value=3):
                        res = run_reaper(timeout_minutes=15)
                        assert res["ai_analysis_jobs_reaped"] == 2
                        assert res["durable_jobs_reaped"] == 1
                        assert res["worker_leases_recovered"] == 3
