"""
job_store.py — Durable PostgreSQL + In-Memory Caching Job Store for ReelMob.
Replaces volatile in-memory job dictionaries with a durable storage layer backed by Supabase `jobs` table,
while preserving high-speed in-memory reads and 100% backward-compatible dictionary semantics.
"""

import logging
from collections.abc import MutableMapping
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Iterator

logger = logging.getLogger("reelsmob.job_store")


class TrackedJob(dict):
    """A dictionary wrapper that notifies the parent JobStore when keys are modified."""

    def __init__(self, store: "JobStore", job_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._store = store
        self._job_id = job_id

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if hasattr(self, "_store") and self._store:
            self._store._on_job_modified(self._job_id, self)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if hasattr(self, "_store") and self._store:
            self._store._on_job_modified(self._job_id, self)


class JobStore(MutableMapping):
    """
    Durable, dictionary-compatible job store.
    Features:
    - Microsecond in-memory reads/writes for fast polling
    - Read-through from Supabase `jobs` table when key is missing from memory (survives app restarts)
    - Write-through / upsert to Supabase `jobs` table on status/progress transitions
    - Full collections.abc.MutableMapping compliance (drop-in replacement for raw Dict)
    """

    def __init__(self, default_type: str = "generic"):
        self.default_type = default_type
        self._memory: Dict[str, TrackedJob] = {}

    def _get_supabase_client(self):
        try:
            from cloud.cloud_auth import get_supabase_client
            return get_supabase_client()
        except Exception as e:
            logger.debug(f"Could not initialize Supabase client for job store: {e}")
            return None

    def _sync_to_database(self, job_id: str, job_data: Dict[str, Any]):
        """Persists job state to PostgreSQL `jobs` table."""
        sb = self._get_supabase_client()
        if not sb:
            return

        try:
            status_val = str(job_data.get("status") or "queued").lower()
            # Map statuses
            valid_statuses = {"queued", "pending", "running", "processing", "completed", "failed", "cancelled"}
            if status_val not in valid_statuses:
                if status_val in ("in_progress", "active"):
                    status_val = "running"
                elif status_val in ("success", "done"):
                    status_val = "completed"
                elif status_val == "error":
                    status_val = "failed"
                else:
                    status_val = "running"

            progress_val = int(job_data.get("progress") or 0)
            step_val = str(job_data.get("current_step") or "")
            job_type_val = str(job_data.get("job_type") or self.default_type)
            result_val = job_data.get("result") or {}
            if not isinstance(result_val, dict):
                result_val = {"data": result_val}

            payload_val = {
                k: v for k, v in job_data.items()
                if k not in ("result", "status", "progress", "current_step", "job_type", "error")
            }

            db_payload = {
                "id": str(job_id),
                "job_type": job_type_val,
                "status": status_val,
                "progress": progress_val,
                "current_step": step_val,
                "result_reference": result_val,
                "input_reference": payload_val,
                "error_message": str(job_data.get("error") or "") if job_data.get("error") else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if status_val == "completed":
                db_payload["completed_at"] = datetime.now(timezone.utc).isoformat()

            sb.table("jobs").upsert(db_payload).execute()
        except Exception as e:
            logger.debug(f"Non-blocking job persistence to Supabase skipped: {e}")

    def _fetch_from_database(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Attempts to restore job state from Supabase if absent from memory."""
        sb = self._get_supabase_client()
        if not sb:
            return None

        try:
            res = sb.table("jobs").select("*").eq("id", str(job_id)).limit(1).execute()
            if res and res.data:
                row = res.data[0]
                restored = {
                    "job_id": row.get("id"),
                    "status": str(row.get("status", "QUEUED")).upper(),
                    "progress": int(row.get("progress", 0)),
                    "current_step": row.get("current_step", ""),
                    "result": row.get("result_reference", {}),
                    "job_type": row.get("job_type", self.default_type),
                    "error": row.get("error_message"),
                    "created_at": row.get("created_at"),
                }
                # Merge input reference back into top level
                input_ref = row.get("input_reference") or {}
                if isinstance(input_ref, dict):
                    for k, v in input_ref.items():
                        if k not in restored:
                            restored[k] = v
                return restored
        except Exception as e:
            logger.debug(f"Could not restore job from database: {e}")
        return None

    def _on_job_modified(self, job_id: str, job_data: Dict[str, Any]):
        self._sync_to_database(job_id, job_data)

    def create_job(self, job_id: str, job_type: Optional[str] = None, initial_data: Optional[Dict[str, Any]] = None) -> TrackedJob:
        data = {
            "status": "QUEUED",
            "progress": 0,
            "current_step": "Job registered",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "job_type": job_type or self.default_type,
        }
        if initial_data:
            data.update(initial_data)

        tracked = TrackedJob(self, job_id, data)
        self._memory[job_id] = tracked
        self._sync_to_database(job_id, tracked)
        return tracked

    def get_job(self, job_id: str) -> Optional[TrackedJob]:
        return self.get(job_id)

    # ── MutableMapping implementation ──────────────────────────────────────────

    def __getitem__(self, key: str) -> TrackedJob:
        if key in self._memory:
            return self._memory[key]

        # Read-through from DB
        db_job = self._fetch_from_database(key)
        if db_job is not None:
            tracked = TrackedJob(self, key, db_job)
            self._memory[key] = tracked
            return tracked

        raise KeyError(key)

    def __setitem__(self, key: str, value: Any):
        if not isinstance(value, dict):
            value = {"value": value}
        if "job_type" not in value:
            value["job_type"] = self.default_type

        if len(self._memory) >= 500:
            self._memory.pop(next(iter(self._memory)), None)
        tracked = TrackedJob(self, key, value)
        self._memory[key] = tracked
        self._sync_to_database(key, tracked)

    def __delitem__(self, key: str):
        if key in self._memory:
            del self._memory[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._memory)

    def __len__(self) -> int:
        return len(self._memory)

    def __contains__(self, key: object) -> bool:
        if str(key) in self._memory:
            return True
        db_job = self._fetch_from_database(str(key))
        if db_job is not None:
            self._memory[str(key)] = TrackedJob(self, str(key), db_job)
            return True
        return False

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self):
        self._memory.clear()

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self:
            self[key] = default if default is not None else {}
        return self[key]
