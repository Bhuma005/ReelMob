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
) -> str:
    """
    Uploads file to Supabase Storage, inserts DB row, returns the new video's UUID.
    schedule_time: ISO 8601 string (any tz) — stored as UTC in the DB.
    """
    sb = get_supabase_client()

    # ── 1. Parse and normalise schedule_time to UTC ───────────────────────────
    dt = datetime.fromisoformat(schedule_time)
    if dt.tzinfo is None:
        print("⚠️  schedule_time has no timezone — assuming UTC.")
        dt = dt.replace(tzinfo=timezone.utc)
    schedule_utc = dt.astimezone(timezone.utc).isoformat()

    # ── 2. Upload file to Supabase Storage ────────────────────────────────────
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    storage_name = f"{uuid.uuid4().hex}_{file_path.name}"
    storage_path = f"videos/{storage_name}"

    print(f"[Upload] Uploading {file_path.name} → {storage_path} ...")
    with open(file_path, "rb") as f:
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=f,
            file_options={"content-type": "video/mp4"},
        )
    print(f"[Upload] ✅ Uploaded to storage: {storage_path}")

    # ── 3. Check storage usage after upload ───────────────────────────────────
    _check_bucket_usage(sb)

    # ── 4. Insert DB row ──────────────────────────────────────────────────────
    row = {
        "title":         title,
        "description":   description,
        "hashtags":      hashtags,
        "storage_path":  storage_path,
        "schedule_time": schedule_utc,
        "upload_status": "pending",
    }
    result = sb.table("scheduled_videos").insert(row).execute()
    new_id = result.data[0]["id"]
    print(f"[DB]     ✅ Scheduled: id={new_id} | time={schedule_utc}")
    
    # Write to audit log
    try:
        from datetime import datetime
        # We write to root reelgrab_audit.log
        audit_path = Path(__file__).parent.parent / "reelgrab_audit.log"
        with open(audit_path, "a", encoding='utf-8') as log_file:
            log_file.write(f"[{datetime.now().isoformat()}] UPLOADED VIDEO | ID: {new_id} | Title: {title} | Storage: {storage_path} | Schedule UTC: {schedule_utc}\n")
    except Exception as e:
        print(f"[Log] Failed to audit log: {e}")
        
    return new_id


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
    print(f"\n✅ Done — video enqueued with id: {new_id}")
