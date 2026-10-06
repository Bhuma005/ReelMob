"""
workflow_reap_stuck_jobs.py — Cloud worker script to detect and fail timed-out jobs in Supabase.

Finds jobs in `ai_analysis_jobs` (and durable `jobs`) stuck in active states
(QUEUED, ANALYZING, PROCESSING, etc.) for longer than the timeout window (default 15 minutes),
and marks them FAILED with an explanatory error message so the frontend doesn't poll indefinitely.
Also recovers expired worker leases in `scheduled_videos`.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from cloud.cloud_auth import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("reelsmob.stuck_job_reaper")

DEFAULT_TIMEOUT_MINUTES = int(os.getenv("STUCK_JOB_TIMEOUT_MINUTES", "15"))


def reap_stuck_ai_analysis_jobs(sb, timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> int:
    """Finds ai_analysis_jobs stuck in active states past timeout threshold and marks them FAILED."""
    cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)).isoformat()
    logger.info(f"Checking for ai_analysis_jobs active before {cutoff_time} (older than {timeout_minutes}m)...")

    active_statuses = ["QUEUED", "DOWNLOADING", "TRANSCRIBING", "ANALYZING", "GENERATING_METADATA"]
    reaped_count = 0

    try:
        # Fetch active jobs started or created before cutoff
        res = sb.table("ai_analysis_jobs").select("id, status, started_at, created_at, updated_at") \
            .in_("status", active_statuses) \
            .lte("created_at", cutoff_time) \
            .execute()
        
        stuck_jobs = res.data or []
        for job in stuck_jobs:
            job_id = job.get("id")
            prev_status = job.get("status")
            now_iso = datetime.now(timezone.utc).isoformat()
            
            logger.warning(f"Reaping stuck ai_analysis_job {job_id} (status: {prev_status})")
            sb.table("ai_analysis_jobs").update({
                "status": "FAILED",
                "progress": 100,
                "current_step": "Job execution timed out",
                "error_message": f"Analysis job timed out on runner after exceeding {timeout_minutes} minutes without completion.",
                "completed_at": now_iso
            }).eq("id", job_id).execute()
            reaped_count += 1

    except Exception as e:
        logger.error(f"Error while reaping ai_analysis_jobs: {e}")

    return reaped_count


def reap_stuck_durable_jobs(sb, timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> int:
    """Finds durable `jobs` table rows stuck in active states past timeout threshold and marks them failed."""
    cutoff_time = (datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)).isoformat()
    active_statuses = ["queued", "pending", "running", "processing"]
    reaped_count = 0

    try:
        res = sb.table("jobs").select("id, status, job_type, created_at, started_at") \
            .in_("status", active_statuses) \
            .lte("created_at", cutoff_time) \
            .execute()

        stuck_jobs = res.data or []
        for job in stuck_jobs:
            job_id = job.get("id")
            prev_status = job.get("status")
            now_iso = datetime.now(timezone.utc).isoformat()

            logger.warning(f"Reaping stuck durable job {job_id} (type: {job.get('job_type')}, status: {prev_status})")
            sb.table("jobs").update({
                "status": "failed",
                "current_step": "Job execution timed out",
                "error_message": f"Job timed out after exceeding {timeout_minutes} minutes without progress.",
                "completed_at": now_iso
            }).eq("id", job_id).execute()
            reaped_count += 1

    except Exception as e:
        # Table might not exist or empty
        logger.debug(f"Could not reap durable jobs table: {e}")

    return reaped_count


def reap_expired_worker_leases(sb) -> int:
    """Releases expired worker leases on scheduled_videos so uploads can be retried."""
    now_iso = datetime.now(timezone.utc).isoformat()
    recovered_count = 0

    try:
        res = sb.table("scheduled_videos").select("id, title, worker_id, lease_expires_at") \
            .in_("upload_status", ["claimed", "uploading"]) \
            .lte("lease_expires_at", now_iso) \
            .execute()

        expired = res.data or []
        for item in expired:
            vid_id = item.get("id")
            logger.warning(f"Releasing expired lease for scheduled video {vid_id} ('{item.get('title')}')")
            sb.table("scheduled_videos").update({
                "upload_status": "pending",
                "claimed_at": None,
                "lease_expires_at": None,
                "worker_id": None
            }).eq("id", vid_id).execute()
            recovered_count += 1

    except Exception as e:
        logger.debug(f"Could not release worker leases: {e}")

    return recovered_count


def run_reaper(timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> Dict[str, int]:
    """Runs all stuck job checks and returns counts."""
    sb = get_supabase_client()
    logger.info("🚀 Starting stuck job reaper workflow...")

    ai_reaped = reap_stuck_ai_analysis_jobs(sb, timeout_minutes)
    durable_reaped = reap_stuck_durable_jobs(sb, timeout_minutes)
    leases_recovered = reap_expired_worker_leases(sb)

    summary = {
        "ai_analysis_jobs_reaped": ai_reaped,
        "durable_jobs_reaped": durable_reaped,
        "worker_leases_recovered": leases_recovered
    }
    logger.info(f"✅ Stuck job reaper complete: {summary}")
    return summary


if __name__ == "__main__":
    run_reaper()
