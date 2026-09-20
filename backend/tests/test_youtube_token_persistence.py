"""
test_youtube_token_persistence.py — Tests for Supabase-backed YouTube OAuth Token Persistence.
Verifies migration 007, credential saving/upserting, credential loading, unreachability resilience,
and /auth/status /auth/logout API routes.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app, RATE_LIMIT_STORE
from backend.youtube_auth import (
    _save_credentials,
    _load_credentials,
    _get_supabase_client,
)


@pytest.fixture
def client():
    RATE_LIMIT_STORE.clear()
    with TestClient(app) as c:
        yield c


def test_migration_007_exists():
    """Verify migration 007 file exists and configures oauth_tokens with RLS."""
    mig_path = os.path.join("cloud", "007_add_oauth_tokens.sql")
    assert os.path.exists(mig_path), "Migration 007_add_oauth_tokens.sql must exist"
    with open(mig_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "CREATE TABLE IF NOT EXISTS oauth_tokens" in content
    assert "provider TEXT NOT NULL UNIQUE" in content
    assert "access_token TEXT NOT NULL" in content
    assert "refresh_token TEXT" in content
    assert "ROW LEVEL SECURITY" in content
    assert "idx_oauth_tokens_provider" in content


class TestYouTubeTokenPersistence:
    """Tests for Supabase-backed _save_credentials and _load_credentials."""

    def test_save_credentials_upserts_to_supabase(self):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        sample_tokens = {
            "access_token": "ya29.sample_access_token",
            "refresh_token": "1//sample_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/youtube.upload",
            "channel_name": "Test Creator Channel"
        }

        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_client):
            _save_credentials(sample_tokens)

        mock_client.table.assert_called_with("oauth_tokens")
        mock_table.upsert.assert_called_once()
        upsert_args, upsert_kwargs = mock_table.upsert.call_args
        record = upsert_args[0]

        assert record["provider"] == "youtube"
        assert record["access_token"] == "ya29.sample_access_token"
        assert record["refresh_token"] == "1//sample_refresh_token"
        assert record["token_type"] == "Bearer"
        assert record["channel_name"] == "Test Creator Channel"
        assert record["expires_at"] is not None
        assert upsert_kwargs.get("on_conflict") == "provider"

    def test_save_credentials_preserves_existing_refresh_token(self):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value.execute.return_value = MagicMock(data=[{"id": 1}])

        existing_creds = {
            "access_token": "old_token",
            "refresh_token": "existing_valid_refresh_token_123"
        }

        new_tokens_without_refresh = {
            "access_token": "ya29.new_fresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "channel_name": "Test Channel"
        }

        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_client):
            with patch("backend.youtube_auth._load_credentials", return_value=existing_creds):
                _save_credentials(new_tokens_without_refresh)

        upsert_args, _ = mock_table.upsert.call_args
        record = upsert_args[0]
        assert record["refresh_token"] == "existing_valid_refresh_token_123"
        assert record["access_token"] == "ya29.new_fresh_token"

    def test_save_credentials_handles_unreachable_supabase_gracefully(self):
        with patch("backend.youtube_auth._get_supabase_client", return_value=None):
            # Should not raise exception
            _save_credentials({"access_token": "test"})

        mock_failing_client = MagicMock()
        mock_failing_client.table.side_effect = ConnectionError("Supabase connection timeout")
        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_failing_client):
            # Should catch and log error gracefully
            _save_credentials({"access_token": "test"})

    def test_load_credentials_returns_row_when_found(self):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq

        mock_response = MagicMock()
        mock_response.data = [{
            "id": 1,
            "provider": "youtube",
            "access_token": "ya29.stored_token",
            "refresh_token": "1//stored_refresh",
            "token_type": "Bearer",
            "expires_at": "2026-10-01T12:00:00Z",
            "channel_name": "ReelsMob Official",
            "scope": "https://www.googleapis.com/auth/youtube.upload",
            "updated_at": "2026-09-20T12:00:00Z"
        }]
        mock_eq.execute.return_value = mock_response

        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_client):
            creds = _load_credentials()

        assert creds is not None
        assert creds["provider"] == "youtube"
        assert creds["access_token"] == "ya29.stored_token"
        assert creds["refresh_token"] == "1//stored_refresh"
        assert creds["channel_name"] == "ReelsMob Official"

    def test_load_credentials_returns_none_when_no_row_exists(self):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq

        mock_response = MagicMock()
        mock_response.data = []  # Empty table
        mock_eq.execute.return_value = mock_response

        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_client):
            creds = _load_credentials()

        assert creds is None

    def test_load_credentials_handles_unreachable_supabase_gracefully(self):
        with patch("backend.youtube_auth._get_supabase_client", return_value=None):
            assert _load_credentials() is None

        mock_failing_client = MagicMock()
        mock_failing_client.table.side_effect = ConnectionError("Supabase connection refused")
        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_failing_client):
            assert _load_credentials() is None


class TestYouTubeAuthEndpointsWithSupabase:
    """Test /auth/status and /auth/logout routes using Supabase backend."""

    def test_auth_status_authenticated_via_supabase(self, client):
        mock_creds = {
            "provider": "youtube",
            "access_token": "ya29.valid_token",
            "refresh_token": "1//valid_refresh",
            "channel_name": "Viral Clips Studio"
        }

        with patch("backend.youtube_auth._load_credentials", return_value=mock_creds):
            with patch("backend.youtube_auth._load_secrets", return_value={"client_id": "test", "client_secret": "test"}):
                res = client.get("/auth/status")
                assert res.status_code == 200
                data = res.json()
                assert data["is_authenticated"] is True
                assert data["channel_name"] == "Viral Clips Studio"
                assert data["has_client_secrets"] is True

    def test_auth_status_unauthenticated_when_no_token_in_supabase(self, client):
        with patch("backend.youtube_auth._load_credentials", return_value=None):
            with patch("backend.youtube_auth._load_secrets", return_value=None):
                res = client.get("/auth/status")
                assert res.status_code == 200
                data = res.json()
                assert data["is_authenticated"] is False
                assert data["channel_name"] is None
                assert data["has_client_secrets"] is False

    def test_auth_logout_deletes_token_from_supabase(self, client):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_delete = MagicMock()
        mock_table.delete.return_value = mock_delete
        mock_eq = MagicMock()
        mock_delete.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        with patch("backend.youtube_auth._get_supabase_client", return_value=mock_client):
            res = client.get("/auth/logout")
            assert res.status_code == 200
            assert res.json() == {"status": "logged_out"}

            mock_client.table.assert_called_with("oauth_tokens")
            mock_table.delete.assert_called_once()
            mock_delete.eq.assert_called_once_with("provider", "youtube")
