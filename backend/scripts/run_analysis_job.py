"""
run_analysis_job.py — Standalone headless runner executed on GitHub Actions (2 CPU, 7GB RAM).

Receives job payload from GitHub Actions repository_dispatch event, runs the shared
video analysis pipeline, and writes the final results directly to Supabase.
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cloud.cloud_auth import get_supabase_client
from backend.services.analysis_service import run_video_analysis
from backend.agents.master_agent import backfill_hashtags
from backend.retry import sync_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("reelsmob.github_runner")


def parse_job_payload() -> Dict[str, Any]:
    """Extracts payload from JOB_PAYLOAD env var or command-line arguments."""
    raw_payload = os.environ.get("JOB_PAYLOAD", "").strip()
    if raw_payload:
        try:
            return json.loads(raw_payload)
        except Exception as e:
            logger.warning(f"Failed to parse JOB_PAYLOAD as JSON: {e}")

    # Fallback to CLI argument or file
    if len(sys.argv) > 1 and sys.argv[1].endswith(".json") and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def update_supabase_job(sb, job_id: str, fields: Dict[str, Any]):
    """Safely updates ai_analysis_jobs record in Supabase with retry."""
    def _do_update():
        return sb.table("ai_analysis_jobs").update(fields).eq("id", job_id).execute()

    try:
        sync_retry(_do_update, max_retries=3, operation_name="update_ai_analysis_jobs")
    except Exception as e:
        logger.error(f"Failed to update Supabase for job {job_id}: {e}")


def main():
    payload = parse_job_payload()
    job_id = payload.get("job_id")
    video_url = payload.get("video_url") or payload.get("url") or ""
    title = payload.get("title") or ""
    description = payload.get("description") or ""

    if not job_id:
        logger.error("No job_id provided in payload. Exiting.")
        sys.exit(1)

    logger.info(f"🚀 Starting GitHub Actions video analysis for job: {job_id}")
    logger.info(f"Target URL: {video_url} | Title: {title[:50]}...")

    sb = None
    try:
        sb = get_supabase_client()
    except Exception as e:
        logger.error(f"Supabase client initialization failed: {e}")

    # Step 1: Mark job as actively running on GitHub Actions
    if sb:
        update_supabase_job(sb, job_id, {
            "status": "ANALYZING",
            "progress": 25,
            "current_step": "Extracting frames on GitHub Actions runner (2 CPU)...",
            "started_at": datetime.now(timezone.utc).isoformat()
        })

    def _progress_cb(pct: int, msg: str):
        logger.info(f"[{pct}%] {msg}")
        if sb and pct in (20, 50, 75):
            update_supabase_job(sb, job_id, {
                "progress": pct,
                "current_step": f"{msg} (GitHub Actions)"
            })

    # Step 2: Run shared video analysis with generous 8-min ceiling on 2-CPU runner
    try:
        result_payload = asyncio.run(
            run_video_analysis(
                video_url=video_url,
                raw_title=title,
                raw_description=description,
                progress_callback=_progress_cb,
                timeout_seconds=480.0
            )
        )
        result_payload["processed_by"] = "github_actions"

        logger.info(f"✅ Video analysis complete for job {job_id}. Title: {result_payload.get('viral_title')}")

        if sb:
            update_supabase_job(sb, job_id, {
                "status": "COMPLETED",
                "progress": 100,
                "current_step": "AI optimization complete (GitHub Actions)",
                "result": result_payload,
                "fallback_reason": result_payload.get("fallback_reason"),
                "completed_at": datetime.now(timezone.utc).isoformat()
            })

    except Exception as e:
        logger.error(f"❌ Analysis failed on GitHub Actions runner: {e}", exc_info=True)
        fallback_reason = f"GitHub Actions runner execution error: {e}"
        fallback_title = title or "Trending Reel"
        fallback_desc = description or "Watch this trending video! #Shorts #Viral"
        fallback_tags = backfill_hashtags([], fallback_title, fallback_desc, min_count=7)

        from backend.services.scheduler import calculate_deterministic_schedule
        sched_rec = calculate_deterministic_schedule()
        posting_slot = sched_rec.get("human_readable_time") or sched_rec.get("fallback_schedule", {}).get("human_readable_time", "06:00 PM")
        posting_reason = sched_rec.get("reason", "Deterministic scheduling fallback.")

        raw_result = {
            "title": fallback_title,
            "description": fallback_desc,
            "youtube_hashtags": fallback_tags,
            "instagram_hashtags": fallback_tags,
            "title_candidates": [{"strategy": "Original", "title": fallback_title}],
            "viewer_appeal_score": 80,
            "title_reason": ["GitHub Actions runner fallback"],
            "posting_recommendation": {
                "human_readable_time": posting_slot,
                "reason": posting_reason,
                "status": sched_rec.get("status", "insufficient_data")
            },
            "ai_failed": True,
            "fallback": True,
            "fallback_reason": fallback_reason,
            "source_label": "From caption — runner fallback",
            "analysis_source": "caption_fallback",
            "video_analyzed": False,
            "processed_by": "github_actions"
        }

        fallback_payload = {
            "viral_title": fallback_title,
            "optimized_description": fallback_desc,
            "youtube": fallback_tags,
            "instagram": fallback_tags,
            "analysis": f"Completed with fallback metadata ({fallback_reason}).",
            "confidence_notes": "FALLBACK",
            "scheduled_time": posting_slot,
            "raw_result": raw_result,
            "ai_failed": True,
            "fallback_reason": fallback_reason,
            "source_label": "From caption — runner fallback",
            "analysis_source": "caption_fallback",
            "video_analyzed": False,
            "processed_by": "github_actions"
        }

        if sb:
            update_supabase_job(sb, job_id, {
                "status": "COMPLETED",
                "progress": 100,
                "current_step": "AI completed with fallback metadata (GitHub Actions)",
                "result": fallback_payload,
                "error_message": str(e),
                "fallback_reason": fallback_reason,
                "completed_at": datetime.now(timezone.utc).isoformat()
            })


if __name__ == "__main__":
    main()
