def get_dashboard_videos():
    from cloud.cloud_auth import get_supabase_client
    try:
        sb = get_supabase_client()
        res = sb.table("scheduled_videos").select("*").order("schedule_time", desc=True).limit(20).execute()
        videos = res.data
        for v in videos:
            if v.get("storage_path"):
                try:
                    signed = sb.storage.from_("reelgrab-videos").create_signed_url(v["storage_path"], 3600*24)
                    v["public_url"] = signed.get("signedURL") or signed.get("signedUrl") or signed
                except Exception as e:
                    logger.error(f"Failed to generate signed url: {e}")
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Dashboard Videos error: {e}")
        return {"videos": [], "error": str(e)}


@app.delete("/api/dashboard/videos/{video_id}", summary="Delete a video", description="Deletes video from Supabase Storage and DB.")
async 