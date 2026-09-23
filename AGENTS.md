# ReelMob Developer & AI Agent Operations Manual

This repository contains ReelMob, a production-grade automated short-form video optimization, intelligence, and publishing platform built with FastAPI, React, Supabase, and Google YouTube Data APIs.

---

## Architecture Overview

- **Backend**: FastAPI (`backend/main.py`), Modular services (`backend/services/`), State Machine (`backend/services/state_machine.py`), Deterministic Scheduler (`backend/services/scheduler.py`), Durable Job Store (`backend/services/job_store.py`).
- **Frontend**: React 18 with Vite, Tailwind CSS, Lucide icons, Vitest (`frontend-react/`).
- **Cloud & Automation**: Supabase PostgreSQL + Storage (`cloud/`), GitHub Actions workflows for scheduled publishing (`cloud/workflow_upload.py`), storage cleanup (`cloud/workflow_cleanup.py`), and headless analysis offloading (`backend/scripts/run_analysis_job.py`).

---

## Core Invariants for AI Agents

1. **State Machine Integrity**: Always check `backend/services/state_machine.py` before modifying video lifecycle statuses.
2. **Deterministic Intelligence**: Never generate synthetic statistics or let an LLM generate YouTube posting times. Use `backend/services/scheduler.py`.
3. **Library Metadata Permanence**: Never delete records from `video_library`. Use soft-deletion (`status = 'cleaned'`, `storage_path = NULL`).
4. **Atomic Worker Claiming**: When working with background upload queues, claim rows atomically using worker leases (`cloud/workflow_upload.py`).
5. **Durable Jobs**: Always use `JobStore` for asynchronous background jobs to guarantee persistence across restarts.

---

## Development & Test Commands

### Backend Tests
```bash
# Run entire backend test suite
pytest

# Run specific domain test suites
pytest backend/tests/test_deterministic_scheduler.py
pytest backend/tests/test_durable_jobs.py
pytest backend/tests/test_atomic_claim.py
pytest backend/tests/test_cleanup_permanence.py
pytest backend/tests/test_oauth_security.py
pytest backend/tests/test_supabase_audit.py
```

### Frontend Tests & Build
```bash
cd frontend-react
npm test
npm run build
```

### Docker Build Verification
```bash
docker build -t reelmob:production .
```

---

## Database Migrations

Migrations are stored in `cloud/*.sql` and must be applied in sequential order:
- `001_initial_schema.sql` through `007_youtube_oauth_tokens.sql`
- `008_production_hardening.sql`: Adds durable `jobs` table, atomic claim columns (`claimed_at`, `lease_expires_at`, `worker_id`) to `scheduled_videos`, state machine constraints, and search indexes.
