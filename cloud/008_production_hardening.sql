-- =============================================================
-- Migration 008: Production Hardening & Authoritative Schemas
-- Adds durable jobs table, atomic claiming to scheduled_videos,
-- expanded state machine constraints, and performance indexes.
-- =============================================================

-- 1. Create durable jobs table for all asynchronous operations
CREATE TABLE IF NOT EXISTS jobs (
    id                TEXT PRIMARY KEY,
    job_type          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (lower(status) IN ('queued', 'pending', 'running', 'processing', 'completed', 'failed', 'cancelled')),
    progress          INT NOT NULL DEFAULT 0,
    current_step      TEXT DEFAULT 'Queued for processing',
    input_reference   JSONB DEFAULT '{}'::jsonb,
    result_reference  JSONB DEFAULT '{}'::jsonb,
    error_code        TEXT,
    error_message     TEXT,
    attempt_count     INT NOT NULL DEFAULT 0,
    worker_id         TEXT,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_type ON jobs(status, job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at_desc ON jobs(created_at DESC);

-- Trigger for updated_at on jobs
DROP TRIGGER IF EXISTS update_jobs_modtime ON jobs;
CREATE TRIGGER update_jobs_modtime
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();

-- Enable RLS on jobs
ALTER TABLE IF EXISTS jobs ENABLE ROW LEVEL SECURITY;


-- 2. Add atomic claim & lease fields to scheduled_videos
ALTER TABLE scheduled_videos 
ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS worker_id TEXT;

-- Drop and recreate the upload_status check constraint to include 'claimed' and 'cancelled'
DO $$
BEGIN
    ALTER TABLE scheduled_videos DROP CONSTRAINT IF EXISTS scheduled_videos_upload_status_check;
    ALTER TABLE scheduled_videos 
    ADD CONSTRAINT scheduled_videos_upload_status_check 
    CHECK (upload_status IN ('pending', 'claimed', 'uploading', 'uploaded', 'failed', 'cancelled'));
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Constraint update skipped or already applied: %', SQLERRM;
END $$;

-- Index for atomic claiming by workers
CREATE INDEX IF NOT EXISTS idx_sv_atomic_claim
ON scheduled_videos (upload_status, schedule_time, lease_expires_at);


-- 3. Expand video_library status constraints for authoritative state machine
DO $$
BEGIN
    ALTER TABLE video_library DROP CONSTRAINT IF EXISTS video_library_status_check;
    ALTER TABLE video_library 
    ADD CONSTRAINT video_library_status_check 
    CHECK (status IN (
        'created', 'downloading', 'downloaded', 'processing',
        'ready', 'scheduled', 'uploading', 'published',
        'delete_pending', 'cleaned', 'failed'
    ));
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Constraint update skipped or already applied: %', SQLERRM;
END $$;

-- Search indexes for library queries
CREATE INDEX IF NOT EXISTS idx_video_library_youtube_id ON video_library(youtube_video_id) WHERE youtube_video_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_video_library_hashtags ON video_library USING GIN (hashtags);
