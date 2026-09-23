# ReelMob Production Engineering Rules & Invariants

These architectural rules govern all changes to ReelMob. Any future AI agent or developer modifying this repository MUST strictly follow these rules to preserve production stability, security, and algorithmic integrity.

---

## 1. Zero Synthetic Data Fabrication
- **Rule**: Never generate fake views, random likes, simulated follower engagement, or invented viral scores when database records are missing or sparse.
- **Requirement**: If historical data has fewer than 3–5 published videos, services must return explicit `status="insufficient_data"` or `status="ANALYTICS_UNAVAILABLE"` with empty trend lists and transparent explanation messages.
- **UI Policy**: Frontend must display "Not enough channel data to recommend an authoritative posting time / historical trend" rather than fabricating numbers.

---

## 2. Authoritative Deterministic Scheduling
- **Rule**: Never allow an LLM or non-deterministic random seed to determine authoritative YouTube posting windows.
- **Implementation**: All posting recommendations must pass through `backend/services/scheduler.py` (`calculate_deterministic_schedule()`).
- **Guarantee**: Given identical historical channel view distributions and reference times, the engine must return the exact same recommended publishing slot every time.

---

## 3. Library Permanence & Cloud Storage Soft-Deletion
- **Rule**: Never delete metadata rows from `video_library`.
- **Policy**:
  - Raw video files stored in Supabase Storage (`reelgrab-videos` bucket) may be purged to manage storage quotas (upon user deletion or after 3-day retention).
  - The corresponding `video_library` row must permanently transition to `status = 'cleaned'` with `storage_path = NULL` and `storage_deleted_at = now()`.
  - All channel analytics, titles, YouTube video IDs, view counts, and engagement telemetry must remain permanently queryable.

---

## 4. Atomic Worker Claiming & Distributed Leases
- **Rule**: Cloud workers (`cloud/workflow_upload.py`, GitHub Actions, or background runners) must never pull and process queue rows without an atomic lease claim.
- **Query Pattern**:
  Update `scheduled_videos` to `upload_status = 'claimed'`, `claimed_at = now()`, `lease_expires_at = now() + 15m`, and `worker_id = <unique_id>` where `upload_status IN ('pending', 'claimed')`.
- **Idempotency**: Before initiating any YouTube Data API upload, always verify whether `video_library` or `scheduled_videos` already contains a valid `youtube_video_id` for that reel. If present, skip re-uploading and mark as `uploaded`.

---

## 5. Durable PostgreSQL Job Store
- **Rule**: Asynchronous tasks (AI video analysis, highlight detection, content moderation) must persist state in PostgreSQL `jobs` table (`backend/services/job_store.py`).
- **Policy**: In-memory dictionaries (`AI_JOBS_STORE`, `HIGHLIGHT_JOBS`, `MODERATION_JOBS`) must use `JobStore` to ensure instant local memory access with read-through and write-through persistence to Supabase. Jobs must survive process restarts.

---

## 6. Strict OAuth Security & Redirect URI Allowlisting
- **Rule**: Never redirect OAuth flows to dynamic or unverified URIs passed in query parameters or untrusted Host headers.
- **Allowlist**:
  - `http://localhost:*`
  - `http://127.0.0.1:*`
  - `https://*.onrender.com`
  - `https://*.reelmob.app`
  - Configured entries in `ALLOWED_OAUTH_REDIRECT_URIS`
- **Credential Safety**: Access tokens and refresh tokens must never be logged to console in plain text or returned in client API payloads.

---

## 7. PostgreSQL Database Query Pushdown
- **Rule**: Avoid pulling entire tables into Python memory to perform linear scans or filtering.
- **Requirement**: Use database filters (`.eq()`, `.ilike()`, `.or_()`, `.range()`) with pagination limits to guarantee scalability across thousands of stored videos.

---

## 8. Reproducible Builds & Pinned Dependencies
- **Rule**: All Python packages in `backend/requirements.txt` must have pinned versions.
- **Docker & CI**: Node dependencies must be installed with `npm ci` (never unpinned `npm install` in Docker or CI workflows).
