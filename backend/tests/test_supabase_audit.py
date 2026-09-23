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


class TestMigration008Integrity:
    def test_migration_008_exists_and_contains_jobs_and_claims(self):
        root = Path(__file__).parent.parent.parent
        migration_file = root / "cloud" / "008_production_hardening.sql"
        assert migration_file.exists(), f"Migration file missing at {migration_file}"

        content = migration_file.read_text(encoding="utf-8")

        # 1. Jobs table creation
        assert "CREATE TABLE IF NOT EXISTS jobs" in content
        assert "job_type" in content
        assert "progress" in content
        assert "input_reference" in content
        assert "result_reference" in content

        # 2. Atomic claim columns on scheduled_videos
        assert "claimed_at TIMESTAMPTZ" in content
        assert "lease_expires_at TIMESTAMPTZ" in content
        assert "worker_id TEXT" in content

        # 3. Status checks
        assert "scheduled_videos_upload_status_check" in content
        assert "'claimed'" in content
        assert "'cancelled'" in content
        assert "video_library_status_check" in content
        assert "'cleaned'" in content

        # 4. RLS enabled on jobs
        assert "ALTER TABLE IF EXISTS jobs ENABLE ROW LEVEL SECURITY;" in content


class TestStateMachine:
    def test_legal_library_transitions(self):
        from backend.services.state_machine import (
            can_transition_library,
            transition_library_status,
            LibraryStatus,
        )

        # Legal: created -> ready -> scheduled -> uploading -> published -> cleaned
        assert can_transition_library(LibraryStatus.CREATED, LibraryStatus.READY)
        assert can_transition_library(LibraryStatus.READY, LibraryStatus.SCHEDULED)
        assert can_transition_library(LibraryStatus.SCHEDULED, LibraryStatus.UPLOADING)
        assert can_transition_library(LibraryStatus.UPLOADING, LibraryStatus.PUBLISHED)
        assert can_transition_library(LibraryStatus.PUBLISHED, LibraryStatus.CLEANED)

        # Illegal: published -> processing
        assert not can_transition_library(LibraryStatus.PUBLISHED, LibraryStatus.PROCESSING)
        with pytest.raises(ValueError, match="Illegal Library state transition"):
            transition_library_status(LibraryStatus.PUBLISHED, LibraryStatus.PROCESSING)

        # Illegal: cleaned is terminal
        assert not can_transition_library(LibraryStatus.CLEANED, LibraryStatus.UPLOADING)

    def test_legal_queue_transitions(self):
        from backend.services.state_machine import (
            can_transition_queue,
            transition_queue_status,
            QueueStatus,
        )

        # Legal: pending -> claimed -> uploading -> uploaded
        assert can_transition_queue(QueueStatus.PENDING, QueueStatus.CLAIMED)
        assert can_transition_queue(QueueStatus.CLAIMED, QueueStatus.UPLOADING)
        assert can_transition_queue(QueueStatus.UPLOADING, QueueStatus.UPLOADED)

        # Expired lease recovery: claimed -> pending
        assert can_transition_queue(QueueStatus.CLAIMED, QueueStatus.PENDING)

        # Illegal: uploaded -> pending
        assert not can_transition_queue(QueueStatus.UPLOADED, QueueStatus.PENDING)
        with pytest.raises(ValueError, match="Illegal Queue state transition"):
            transition_queue_status(QueueStatus.UPLOADED, QueueStatus.PENDING)

