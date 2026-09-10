"""
workflow_cleanup.py  —  Cloud worker script designed to run in GitHub Actions once daily.

What it does:
  1. Polls Supabase for 'uploaded' videos where delete_after <= NOW().
  2. Deletes the physical video file from Supabase Storage.
  3. Inserts an audit log record into videos_audit_log (soft delete).
  4. Deletes the original row from scheduled_videos.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from cloud.cloud_auth import get_supabase_client

BUCKET = "reelgrab-videos"

def process_cleanup():
    sb = get_supabase_client()
    now_utc = datetime.now(timezone.utc).isoformat()

    print(f"[{now_utc}] Checking for videos ready to be cleaned up (soft-deleted)...")

    # 1. Fetch uploaded videos whose 3-day retention period has expired
    res = sb.table("scheduled_videos").select("*") \
            .eq("upload_status", "uploaded") \
            .lte("delete_after", now_utc) \
            .execute()
    
    videos = res.data
    if not videos:
        print("No videos due for cleanup at this time. Exiting.")
        return

    print(f"Found {len(videos)} video(s) ready for cleanup.")

    for video in videos:
        vid_id = video["id"]
        library_id = video.get("library_video_id")
        title = video["title"]
        yt_id = video.get("youtube_video_id", "UNKNOWN")
        storage_path = video["storage_path"]
        uploaded_at = video.get("uploaded_at")

        print(f"\n🧹 Cleaning up: {title} (Queue ID: {vid_id}, Library ID: {library_id})")

        # Idempotency check
        if not storage_path:
            print(f"  ⏭️ Idempotency check: storage_path already NULL. Skipping storage delete.")
            sb.table("scheduled_videos").delete().eq("id", vid_id).execute()
            continue

        if library_id:
            sb.table("video_activity_log").insert({
                "video_id": library_id,
                "event_type": "STORAGE_DELETE_STARTED",
                "message": "Attempting to delete cloud video file"
            }).execute()

        try:
            print(f"  🗑️ Deleting file from storage: {storage_path}")
            # The Supabase storage remove API returns a list of deleted files.
            # If the file is already gone, it might return empty or error. We proceed anyway.
            sb.storage.from_(BUCKET).remove([storage_path])

            print(f"  📝 Creating audit log record for YouTube ID: {yt_id}")
            audit_row = {
                "title": title,
                "youtube_video_id": yt_id,
                "uploaded_at": uploaded_at,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            }
            sb.table("videos_audit_log").insert(audit_row).execute()
            
            if library_id:
                sb.table("video_library").update({
                    "storage_path": None,
                    "storage_deleted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "cleaned"
                }).eq("id", library_id).execute()
                sb.table("video_activity_log").insert({
                    "video_id": library_id,
                    "event_type": "STORAGE_DELETE_SUCCESS",
                    "message": "Cloud video file permanently deleted"
                }).execute()

            print(f"  ✂️ Removing row from scheduled_videos table")
            sb.table("scheduled_videos").delete().eq("id", vid_id).execute()

            print(f"  ✅ Cleanup successful for {title}")

        except Exception as e:
            print(f"  ❌ Cleanup failed: {str(e)}")
            if library_id:
                sb.table("video_library").update({
                    "status": "delete_pending"
                }).eq("id", library_id).execute()
                sb.table("video_activity_log").insert({
                    "video_id": library_id,
                    "event_type": "STORAGE_DELETE_FAILED",
                    "message": f"Storage cleanup failed: {str(e)}"
                }).execute()

if __name__ == "__main__":
    process_cleanup()
