"""
test_github_actions_offload.py — Unit and integration tests for GitHub Actions Video Analysis Offloading.

Tests:
1. Offload config validation (fails fast if GITHUB_DISPATCH_TOKEN missing in github_actions mode)
2. GitHub repository_dispatch HTTP call (payload shape, headers, response handling)
3. API endpoint /api/analyze routing to GitHub Actions vs local mode
4. API endpoint /api/analyze/status/{job_id} reading results from Supabase
5. Headless runner script payload parsing and execution
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app, RATE_LIMIT_STORE, AI_JOBS_STORE, dispatch_github_actions_analysis
from backend.config import validate_offload_config, validate_config
from backend.scripts.run_analysis_job import parse_job_payload, update_supabase_job


@pytest.fixture
def client():
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


class TestOffloadConfigValidation:
    """Tests for fail-fast configuration checks."""

    def test_local_mode_passes_without_token(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_OFFLOAD_MODE", "local")
        monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
        # Should not raise
        validate_offload_config()
        status = validate_config(fail_fast=True)
        assert status["analysis_offload_mode"] == "local"
        assert status["github_dispatch_configured"] is False

    def test_github_actions_mode_fails_without_token(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_OFFLOAD_MODE", "github_actions")
        monkeypatch.delenv("GITHUB_DISPATCH_TOKEN", raising=False)
        with pytest.raises(EnvironmentError) as exc_info:
            validate_offload_config()
        assert "GITHUB_DISPATCH_TOKEN is missing" in str(exc_info.value)

    def test_github_actions_mode_passes_with_token(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_OFFLOAD_MODE", "github_actions")
        monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "ghp_valid_mock_token_123")
        validate_offload_config()
        status = validate_config(fail_fast=True)
        assert status["analysis_offload_mode"] == "github_actions"
        assert status["github_dispatch_configured"] is True


class TestGitHubRepositoryDispatch:
    """Tests for triggering repository_dispatch event."""

    def test_dispatch_success(self, monkeypatch):
        monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "mock_pat_token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "Bhuma005/ReelMob")

        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            success = dispatch_github_actions_analysis(
                job_id="test-job-uuid-1234",
                video_url="https://youtube.com/shorts/sample123",
                title="Sample Video",
                description="Sample Description",
                content_hash="abc123hash"
            )
            assert success is True

            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            assert "https://api.github.com/repos/Bhuma005/ReelMob/dispatches" in req.full_url
            assert req.get_header("Authorization") == "Bearer mock_pat_token"
            assert req.get_header("Accept") == "application/vnd.github+json"

            body = json.loads(req.data.decode("utf-8"))
            assert body["event_type"] == "analyze-video"
            assert body["client_payload"]["job_id"] == "test-job-uuid-1234"
            assert body["client_payload"]["video_url"] == "https://youtube.com/shorts/sample123"

    def test_dispatch_raises_on_http_error(self, monkeypatch):
        import urllib.error
        monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "invalid_token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "Bhuma005/ReelMob")

        err = urllib.error.HTTPError(
            url="https://api.github.com",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Bad credentials"}')
        )

        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError) as exc_info:
                dispatch_github_actions_analysis("job-1", "https://video.url", "Title", "Desc")
            assert "401" in str(exc_info.value)


class TestAPIAnalyzeOffloadRouting:
    """Tests for API endpoint dispatching to GitHub Actions vs local background task."""

    def test_analyze_endpoint_local_mode(self, client, monkeypatch):
        monkeypatch.setenv("ANALYSIS_OFFLOAD_MODE", "local")

        with patch("backend.main.execute_ai_analysis_job") as mock_local_exec:
            res = client.post("/api/analyze", json={
                "url": "https://youtube.com/shorts/dance999",
                "title": "Subway Dance",
                "description": "Fun subway video"
            })
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "QUEUED"
            assert data["processed_by"] == "local"
            assert data["job_id"].startswith("ai_")

    def test_analyze_endpoint_github_actions_mode(self, client, monkeypatch):
        monkeypatch.setenv("ANALYSIS_OFFLOAD_MODE", "github_actions")
        monkeypatch.setenv("GITHUB_DISPATCH_TOKEN", "mock_valid_token")

        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
            with patch("backend.main.dispatch_github_actions_analysis", return_value=True) as mock_dispatch:
                res = client.post("/api/analyze", json={
                    "url": "https://youtube.com/shorts/cooking888",
                    "title": "Cooking Magic",
                    "description": "Chef cooking fast"
                })
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "QUEUED"
                assert data["processed_by"] == "github_actions"
                assert "GitHub Actions" in data["current_step"]
                mock_dispatch.assert_called_once()


class TestAPIStatusSupabaseIntegration:
    """Tests for /api/analyze/status/{job_id} reading from Supabase table."""

    def test_status_reads_supabase_completed_job(self, client):
        test_job_id = "test-gha-job-uuid-9999"

        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq

        mock_eq.execute.return_value = MagicMock(data=[{
            "id": test_job_id,
            "status": "COMPLETED",
            "progress": 100,
            "current_step": "AI optimization complete (GitHub Actions)",
            "result": {
                "viral_title": "He Thought Nobody Was Watching \U0001f631",
                "optimized_description": "Incredible scene from the streets.",
                "youtube": ["#Shorts", "#Viral"],
                "instagram": ["#Reels"],
                "processed_by": "github_actions"
            },
            "error_message": None
        }])

        with patch("cloud.cloud_auth.get_supabase_client", return_value=mock_sb):
            res = client.get(f"/api/analyze/status/{test_job_id}")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "COMPLETED"
            assert data["progress"] == 100
            assert data["processed_by"] == "github_actions"
            assert data["result"]["viral_title"] == "He Thought Nobody Was Watching \U0001f631"


class TestHeadlessRunnerScript:
    """Tests for backend/scripts/run_analysis_job.py."""

    def test_parse_job_payload_from_env(self, monkeypatch):
        payload_dict = {
            "job_id": "job-runner-123",
            "video_url": "https://youtube.com/shorts/test",
            "title": "Title",
            "description": "Desc"
        }
        monkeypatch.setenv("JOB_PAYLOAD", json.dumps(payload_dict))
        parsed = parse_job_payload()
        assert parsed["job_id"] == "job-runner-123"
        assert parsed["video_url"] == "https://youtube.com/shorts/test"

    def test_update_supabase_job_helper(self):
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_eq = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{"id": 1}])

        update_supabase_job(mock_sb, "job-123", {"status": "ANALYZING"})
        mock_table.update.assert_called_once_with({"status": "ANALYZING"})
        mock_update.eq.assert_called_once_with("id", "job-123")
