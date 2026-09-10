"""
enqueue.py  —  Local script: run this after your video is processed.

What it does:
  1. Uploads the finished video file to Supabase Storage
  2. Inserts a row into scheduled_videos with your chosen schedule_time
  3. Prints the new row's UUID so you can monitor it

Usage:
    python -m cloud.enqueue \
        --file   "path/to/video.mp4" \
        --title  "Night Has Come – Final Twist" \
        --description "A psychological thriller where nobody saw the ending coming." \
        --hashtags "#KDrama,#Thriller,#Shorts" \
        --schedule "2026-08-03T19:00:00+05:30"

    (schedule is ISO 8601 with timezone; the script converts to UTC before storing)

Environment variables required (or set via .env locally):
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── allow running as: python -m cloud.enqueue ─────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from cloud.cloud_auth import get_supabase_client

BUCKET = "reelgrab-videos"   # Supabase Storage bucket name

# ── Free-tier storage warning threshold (bytes) ───────────────────────────────
# Supabase free tier: 1 GB storage.  Warn at 800 MB.
WARN_BYTES = 800 * 1024 * 1024


def _check_bucket_usage(sb) -> None:
    """Log a warning if bucket usage is approaching the free-tier limit."""
    try:
        files = sb.storage.from_(BUCKET).list()
        total = sum(f.get("metadata", {}).get("size", 0) for f in files if isinstance(f, dict))
        mb = total / (1024 * 1024)
        print(f"[Storage] Current bucket usage: {mb:.1f} MB")
        if total >= WARN_BYTES:
            print(
                f"⚠️  WARNING: Bucket usage ({mb:.1f} MB) is approaching the Supabase "
                "free-tier 1 GB limit. Consider cleaning up old files or upgrading."
            )
    except Exception as e:
        print(f"[Storage] Could not check bucket usage: {e}")


def enqueue_video(
    file_path: str,
    title: str,
    description: str,
    hashtags: list[str],
    schedule_time: str,
    source_url: str = None,
    thumbnail_url: str = None,
) -> str:
    """
    Creates permanent Library record, uploads file to Supabase Storage, 
    inserts queue row, and logs activity.
    """
    sb = get_supabase_client()

    dt = datetime.fromisoformat(schedule_time)
    if dt.tzinfo is None:
        print("⚠️  schedule_time has no timezone — assuming UTC.")
        dt = dt.replace(tzinfo=timezone.utc)
    schedule_utc = dt.astimezone(timezone.utc).isoformat()

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    storage_name = f"{uuid.uuid4().hex}_{file_path.name}"
    storage_path = f"videos/{storage_name}"
    
    # ── 1. Create Permanent Library Record ─────────────────────────────────────
    print("[DB] Creating permanent library record...")
    lib_row = {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "schedule_time": schedule_utc,
        "status": "scheduled",
        "storage_path": storage_path,
        "source_url": source_url,
        "thumbnail_url": thumbnail_url
    }
    lib_res = sb.table("video_library").insert(lib_row).execute()
    library_id = lib_res.data[0]["id"]
    print(f"[DB] ✅ Library record created: {library_id}")

    # ── 2. Log VIDEO_CREATED ──────────────────────────────────────────────────
    sb.table("video_activity_log").insert({
        "video_id": library_id,
        "event_type": "VIDEO_CREATED",
        "message": f"Library record created for {title}"
    }).execute()

    # ── 3. Upload file to Supabase Storage ────────────────────────────────────
    print(f"[Upload] Uploading {file_path.name} → {storage_path} ...")
    try:
        with open(file_path, "rb") as f:
            sb.storage.from_(BUCKET).upload(
                path=storage_path,
                file=f,
                file_options={"content-type": "video/mp4"},
            )
        print(f"[Upload] ✅ Uploaded to storage: {storage_path}")
    except Exception as e:
        print(f"[Upload] ❌ Upload failed: {e}")
        print(f"[DB] Rolling back library record {library_id}...")
        # Safe cleanup of the orphaned library record since storage failed
        sb.table("video_library").delete().eq("id", library_id).execute()
        raise e

    _check_bucket_usage(sb)

    # ── 4. Insert Queue Row (scheduled_videos) ────────────────────────────────
    queue_row = {
        "title":         title,
        "description":   description,
        "hashtags":      hashtags,
        "storage_path":  storage_path,
        "schedule_time": schedule_utc,
        "upload_status": "pending",
        "library_video_id": library_id
    }
    queue_res = sb.table("scheduled_videos").insert(queue_row).execute()
    queue_id = queue_res.data[0]["id"]
    print(f"[DB] ✅ Queued in scheduled_videos: {queue_id}")

    # ── 5. Log VIDEO_SCHEDULED ────────────────────────────────────────────────
    sb.table("video_activity_log").insert({
        "video_id": library_id,
        "event_type": "VIDEO_SCHEDULED",
        "message": f"Video scheduled for {schedule_utc} (Queue ID: {queue_id})"
    }).execute()
    
    return library_id


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enqueue a video for cloud upload")
    parser.add_argument("--file",        required=True, help="Path to the local video file")
    parser.add_argument("--title",       required=True, help="YouTube video title")
    parser.add_argument("--description", default="",   help="YouTube description")
    parser.add_argument("--hashtags",    default="",   help="Comma-separated hashtags, e.g. #Shorts,#KDrama")
    parser.add_argument("--schedule",    required=True, help="ISO 8601 datetime, e.g. 2026-08-03T19:00:00+05:30")
    args = parser.parse_args()

    tags = [t.strip() for t in args.hashtags.split(",") if t.strip()]
    new_id = enqueue_video(
        file_path=args.file,
        title=args.title,
        description=args.description,
        hashtags=tags,
        schedule_time=args.schedule,
    )
    print(f"\n✅ Done — video enqueued to library: {new_id}")
