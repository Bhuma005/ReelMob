"""
test_supabase_audit.py — Unit and integration tests for Supabase configuration,
client caching, schema migration integrity, and query bounding.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from cloud.cloud_auth import (
    validate_supabase_config,
    get_supabase_client,
    normalize_supabase_url,
    normalize_supabase_key,
)
import cloud.cloud_auth as cloud_auth_module


class TestSupabaseConfigValidation:
    def test_missing_config_fails(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

        res = validate_supabase_config(fail_fast=False)
        assert res["valid"] is False
        assert len(res["errors"]) >= 2
        assert any("SUPABASE_URL" in e for e in res["errors"])
        assert any("SUPABASE_SERVICE_KEY" in e for e in res["errors"])

    def test_missing_config_fail_fast_raises(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

        with pytest.raises(EnvironmentError) as exc_info:
            validate_supabase_config(fail_fast=True)
        assert "SUPABASE_URL" in str(exc_info.value)

    def test_malformed_url_rejected(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "not-a-valid-url.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummysecretkey1234567890")

        res = validate_supabase_config(fail_fast=False)
        assert res["valid"] is False
        assert any("malformed" in e for e in res["errors"])

    def test_short_service_key_rejected(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://xyz.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "short_key")

        res = validate_supabase_config(fail_fast=False)
        assert res["valid"] is False
        assert any("suspiciously short" in e for e in res["errors"])

    def test_valid_config_passes(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummysecretkey1234567890abcdef")

        res = validate_supabase_config(fail_fast=False)
        assert res["valid"] is True
        assert len(res["errors"]) == 0

    def test_url_normalization_with_rest_v1_and_trailing_slashes(self):
        # Prevents PostgREST PGRST125 path duplication
        assert normalize_supabase_url("https://xyz.supabase.co/rest/v1") == "https://xyz.supabase.co"
        assert normalize_supabase_url("https://xyz.supabase.co/rest/v1/") == "https://xyz.supabase.co"
        assert normalize_supabase_url("https://xyz.supabase.co/rest") == "https://xyz.supabase.co"
        assert normalize_supabase_url("https://xyz.supabase.co/") == "https://xyz.supabase.co"
        assert normalize_supabase_url("\"https://xyz.supabase.co/rest/v1\"") == "https://xyz.supabase.co"
        assert normalize_supabase_url("'https://xyz.supabase.co'") == "https://xyz.supabase.co"
        assert normalize_supabase_key("  'my-secret-key'  ") == "my-secret-key"


class TestSupabaseClientCaching:
    def test_client_singleton_cached(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummysecretkey1234567890abcdef")

        fake_client_1 = MagicMock(name="Client1")
        fake_client_2 = MagicMock(name="Client2")

        with patch("supabase.create_client", side_effect=[fake_client_1, fake_client_2]) as mock_create:
            # Clear any existing singleton
            cloud_auth_module._SUPABASE_CLIENT = None

            c1 = get_supabase_client()
            c2 = get_supabase_client()

            assert c1 is fake_client_1
            assert c2 is fake_client_1
            assert mock_create.call_count == 1

            # Force refresh
            c3 = get_supabase_client(force_refresh=True)
            assert c3 is fake_client_2
            assert mock_create.call_count == 2


class TestMigration004Integrity:
    def test_migration_file_exists_and_contains_critical_indexes(self):
        root = Path(__file__).parent.parent.parent
        migration_file = root / "cloud" / "004_supabase_hardening.sql"
        assert migration_file.exists(), f"Migration file missing at {migration_file}"

        content = migration_file.read_text(encoding="utf-8")

        # 1. Critical Indexes
        assert "idx_video_library_status" in content
        assert "idx_video_library_created_at_desc" in content
        assert "idx_video_library_schedule_time" in content
        assert "idx_scheduled_videos_library_id" in content
        assert "idx_video_activity_log_video_id" in content
        assert "idx_video_activity_log_created_at_desc" in content

        # 2. Data Integrity Partial Unique Index
        assert "idx_sv_unique_pending_library_video" in content
        assert "WHERE upload_status = 'pending'" in content

        # 3. videos_audit_log uploaded_at nullable fix
        assert "ALTER TABLE IF EXISTS videos_audit_log" in content
        assert "ALTER COLUMN uploaded_at DROP NOT NULL" in content

        # 4. RLS Enabled on all 8 tables
        expected_tables = [
            "scheduled_videos",
            "video_library",
            "video_activity_log",
            "videos_audit_log",
            "ai_analysis_jobs",
            "analytics_snapshots",
            "historical_shorts_data",
            "posting_slot_scores",
        ]
        for tbl in expected_tables:
            assert f"ALTER TABLE IF EXISTS {tbl} ENABLE ROW LEVEL SECURITY;" in content
