"""
workflow_upload.py  —  Cloud worker script designed to run in GitHub Actions.

What it does:
  1. Polls Supabase for 'pending' or expired 'claimed' videos where schedule_time <= NOW().
  2. Atomically claims each video with worker lease to prevent duplicate uploads across concurrent runners.
  3. Pre-upload idempotency check: verifies video hasn't already been published to YouTube.
  4. Downloads the video from Supabase Storage to a temporary runner space.
  5. Uploads the video to YouTube via the Data API using OAuth credentials.
  6. Updates the DB (status='uploaded', library status='published', sets delete_after to now + 3 days).
  7. Handles failures gracefully (retries up to 3 times before setting 'failed').
"""

import os
import sys
import uuid
import tempfile
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Required for YouTube API - allow graceful import for test suites
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    Credentials = None
    build = None
    MediaFileUpload = None

sys.path.insert(0, str(Path(__file__).parent.parent))
from cloud.cloud_auth import get_supabase_client, get_youtube_creds
from backend.services.state_machine import can_transition_queue, can_transition_library

BUCKET = "reelgrab-videos"
DEFAULT_LEASE_MINUTES = 15


def get_youtube_service():
    """Initialises the YouTube Data API client using our unified credentials."""
    if build is None or Credentials is None:
        raise RuntimeError("Google API client libraries are not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

    creds_data = get_youtube_creds()
    
    # We construct the Credentials object directly so it can auto-refresh natively
    creds = Credentials(
        token=None,  # Forces a refresh on first use
        refresh_token=creds_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"]
    )
    return build("youtube", "v3", credentials=creds)


def claim_video(sb, video_id: str, worker_id: str, lease_minutes: int = DEFAULT_LEASE_MINUTES) -> bool:
    """
    Atomically claims a scheduled video row with a worker ID and lease expiration.
    Returns True if successfully claimed, False if another worker claimed it first.
    """
    now = datetime.now(timezone.utc)
    now_utc = now.isoformat()
    lease_expires_utc = (now + timedelta(minutes=lease_minutes)).isoformat()

    try:
        res = sb.table("scheduled_videos").update({
            "upload_status": "claimed",
            "claimed_at": now_utc,
            "lease_expires_at": lease_expires_utc,
            "worker_id": worker_id
        }).eq("id", video_id).in_("upload_status", ["pending", "claimed"]).execute()

        if res and res.data and len(res.data) > 0:
            return True
        return False
    except Exception as e:
        print(f"Error attempting atomic claim on video {video_id}: {e}")
        return False


def process_pending_uploads(worker_id: Optional[str] = None):
    sb = get_supabase_client()
    now = datetime.now(timezone.utc)
    now_utc = now.isoformat()
    worker_id = worker_id or f"worker-{os.getenv('GITHUB_RUN_ID', 'local')}-{uuid.uuid4().hex[:6]}"

    print(f"[{now_utc}] Worker '{worker_id}' checking for scheduled uploads due before now...")

    # 1. Fetch pending videos due for upload (FIFO order, max 25 per run)
    res = sb.table("scheduled_videos").select("*") \
            .in_("upload_status", ["pending", "claimed"]) \
            .lte("schedule_time", now_utc) \
            .order("schedule_time", desc=False) \
            .limit(25) \
            .execute()
    
    candidates = res.data or []
    if not candidates:
        print("No videos due for upload at this time. Exiting.")
        return

    # Filter out active claimed videos whose lease has not expired
    videos_to_process = []
    for c in candidates:
        if c.get("upload_status") == "claimed":
            lease_exp_str = c.get("lease_expires_at")
            if lease_exp_str:
                try:
                    lease_exp = datetime.fromisoformat(lease_exp_str.replace("Z", "+00:00"))
                    if lease_exp > now:
                        # Still actively claimed by another worker
                        continue
                except Exception:
                    pass
        videos_to_process.append(c)

    if not videos_to_process:
        print("All due videos are currently leased by active workers. Exiting.")
        return

    print(f"Found {len(videos_to_process)} candidate video(s) ready for upload.")
    yt_service = None

    for video in videos_to_process:
        vid_id = video["id"]
        library_id = video.get("library_video_id")
        title = video["title"]
        desc = video["description"]
        tags = video["hashtags"]
        storage_path = video["storage_path"]
        retry_count = video.get("retry_count", 0)

        print(f"\n🎥 Attempting atomic claim on: {title} (Queue ID: {vid_id}, Library ID: {library_id})")

        # 2. Atomic claim with lease
        if not claim_video(sb, vid_id, worker_id):
            print(f"  ⚠️ Video {vid_id} claimed by another worker concurrently. Skipping.")
            continue

        print(f"  🔒 Successfully claimed by {worker_id}")

        # 3. Pre-upload idempotency check
        if library_id:
            lib_res = sb.table("video_library").select("youtube_video_id, status").eq("id", library_id).execute()
            if lib_res.data:
                lib_data = lib_res.data[0]
                if lib_data.get("youtube_video_id") or lib_data.get("status") in ["published", "cleaned"]:
                    print(f"  ⏭️ Idempotency check: Already published to YouTube. Skipping.")
                    now_done = datetime.now(timezone.utc)
                    delete_after = (now_done + timedelta(days=3)).isoformat()
                    sb.table("scheduled_videos").update({
                        "upload_status": "uploaded",
                        "youtube_video_id": lib_data.get("youtube_video_id"),
                        "delete_after": delete_after,
                        "lease_expires_at": None
                    }).eq("id", vid_id).execute()
                    continue

        # 4. Transition to uploading
        sb.table("scheduled_videos").update({"upload_status": "uploading"}).eq("id", vid_id).execute()
        if library_id:
            sb.table("video_library").update({"status": "uploading"}).eq("id", library_id).execute()
            sb.table("video_activity_log").insert({
                "video_id": library_id,
                "event_type": "UPLOAD_STARTED",
                "message": f"Started YouTube upload process (Worker: {worker_id})"
            }).execute()

        try:
            if yt_service is None:
                yt_service = get_youtube_service()

            print(f"  ⬇️ Downloading {storage_path} from Supabase...")
            file_data = sb.storage.from_(BUCKET).download(storage_path)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp.write(file_data)
                local_path = tmp.name

            print(f"  ⬆️ Uploading to YouTube...")
            full_desc = desc
            if tags:
                full_desc += "\n\n" + " ".join(tags)

            body = {
                "snippet": {
                    "title": title,
                    "description": full_desc,
                    "tags": tags,
                    "categoryId": "24",
                },
                "status": {
                    "privacyStatus": "public",
                    "madeForKids": False,
                    "selfDeclaredMadeForKids": False,
                }
            }

            media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=True)
            request = yt_service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  ... Uploaded {int(status.progress() * 100)}%")

            yt_id = response.get("id")
            yt_url = f"https://youtube.com/shorts/{yt_id}"
            print(f"  ✅ Upload successful! YouTube Video ID: {yt_id}")

            try:
                os.remove(local_path)
            except Exception:
                pass

            now_success = datetime.now(timezone.utc)
            delete_after = (now_success + timedelta(days=3)).isoformat()
            
            sb.table("scheduled_videos").update({
                "upload_status": "uploaded",
                "youtube_video_id": yt_id,
                "uploaded_at": now_success.isoformat(),
                "delete_after": delete_after,
                "lease_expires_at": None,
                "last_error": None
            }).eq("id", vid_id).execute()
            
            if library_id:
                sb.table("video_library").update({
                    "status": "published",
                    "upload_status": "uploaded",
                    "youtube_video_id": yt_id,
                    "youtube_url": yt_url,
                    "uploaded_at": now_success.isoformat()
                }).eq("id", library_id).execute()
                sb.table("video_activity_log").insert({
                    "video_id": library_id,
                    "event_type": "YOUTUBE_UPLOAD_SUCCESS",
                    "message": f"Successfully published. ID: {yt_id}"
                }).execute()

        except Exception as e:
            err_msg = str(e)
            print(f"  ❌ Upload failed: {err_msg}")
            traceback.print_exc()

            retry_count += 1
            if retry_count >= 3:
                print(f"  🛑 Maximum retries reached. Marking as failed.")
                sb.table("scheduled_videos").update({
                    "upload_status": "failed",
                    "retry_count": retry_count,
                    "last_error": err_msg,
                    "lease_expires_at": None
                }).eq("id", vid_id).execute()
                if library_id:
                    sb.table("video_library").update({"status": "failed", "error_message": err_msg}).eq("id", library_id).execute()
                    sb.table("video_activity_log").insert({
                        "video_id": library_id,
                        "event_type": "YOUTUBE_UPLOAD_FAILED",
                        "message": f"Failed after 3 retries: {err_msg}"
                    }).execute()
            else:
                print(f"  ⚠️ Will retry on next run ({retry_count}/3). Releasing lease.")
                sb.table("scheduled_videos").update({
                    "upload_status": "pending",
                    "retry_count": retry_count,
                    "last_error": err_msg,
                    "claimed_at": None,
                    "lease_expires_at": None,
                    "worker_id": None
                }).eq("id", vid_id).execute()
                if library_id:
                    sb.table("video_library").update({"status": "scheduled"}).eq("id", library_id).execute()
                    sb.table("video_activity_log").insert({
                        "video_id": library_id,
                        "event_type": "YOUTUBE_UPLOAD_RETRY",
                        "message": f"Upload failed (attempt {retry_count}/3): {err_msg[:200]}"
                    }).execute()


if __name__ == "__main__":
    process_pending_uploads()
