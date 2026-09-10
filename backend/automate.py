"""
automate.py  —  YouTube Shorts Automation endpoint.
Delegates AI generation to the professional ai_pipeline module.
"""

from fastapi import APIRouter, BackgroundTasks
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

logger = logging.getLogger(__name__)
import logging
fh = logging.FileHandler('automate_debug.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)


from backend.ai_pipeline import generate_shorts_content
from cloud.enqueue import enqueue_video
from cloud.cloud_auth import get_supabase_client

router = APIRouter()


class AutomateRequest(BaseModel):
    title: str
    description: str
    hashtags: List[str] = []
    thumbnail_url: Optional[str] = None
    url: str
    opus_mode: Optional[bool] = False
    iso_schedule: Optional[str] = None
    scheduled_time_human: Optional[str] = None
    # Optional enrichment fields (sent from frontend if available)
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    detected_genre: Optional[str] = None
    detected_language: Optional[str] = "English"
    target_region: Optional[str] = "India"


@router.post("/automate", summary="Trigger Cloud Automation Pipeline", description="Downloads video, applies layout, and schedules for upload to Supabase.")
async def automate_pipeline(req: AutomateRequest, background_tasks: BackgroundTasks):
    logger.info(f"🚀 Starting automation pipeline for: {req.url}")
    
    opt_title = req.title
    opt_desc = req.description
    opt_tags = req.hashtags
    sched_time = req.scheduled_time_human or "07:30 PM" 
    
    if req.iso_schedule:
        final_iso_schedule = req.iso_schedule
        human_readable_time = req.scheduled_time_human or "07:30 PM"
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

    # 2. Download the video locally to a temporary location
    downloads_dir = Path(__file__).parent.parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    temp_id = str(uuid.uuid4())
    temp_filepath = str(downloads_dir / f"auto_{temp_id}.mp4")

    logger.info(f"⬇️ Downloading video to temporary file: {temp_filepath}...")
    ydl_opts = {
        'format': 'best',
        'outtmpl': temp_filepath,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [req.url])
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {"status": "error", "message": f"Download failed: {str(e)}"}

    # Apply Auto-Detect & Fit-to-Canvas (Master Requirement)
    import sys
    # path fixes to reach fit_to_canvas in root
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    try:
        from fit_to_canvas import fit_to_canvas
        fitted_filepath = f"downloads/{uuid.uuid4().hex}_fitted.mp4"
        logger.info("Applying Master Fit-to-Canvas 9:16 layout without cropping...")
        await asyncio.to_thread(fit_to_canvas, temp_filepath, fitted_filepath, 1080, 1920)
        if os.path.exists(temp_filepath): 
            os.remove(temp_filepath)
        temp_filepath = fitted_filepath
    except Exception as e:
        logger.error(f"Fit-to-canvas failed: {e}")
        # non-fatal fallback

    # 3. Enqueue directly to the Supabase Cloud Storage + Database
    logger.info(f"⬆️ Sending securely to Supabase Cloud...")
    try:
        new_id = await asyncio.to_thread(enqueue_video, 
            file_path=temp_filepath,
            title=opt_title,
            description=opt_desc,
            hashtags=opt_tags,
            schedule_time=final_iso_schedule,
            source_url=req.url,
            thumbnail_url=req.thumbnail_url
        )
        logger.info(f"✅ Video enqueued in cloud with DB ID: {new_id}")
    except Exception as e:
        logger.error(f"Cloud Upload failed: {e}")
        # Ensure we delete the file if cloud upload fails
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return {"status": "error", "message": f"Cloud Upload failed: {str(e)}"}

    # 4. Clean up the local hard drive!
    if os.path.exists(temp_filepath):
        logger.info("🧹 Cleaning up local temporary video file...")
        os.remove(temp_filepath)

    return {
        "status": "success",
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
