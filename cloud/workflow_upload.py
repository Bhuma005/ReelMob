"""
workflow_upload.py  —  Cloud worker script designed to run in GitHub Actions.

What it does:
  1. Polls Supabase for 'pending' videos where schedule_time <= NOW().
  2. Downloads the video from Supabase Storage to a temporary runner space.
  3. Uploads the video to YouTube via the Data API using the refresh token.
  4. Updates the DB (status='uploaded', sets delete_after to now + 3 days).
  5. Handles failures gracefully (retries up to 3 times before setting 'failed').
"""

import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Required for YouTube API
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Please run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from cloud.cloud_auth import get_supabase_client, get_youtube_creds

BUCKET = "reelgrab-videos"


def get_youtube_service():
    """Initialises the YouTube Data API client using our unified credentials."""
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


def process_pending_uploads():
    sb = get_supabase_client()
    now_utc = datetime.now(timezone.utc).isoformat()

    print(f"[{now_utc}] Checking for pending uploads due before now...")

    # 1. Fetch pending videos due for upload
    res = sb.table("scheduled_videos").select("*") \
            .eq("upload_status", "pending") \
            .lte("schedule_time", now_utc) \
            .execute()
    
    videos = res.data
    if not videos:
        print("No videos due for upload at this time. Exiting.")
        return

    print(f"Found {len(videos)} video(s) ready for upload.")
    yt_service = get_youtube_service()

    for video in videos:
        vid_id = video["id"]
        library_id = video.get("library_video_id")
        title = video["title"]
        desc = video["description"]
        tags = video["hashtags"]
        storage_path = video["storage_path"]
        retry_count = video.get("retry_count", 0)

        print(f"\n🎥 Processing: {title} (Queue ID: {vid_id}, Library ID: {library_id})")
        
        if library_id:
            lib_res = sb.table("video_library").select("youtube_video_id, status").eq("id", library_id).execute()
            if lib_res.data:
                lib_data = lib_res.data[0]
                if lib_data.get("youtube_video_id") or lib_data.get("status") in ["published", "delete_pending", "cleaned"]:
                    print(f"  ⏭️ Idempotency check: Already published to YouTube. Skipping.")
                    now = datetime.now(timezone.utc)
                    delete_after = (now + timedelta(days=3)).isoformat()
                    sb.table("scheduled_videos").update({
                        "upload_status": "uploaded",
                        "delete_after": delete_after
                    }).eq("id", vid_id).execute()
                    continue

        # Mark as uploading
        sb.table("scheduled_videos").update({"upload_status": "uploading"}).eq("id", vid_id).execute()
        if library_id:
            sb.table("video_library").update({"status": "uploading"}).eq("id", library_id).execute()
            sb.table("video_activity_log").insert({
                "video_id": library_id,
                "event_type": "UPLOAD_STARTED",
                "message": "Started YouTube upload process"
            }).execute()

        try:
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

            os.remove(local_path)

            now = datetime.now(timezone.utc)
            delete_after = (now + timedelta(days=3)).isoformat()
            
            sb.table("scheduled_videos").update({
                "upload_status": "uploaded",
                "youtube_video_id": yt_id,
                "uploaded_at": now.isoformat(),
                "delete_after": delete_after,
                "last_error": None
            }).eq("id", vid_id).execute()
            
            if library_id:
                sb.table("video_library").update({
                    "status": "published",
                    "upload_status": "uploaded",
                    "youtube_video_id": yt_id,
                    "youtube_url": yt_url,
                    "uploaded_at": now.isoformat()
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
                    "last_error": err_msg
                }).eq("id", vid_id).execute()
                if library_id:
                    sb.table("video_library").update({"status": "failed", "error_message": err_msg}).eq("id", library_id).execute()
                    sb.table("video_activity_log").insert({
                        "video_id": library_id,
                        "event_type": "YOUTUBE_UPLOAD_FAILED",
                        "message": f"Failed after 3 retries: {err_msg}"
                    }).execute()
            else:
                print(f"  ⚠️ Will retry on next run ({retry_count}/3).")
                sb.table("scheduled_videos").update({
                    "upload_status": "pending",
                    "retry_count": retry_count,
                    "last_error": err_msg
                }).eq("id", vid_id).execute()
                if library_id:
                    sb.table("video_library").update({"status": "scheduled"}).eq("id", library_id).execute()

if __name__ == "__main__":
    process_pending_uploads()
