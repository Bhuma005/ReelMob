-- =============================================================
-- Migration 004: ReelsMob Supabase Audit & Hardening
-- Indexes, Constraints, Data Integrity, and Row Level Security
-- =============================================================

-- -------------------------------------------------------------
-- 1. CRITICAL MISSING INDEXES FOR PERFORMANCE & FOREIGN KEYS
-- -------------------------------------------------------------

-- video_library: filter by status (heavily used in /api/dashboard/stats and library tabs)
CREATE INDEX IF NOT EXISTS idx_video_library_status 
ON video_library (status);

-- video_library: order by created_at DESC (used in /api/dashboard/videos pagination)
CREATE INDEX IF NOT EXISTS idx_video_library_created_at_desc 
ON video_library (created_at DESC);

-- video_library: filter by schedule_time
CREATE INDEX IF NOT EXISTS idx_video_library_schedule_time 
ON video_library (schedule_time)
WHERE schedule_time IS NOT NULL;

-- scheduled_videos: foreign key index on library_video_id
-- (PostgreSQL does NOT auto-index foreign keys; prevents full table scans on joins and deletes)
CREATE INDEX IF NOT EXISTS idx_scheduled_videos_library_id 
ON scheduled_videos (library_video_id)
WHERE library_video_id IS NOT NULL;

-- video_activity_log: foreign key index on video_id
CREATE INDEX IF NOT EXISTS idx_video_activity_log_video_id 
ON video_activity_log (video_id);

-- video_activity_log: order by created_at DESC (used in /api/dashboard/logs)
CREATE INDEX IF NOT EXISTS idx_video_activity_log_created_at_desc 
ON video_activity_log (created_at DESC);

-- -------------------------------------------------------------
-- 2. DATA INTEGRITY & DEDUPLICATION CONSTRAINTS
-- -------------------------------------------------------------

-- Prevent duplicate pending queue items for the same library video
CREATE UNIQUE INDEX IF NOT EXISTS idx_sv_unique_pending_library_video 
ON scheduled_videos (library_video_id)
WHERE upload_status = 'pending' AND library_video_id IS NOT NULL;

-- Relax NOT NULL constraint on videos_audit_log.uploaded_at
-- (Prevents workflow_cleanup.py crash if a video was manually queued without uploaded_at)
ALTER TABLE IF EXISTS videos_audit_log 
ALTER COLUMN uploaded_at DROP NOT NULL;

ALTER TABLE IF EXISTS videos_audit_log 
ALTER COLUMN uploaded_at SET DEFAULT now();

-- -------------------------------------------------------------
-- 3. ROW LEVEL SECURITY (RLS) HARDENING
-- Restricts anonymous public API access while preserving full service-key backend access.
-- In Supabase, the service_role key automatically bypasses RLS.
-- Enabling RLS prevents the public 'anon' key from reading/writing creator videos.
-- -------------------------------------------------------------

ALTER TABLE IF EXISTS scheduled_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS video_library ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS video_activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS videos_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS ai_analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS analytics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS historical_shorts_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS posting_slot_scores ENABLE ROW LEVEL SECURITY;
