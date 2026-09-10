-- =============================================================
-- ReelGrab Cloud Schema
-- Run once in your Supabase project's SQL editor
-- =============================================================

-- Enable the uuid extension (usually already enabled on Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- TABLE 1: scheduled_videos
-- Holds all videos queued for YouTube upload
-- =============================================================
CREATE TABLE IF NOT EXISTS scheduled_videos (
    id                UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    title             TEXT          NOT NULL,
    description       TEXT          NOT NULL DEFAULT '',
    hashtags          TEXT[]        NOT NULL DEFAULT '{}',
    storage_path      TEXT          NOT NULL,        -- e.g. 'videos/abc123.mp4'
    schedule_time     TIMESTAMPTZ   NOT NULL,        -- exact intended upload time (UTC)
    upload_status     TEXT          NOT NULL DEFAULT 'pending'
                          CHECK (upload_status IN ('pending','uploading','uploaded','failed')),
    youtube_video_id  TEXT,                          -- set after successful upload
    uploaded_at       TIMESTAMPTZ,                   -- set after successful upload
    delete_after      TIMESTAMPTZ,                   -- uploaded_at + interval '3 days'
    retry_count       INT           NOT NULL DEFAULT 0,
    last_error        TEXT,                          -- last failure message
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Index for the upload poller: fast lookup of "due" pending videos
CREATE INDEX IF NOT EXISTS idx_sv_pending_due
    ON scheduled_videos (upload_status, schedule_time)
    WHERE upload_status = 'pending';

-- Index for the cleanup job: fast lookup of "ready to delete" rows
CREATE INDEX IF NOT EXISTS idx_sv_cleanup
    ON scheduled_videos (upload_status, delete_after)
    WHERE upload_status = 'uploaded';

-- =============================================================
-- TABLE 2: videos_audit_log
-- Soft-delete archive — one row per successfully deleted video
-- =============================================================
CREATE TABLE IF NOT EXISTS videos_audit_log (
    id               UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    title            TEXT        NOT NULL,
    youtube_video_id TEXT        NOT NULL,
    uploaded_at      TIMESTAMPTZ NOT NULL,
    deleted_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================
-- HELPER VIEW: surface any 'failed' videos so you notice them
-- =============================================================
CREATE OR REPLACE VIEW failed_videos AS
    SELECT id, title, retry_count, last_error, schedule_time, created_at
    FROM scheduled_videos
    WHERE upload_status = 'failed'
    ORDER BY created_at DESC;

-- =============================================================
-- MIGRATION NOTE (existing local queue → cloud)
-- If you have videos already queued locally, use enqueue.py to
-- re-insert them here + upload their files to Supabase Storage.
-- No manual SQL inserts needed — enqueue.py handles both steps.
-- =============================================================
