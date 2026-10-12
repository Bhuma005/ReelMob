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


from backend.services.job_store import JobStore

AUTOMATE_JOBS: JobStore = JobStore(default_type="cloud_automation")


async def _execute_automate_background_pipeline(
    job_id: str,
    url: str,
    format_id: Optional[str],
    thumbnail_url: Optional[str],
    opt_title: str,
    opt_desc: str,
    opt_tags: List[str],
    final_iso_schedule: str,
):
    downloads_dir = Path(__file__).parent.parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    temp_filepath = None
    fitted_filepath = None
    try:
        if job_id in AUTOMATE_JOBS:
            AUTOMATE_JOBS[job_id]["progress"] = 25
            AUTOMATE_JOBS[job_id]["current_step"] = "Downloading source video stream..."

        temp_filepath = await async_ensure_video_downloaded(
            url=url,
            target_dir=str(downloads_dir),
            format_id=format_id,
            prefix="auto_"
        )

        if job_id in AUTOMATE_JOBS:
            AUTOMATE_JOBS[job_id]["progress"] = 50
            AUTOMATE_JOBS[job_id]["current_step"] = "Applying 9:16 vertical layout & canvas..."

        fitted_filepath = str(downloads_dir / f"{uuid.uuid4().hex}_fitted.mp4")
        try:
            import gc
            gc.collect()
            from backend.services.resource_limits import heavy_job_gate
            logger.info("Applying Master Fit-to-Canvas 9:16 layout without cropping...")
            async with heavy_job_gate("automate_fit_to_canvas"):
                await asyncio.to_thread(fit_to_canvas, temp_filepath, fitted_filepath, 1080, 1920)
            gc.collect()
            if os.path.exists(fitted_filepath) and os.path.getsize(fitted_filepath) > 0:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                temp_filepath = fitted_filepath
        except Exception as e:
            logger.error(f"Fit-to-canvas failed: {e}")
            # non-fatal fallback: use temp_filepath as-is

        if job_id in AUTOMATE_JOBS:
            AUTOMATE_JOBS[job_id]["progress"] = 75
            AUTOMATE_JOBS[job_id]["current_step"] = "Uploading to Cloud Storage & Scheduling..."

        logger.info("⬆️ Sending securely to Supabase Cloud...")
        new_id = await asyncio.to_thread(
            enqueue_video,
            file_path=temp_filepath,
            title=opt_title,
            description=opt_desc,
            hashtags=opt_tags,
            schedule_time=final_iso_schedule,
            source_url=url,
            thumbnail_url=thumbnail_url
        )
        logger.info(f"✅ Video enqueued in cloud with DB ID: {new_id}")

        if job_id in AUTOMATE_JOBS:
            AUTOMATE_JOBS[job_id]["status"] = "completed"
            AUTOMATE_JOBS[job_id]["progress"] = 100
            AUTOMATE_JOBS[job_id]["current_step"] = "Video scheduled successfully"
            AUTOMATE_JOBS[job_id]["result"] = {"queue_id": new_id}

    except Exception as e:
        logger.error(f"Cloud upload/process failed in background: {e}", exc_info=True)
        if job_id in AUTOMATE_JOBS:
            AUTOMATE_JOBS[job_id]["status"] = "failed"
            AUTOMATE_JOBS[job_id]["error"] = str(e)
            AUTOMATE_JOBS[job_id]["current_step"] = f"Failed: {str(e)}"
    finally:
        for f in (temp_filepath, fitted_filepath):
            if f and os.path.exists(f):
                logger.info(f"🧹 Cleaning up local temporary video file: {f}")
                try:
                    os.remove(f)
                except Exception:
                    pass


@router.post("/automate", summary="Trigger Cloud Automation Pipeline", description="Downloads video, applies layout, and schedules for upload to Supabase.")
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

    # Queue durable background task so HTTP response completes in <1s (prevents Render 100s proxy timeout)
    job_id = uuid.uuid4().hex
    AUTOMATE_JOBS[job_id] = {
        "status": "processing",
        "progress": 10,
        "current_step": "Pipeline initiated, downloading video in background...",
        "title": opt_title,
        "url": req.url,
        "schedule_time": final_iso_schedule,
    }

    background_tasks.add_task(
        _execute_automate_background_pipeline,
        job_id=job_id,
        url=req.url,
        format_id=req.format_id,
        thumbnail_url=req.thumbnail_url,
        opt_title=opt_title,
        opt_desc=opt_desc,
        opt_tags=opt_tags,
        final_iso_schedule=final_iso_schedule,
    )

    return {
        "status": "success",
        "job_id": job_id,
        "message": "Automation pipeline triggered successfully",
        "automation_details": {
            "title":              opt_title,
            "description":        opt_desc,
            "hashtags":           opt_tags,
            "scheduled_time":     human_readable_time,
            "iso_schedule":       final_iso_schedule,
            "reasoning":          "Peak engagement window.",
            "confidence_notes":   "",
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
