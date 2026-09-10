-- ReelGrab Cloud Infrastructure Additions
-- Run this in your Supabase SQL Editor

-- 1. Create a composite index to drastically speed up automation worker polling performance.
CREATE INDEX IF NOT EXISTS idx_scheduled_videos_worker_poll
ON scheduled_videos(upload_status, schedule_time);
