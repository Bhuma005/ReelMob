"""
automate.py  —  YouTube Shorts Automation endpoint.
Delegates AI generation to the professional ai_pipeline module.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
import yt_dlp
import asyncio
import logging
from pathlib import Path
import dateutil.parser
from datetime import datetime, date, timedelta
from pydantic import field_validator
from backend.schemas import validate_video_url

logger = logging.getLogger("reelsmob.automate")

from backend.ai_pipeline import generate_shorts_content
from backend.fit_to_canvas import fit_to_canvas
from backend.services.video_download import async_ensure_video_downloaded
from cloud.enqueue import enqueue_video
from cloud.cloud_auth import get_supabase_client

router = APIRouter()


class AutomateRequest(BaseModel):
    title: str
    description: str
    hashtags: List[str] = []
    thumbnail_url: Optional[str] = None
    url: str
    format_id: Optional[str] = None
    opus_mode: Optional[bool] = False

    @field_validator('url')
    @classmethod
    def check_url(cls, v: str) -> str:
        return validate_video_url(v)
    iso_schedule: Optional[str] = None
    scheduled_time_human: Optional[str] = None
    # Optional enrichment fields (sent from frontend if available)
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    detected_genre: Optional[str] = None
    detected_language: Optional[str] = "English"
    target_region: Optional[str] = "India"


import urllib.request
import json
from backend.services.job_store import JobStore
from cloud.enqueue import enqueue_video, enqueue_remote_video

AUTOMATE_JOBS: JobStore = JobStore(default_type="cloud_automation")


def dispatch_github_actions_upload(video_id: str = "") -> bool:
    """
    Fires repository_dispatch event to trigger GitHub Actions upload_poller.yml workflow.
    Uses GitHub Actions high-speed multi-core CPU and gigabit network to process the video.
    """
    token = (os.getenv("GITHUB_DISPATCH_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        logger.info("GITHUB_DISPATCH_TOKEN not set. Video queued in Supabase for scheduled GitHub Actions poller.")
        return False

    repo = os.getenv("GITHUB_REPOSITORY", "Bhuma005/ReelMob").strip()
    url = f"https://api.github.com/repos/{repo}/dispatches"

    payload = {
        "event_type": "trigger-upload",
        "client_payload": {
            "video_id": video_id
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "ReelsMob-Backend"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                logger.info(f"✅ Successfully dispatched GitHub Actions upload worker for video {video_id} on {repo}")
                return True
            return False
    except Exception as e:
        logger.warning(f"GitHub Actions dispatch skipped or failed: {e}")
        return False


@router.post("/automate", summary="Trigger Cloud Automation Pipeline", description="Schedules video and offloads heavy download/encode/upload to GitHub Actions.")
async def automate_pipeline(req: AutomateRequest, background_tasks: BackgroundTasks):
    logger.info(f"🚀 Starting automation pipeline for: {req.url}")
    
    opt_title = req.title
    opt_desc = req.description
    opt_tags = req.hashtags or []
    from backend.services.scheduler import calculate_deterministic_schedule
    sched_intel = calculate_deterministic_schedule()
    default_posting_time = sched_intel.get("human_readable_time") or (
        sched_intel.get("fallback_schedule", {}).get("human_readable_time", "06:00 PM")
    )
    sched_time = req.scheduled_time_human or default_posting_time 
    
    if req.iso_schedule:
        final_iso_schedule = req.iso_schedule
        human_readable_time = req.scheduled_time_human or default_posting_time
    else:
        # ── Intelligent Date Scheduling (Max 2 per day) ──
        try:
            parsed_time = dateutil.parser.parse(sched_time).time()
            now = datetime.now()
            target_date = now.date()
            target_dt = datetime.combine(target_date, parsed_time)
            
            # 1. If today's time has already passed, start checking from tomorrow
            if target_dt < now:
                target_date += timedelta(days=1)
                target_dt = datetime.combine(target_date, parsed_time)
                
            # 2. Query Supabase to ensure MAX 2 posts per day!
            sb = get_supabase_client()
            while True:
                # Check how many videos are scheduled between start and end of target_date
                start_of_day = datetime.combine(target_date, datetime.min.time()).astimezone().isoformat()
                end_of_day = datetime.combine(target_date, datetime.max.time()).astimezone().isoformat()
                
                res = sb.table("scheduled_videos").select("id", count="exact") \
                    .gte("schedule_time", start_of_day) \
                    .lte("schedule_time", end_of_day).execute()
                    
                # 'count' attribute contains the total matching rows in Supabase
                daily_count = res.count if res.count is not None else len(res.data)
                
                if daily_count < 2:
                    # We have space on this day!
                    break
                    
                # If 2 or more videos are already scheduled on this day, push exactly 24 hours forward!
                target_date += timedelta(days=1)
                target_dt = datetime.combine(target_date, parsed_time)
                
            final_iso_schedule = target_dt.astimezone().isoformat()
            human_readable_time = target_dt.strftime("%B %d, %I:%M %p")
            
        except Exception as e:
            logger.error(f"Time parsing Error: {e}")
            # Fallback to right now + 2 hours if parse fails entirely
            target_dt = datetime.now() + timedelta(hours=2)
            final_iso_schedule = target_dt.astimezone().isoformat()
            human_readable_time = target_dt.strftime("%B %d, %I:%M %p")

    # Offload queue insertion to Supabase (Zero Render CPU & Disk usage)
    try:
        new_id = await asyncio.to_thread(
            enqueue_remote_video,
            source_url=req.url,
            title=opt_title,
            description=opt_desc,
            hashtags=opt_tags,
            schedule_time=final_iso_schedule,
            thumbnail_url=req.thumbnail_url
        )
        logger.info(f"✅ Video enqueued in cloud with DB ID: {new_id} (Offloaded to GitHub Actions CPU)")
    except Exception as e:
        logger.error(f"Cloud Queue insert failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cloud Scheduling failed: {str(e)}")

    # Dispatch to GitHub Actions runner in background
    background_tasks.add_task(dispatch_github_actions_upload, video_id=new_id)

    job_id = uuid.uuid4().hex
    AUTOMATE_JOBS[job_id] = {
        "status": "completed",
        "progress": 100,
        "current_step": "Scheduled and offloaded to GitHub Actions multi-core CPU",
        "title": opt_title,
        "url": req.url,
        "schedule_time": final_iso_schedule,
        "result": {"queue_id": new_id}
    }

    return {
        "status": "success",
        "job_id": job_id,
        "message": "Automation pipeline scheduled successfully and offloaded to GitHub Actions",
        "automation_details": {
            "title":              opt_title,
            "description":        opt_desc,
            "hashtags":           opt_tags,
            "scheduled_time":     human_readable_time,
            "iso_schedule":       final_iso_schedule,
            "reasoning":          "Peak engagement window.",
            "confidence_notes":   "Offloaded to GitHub Actions multi-core runner.",
            "post_status":        "Scheduled 🚀",
            "model_used":         "Pre-calculated in frontend"
        }
    }


@router.get("/automate/status/{job_id}", summary="Check status of background automation pipeline")
async def get_automate_job_status(job_id: str):
    job = AUTOMATE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
