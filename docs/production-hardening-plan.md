# ReelMob Production Hardening & Bug-Fix Master Plan

**Date:** September 2026  
**Repository:** [https://github.com/Bhuma005/ReelMob](https://github.com/Bhuma005/ReelMob)  
**Strategy:** Phased, zero-downtime, fully verified production hardening.

---

## Phase Roadmap Overview

- **PHASE 1: Database Correctness & Schema Alignment**
- **PHASE 2: AI & Deterministic Scheduling Correctness**
- **PHASE 3: Durable Job Subsystem Architecture**
- **PHASE 4: Upload Reliability & Atomic Claiming**
- **PHASE 5: Cleanup Reliability & Library Permanence**
- **PHASE 6: Security Hardening (OAuth, Tokens, Proxies)**
- **PHASE 7: Performance & Search Scalability**
- **PHASE 8: Automated Testing Suite Expansion**
- **PHASE 9: Docker & CI/CD Reproducibility**
- **PHASE 10: Final Production Verification & Rules**

---

## Detailed Phase Specifications

### PHASE 1: Database Correctness & Schema Alignment
- **Objective**: Establish authoritative database schema, migrations, constraints, and legal state transitions. Enforce Library record permanence.
- **Files to Modify**:
  - `cloud/004_supabase_hardening.sql` (reference)
  - `backend/schemas.py`
  - `backend/main.py`
- **Files to Create**:
  - `cloud/008_production_hardening.sql`: Add `jobs` table, atomic claim columns (`claimed_at`, `lease_expires_at`, `worker_id`) to `scheduled_videos`, state check constraints, and search indexes.
- **Database Changes**:
  - Add `claimed_at TIMESTAMPTZ`, `lease_expires_at TIMESTAMPTZ`, `worker_id TEXT` to `scheduled_videos`.
  - Update `upload_status` check constraint: `CHECK (upload_status IN ('pending', 'claimed', 'uploading', 'uploaded', 'failed', 'cancelled'))`.
  - Update `video_library.status` check constraint: `CHECK (status IN ('created', 'downloading', 'downloaded', 'processing', 'ready', 'scheduled', 'uploading', 'published', 'delete_pending', 'cleaned', 'failed'))`.
  - Create `jobs` table for all asynchronous background jobs (AI analysis, highlights, moderation).
- **API Changes**: None (internal contract preservation).
- **Rollback Considerations**: All migration statements use `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` to maintain 100% backward compatibility.
- **Verification Commands**: `python -m pytest backend/tests/test_supabase_audit.py`

---

### PHASE 2: AI & Scheduling Correctness
- **Objective**: Strip all hardcoded `"07:30 PM"` / `"Peak evening engagement"` defaults. Remove `random.uniform()` from `posting_engine.py` and fake synthetic records from `analytics_trends.py`. Establish backend deterministic scheduler returning explicit `insufficient_data` states when data is missing.
- **Files to Modify**:
  - `backend/posting_engine.py`
  - `backend/services/analysis_service.py`
  - `backend/services/analytics_trends.py`
  - `backend/automate.py`
  - `backend/main.py`
  - `backend/agents/master_agent.py`
  - `backend/agents/posting_agent.py`
  - `backend/scripts/run_analysis_job.py`
  - `frontend-react/src/pages/CreateReelPage.jsx`
  - `frontend-react/src/pages/SchedulerPage.jsx`
- **Files to Create**:
  - `backend/services/scheduler.py`: Pure deterministic scheduler calculating peak posting windows from historical video performance or returning `insufficient_data`.
- **Frontend Changes**:
  - Display "Not enough channel data to recommend a posting time" when status is `insufficient_data`.
  - Clearly label content assessment as "AI Content Score" (e.g. 85/100) instead of fake viral probabilities.
- **Verification Commands**: `python -m pytest backend/tests/test_ai_fallback_diagnostics.py backend/tests/test_analytics_trends.py`

---

### PHASE 3: Durable Job Subsystem Architecture
- **Objective**: Replace volatile in-memory job dictionaries (`AI_JOBS_STORE`, `HIGHLIGHT_JOBS`, `MODERATION_JOBS`) with durable database-backed storage using the `jobs` table so jobs survive server restarts and multi-worker deployments.
- **Files to Modify**:
  - `backend/main.py`
  - `backend/services/highlight_detector.py`
  - `backend/services/content_moderation.py`
  - `backend/video_analyzer.py`
- **Files to Create**:
  - `backend/services/job_store.py`: Durable job repository handling job creation, atomic step updates, completion, failure, and recovery.
- **API Changes**:
  - `/api/video/highlights`, `/api/video/moderation-check`, `/metadata/analyze` query durable database records with backward-compatible response schemas.
- **Verification Commands**: `python -m pytest backend/tests/test_highlights.py backend/tests/test_moderation.py`

---

### PHASE 4: Upload Reliability & Atomic Claiming
- **Objective**: Fix race condition in `cloud/workflow_upload.py`. Implement atomic claiming with worker leasing (`claimed_at`, `lease_expires_at`, `worker_id`) and prevent duplicate YouTube uploads via pre-upload idempotency checks.
- **Files to Modify**:
  - `cloud/workflow_upload.py`
  - `cloud/enqueue.py`
- **Logic**:
  - Atomic claim: Atomically mark batch rows from `pending` -> `claimed` with worker ID and 15-minute lease expiry.
  - Recovery: Reclaim rows where `upload_status = 'claimed'` and `lease_expires_at < NOW()`.
  - Idempotency: Before upload, verify if `video_library.youtube_video_id` is already populated.
- **Verification Commands**: `python -m pytest backend/tests/test_retry.py`

---

### PHASE 5: Cleanup Reliability & Library Permanence
- **Objective**: Ensure physical storage deletion in `cloud/workflow_cleanup.py` and manual deletion in `backend/main.py` NEVER delete permanent `video_library` records. Make cleanup operations restart-safe and idempotent.
- **Files to Modify**:
  - `cloud/workflow_cleanup.py`
  - `backend/main.py` (line 1200+ `delete_dashboard_video`)
  - `frontend-react/src/pages/LibraryPage.jsx`
- **Frontend Behavior**:
  - Cleaned videos with `status = 'cleaned'` display "Published (Cloud copy cleaned)" and retain open-on-YouTube actions rather than showing "Video missing".
- **Verification Commands**: `python -m pytest backend/tests/test_on_demand_download.py`

---

### PHASE 6: Security Hardening
- **Objective**: Restrict YouTube OAuth redirect URIs to strict allowlist (`ALLOWED_OAUTH_REDIRECT_URIS`). Prevent token leakage across API responses, error logs, and frontend state.
- **Files to Modify**:
  - `backend/youtube_auth.py`
  - `backend/config.py`
  - `backend/security_headers.py`
- **Files to Create**:
  - `backend/services/token_encryption.py` (if secret encryption key provided, or secure token scrubbing utilities).
- **Verification Commands**: `python -m pytest backend/tests/test_youtube_token_persistence.py backend/tests/test_security_headers.py`

---

### PHASE 7: Performance & Search Scalability
- **Objective**: Move `/api/dashboard/search` to database-backed PostgreSQL queries with pagination. Implement cursor/offset pagination for library and logs. Incrementally extract routers from `backend/main.py` to `backend/api/`.
- **Files to Modify**:
  - `backend/main.py`
  - `backend/services/analytics_export.py`
- **Files to Create**:
  - `backend/api/videos.py`
  - `backend/api/dashboard.py`
  - `backend/api/scheduling.py`
- **Verification Commands**: `python -m pytest backend/tests/test_search.py`

---

### PHASE 8: Automated Testing Suite Expansion
- **Objective**: Add comprehensive unit and integration tests covering deterministic scheduling, durable job recovery, atomic claim race prevention, OAuth redirect validation, and library permanence.
- **Files to Create/Modify**:
  - `backend/tests/test_deterministic_scheduler.py`
  - `backend/tests/test_durable_jobs.py`
  - `backend/tests/test_atomic_claim.py`
  - `backend/tests/test_oauth_security.py`
- **Verification Commands**: `python -m pytest backend/tests/`

---

### PHASE 9: Docker & CI/CD Reproducibility
- **Objective**: Upgrade `Dockerfile` with `npm ci` and pinned dependencies. Update `.github/workflows/ci.yml` to remove error-masking fallback operators and add Docker build validation.
- **Files to Modify**:
  - `Dockerfile`
  - `backend/requirements.txt`
  - `.github/workflows/ci.yml`
- **Verification Commands**: `npm --prefix frontend-react run build`

---

### PHASE 10: Final Production Verification & Rules
- **Objective**: Run full test suites, verify API contracts, check zero secret leakage, remove `db.json` legacy fixture from root, and create `.agents/rules/reelmob_production_rules.md` and `docs/production-hardening-report.md`.
- **Files to Create**:
  - `.agents/rules/reelmob_production_rules.md`
  - `AGENTS.md`
  - `docs/production-hardening-report.md`
  - `docs/deployment.md`
