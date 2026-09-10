# ReelsMob Supabase Layer Audit & Hardening Report

**Branch:** `db/supabase-audit`  
**Date:** September 2026  
**Scope:** Supabase database schema, connectivity, indexing, query correctness, data integrity, storage security, and background worker jobs (`cloud/`).

---

## Executive Summary

This diagnostic and hardening audit targeted the ReelsMob cloud database and storage infrastructure. No table meanings, schemas, or posting intelligence logic were altered. All database enhancements are encapsulated within a backward-compatible migration: [`cloud/004_supabase_hardening.sql`](file:///c:/Users/bhuma/.gemini/antigravity/scratch/reelsmob/cloud/004_supabase_hardening.sql).

All 64 unit and integration tests across the backend and cloud modules pass cleanly.

---

## 1. Connectivity & Environment Configuration

### Findings:
- **Client Instantiation Overhead:** Prior to this audit, every call to `get_supabase_client()` instantiated a new Supabase client and underlying HTTP transport without connection pooling, risking socket exhaustion under rapid polling or batch operations.
- **Environment Inconsistency:** `cloud/cloud_auth.py` did not consistently load from both the project root `.env` and `cloud/.env`.
- **Missing Fail-Fast Validation:** Incomplete or malformed URLs (missing `https://` protocol) or missing API keys would fail deep inside HTTP request parsing rather than presenting actionable configuration error messages.

### Hardening Applied:
- **Singleton Client Caching:** In [`cloud/cloud_auth.py`](file:///c:/Users/bhuma/.gemini/antigravity/scratch/reelsmob/cloud/cloud_auth.py), implemented global client caching (`_SUPABASE_CLIENT`) with optional `force_refresh=True` parameter. Reuses transport pools across calls.
- **Fail-Fast Configuration Validation:** Added `validate_supabase_config(fail_fast: bool = False)` function. Validates URL protocol (`http://` or `https://`) and checks JWT service key length before attempting connection.
- **Dual `.env` Resolution:** Added robust multi-directory `.env` detection (root `.env` + `cloud/.env`) wrapped in non-blocking try/except.
- **GitHub Actions Workflows:** Updated `.github/workflows/upload_poller.yml` and `cleanup_job.yml` to ensure `python-dotenv` is available.

---

## 2. Schema Integrity & Foreign Key Indexes

### Findings:
- **Foreign Key Indexing Gap:** PostgreSQL enforces referential integrity constraints via foreign keys (`REFERENCES video_library(id)`), but does **NOT** automatically index foreign key columns.
  - `scheduled_videos.library_video_id` had no index.
  - `video_activity_log.video_id` had no index.
  - **Impact:** Any cascade delete, join query, or filter by video ID performed sequential table scans across the entire table.
- **Sorting & Filtering Gaps:** Dashboard endpoints (`/api/dashboard/stats`, `/api/dashboard/videos`, `/api/dashboard/logs`) query `video_library` and `video_activity_log` sorted by `created_at DESC` or filtered by `status`. Without indexes, performance degrades as rows accumulate.

### Hardening Applied (in `004_supabase_hardening.sql`):
- `idx_video_library_status`: B-tree index on `video_library(status)`.
- `idx_video_library_created_at_desc`: B-tree index on `video_library(created_at DESC)`.
- `idx_video_library_schedule_time`: Partial index on `video_library(schedule_time) WHERE schedule_time IS NOT NULL`.
- `idx_scheduled_videos_library_id`: Partial foreign key index on `scheduled_videos(library_video_id) WHERE library_video_id IS NOT NULL`.
- `idx_video_activity_log_video_id`: B-tree foreign key index on `video_activity_log(video_id)`.
- `idx_video_activity_log_created_at_desc`: B-tree index on `video_activity_log(created_at DESC)`.

---

## 3. Query Correctness & Bounding

### Findings:
- **Unbounded Queries in Workers:**
  - `workflow_upload.py` queried all `scheduled_videos` where `upload_status == 'pending'` without a batch limit or explicit ordering. If a backlog occurred, the poller would pull all rows into memory and risk timeout or YouTube quota exhaustion in a single run.
  - `workflow_cleanup.py` queried `scheduled_videos` eligible for deletion without limits or ordering.
- **Transient Retry Visibility:**
  - In `workflow_upload.py`, temporary upload failures incremented retry count but did not record `YOUTUBE_UPLOAD_RETRY` events in `video_activity_log`, leaving operators blind to intermittent network hiccups until final failure.

### Hardening Applied:
- **Query Bounding & FIFO Ordering:**
  - Added `.order("schedule_time", desc=False).limit(25)` to `workflow_upload.py` pending queries.
  - Added `.order("delete_after", desc=False).limit(50)` to `workflow_cleanup.py`.
- **Transient Activity Tracking:** Added `YOUTUBE_UPLOAD_RETRY` event logging to `video_activity_log` when an upload attempt fails prior to reaching max retries.

---

## 4. Data Integrity & Deduplication

### Findings:
- **Orphaned Storage & Partial Writes in Enqueue:**
  - In `cloud/enqueue.py`, if queue insertion into `scheduled_videos` failed after uploading the binary to Supabase Storage, the uploaded video remained in the storage bucket as an orphaned file consuming quota.
- **Duplicate Pending Queue Entries:**
  - Nothing stopped multiple concurrent calls from queuing the same library video repeatedly for upload.
- **Cleanup Timestamp Constraint Failure:**
  - `videos_audit_log` defined `uploaded_at TIMESTAMPTZ NOT NULL`. If an enqueued video was canceled or purged before `uploaded_at` was set, `workflow_cleanup.py` would crash during audit logging.

### Hardening Applied:
- **Enqueue Multi-Phase Rollback:** In `cloud/enqueue.py`, wrapped `scheduled_videos.insert()` in a dedicated rollback handler that immediately deletes the uploaded storage object from `reelgrab-videos` and removes the `video_library` row if insertion fails.
- **Deduplication Partial Unique Index:** Added `idx_sv_unique_pending_library_video` on `scheduled_videos(library_video_id) WHERE upload_status = 'pending'`, preventing duplicate pending jobs for the same video.
- **Relaxed Audit Constraint:** In `004_supabase_hardening.sql`, modified `videos_audit_log.uploaded_at` to `DROP NOT NULL` with default `now()`. In `workflow_cleanup.py`, added safe fallback timestamps.

---

## 5. Security: Row Level Security (RLS) & Storage

### Findings:
- **RLS Disabled:** None of the initial migrations (`001_initial_schema.sql`, `002_library_and_logging.sql`, `003_posting_intelligence.sql`) enabled PostgreSQL Row Level Security (RLS). While the client application accesses the database via FastAPI using the backend `SUPABASE_SERVICE_KEY`, leaving RLS disabled meant that any exposure of the public `anon` key would allow unrestricted public reads/writes to creator video data.
- **Credential Storage Security:** Confirmed that frontend client bundles contain zero Supabase keys or direct Supabase client initialization. All access is strictly routed through authenticated FastAPI endpoints.

### Hardening Applied:
- **Row Level Security Enabled:** In `004_supabase_hardening.sql`, executed `ENABLE ROW LEVEL SECURITY` across all 8 tables:
  1. `scheduled_videos`
  2. `video_library`
  3. `video_activity_log`
  4. `videos_audit_log`
  5. `ai_analysis_jobs`
  6. `analytics_snapshots`
  7. `historical_shorts_data`
  8. `posting_slot_scores`
- Because the backend and GitHub Actions workers authenticate using `SUPABASE_SERVICE_KEY` (`service_role` role), they automatically bypass RLS and retain full operational access, while anonymous public HTTP access via Supabase PostgREST is blocked by default.

---

## 6. Verification & Test Coverage

New test suite added: [`backend/tests/test_supabase_audit.py`](file:///c:/Users/bhuma/.gemini/antigravity/scratch/reelsmob/backend/tests/test_supabase_audit.py).

```
============================= 64 passed in 4.01s ==============================
backend/tests/test_supabase_audit.py:
  - TestSupabaseConfigValidation::test_missing_config_fails PASSED
  - TestSupabaseConfigValidation::test_missing_config_fail_fast_raises PASSED
  - TestSupabaseConfigValidation::test_malformed_url_rejected PASSED
  - TestSupabaseConfigValidation::test_short_service_key_rejected PASSED
  - TestSupabaseConfigValidation::test_valid_config_passes PASSED
  - TestSupabaseClientCaching::test_client_singleton_cached PASSED
  - TestMigration004Integrity::test_migration_file_exists_and_contains_critical_indexes PASSED
```
All existing tests (`test_api_mocked.py`, `test_logging.py`, `test_retry.py`, `test_validation.py`) continue to pass without regressions.
