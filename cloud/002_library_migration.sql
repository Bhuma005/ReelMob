-- =============================================================
-- Migration 002: Video Library and Activity Log
-- =============================================================

CREATE TABLE IF NOT EXISTS video_library (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title              TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    hashtags           TEXT[] NOT NULL DEFAULT '{}',
    source_url         TEXT,
    thumbnail_url      TEXT,
    
    status             TEXT NOT NULL DEFAULT 'created' 
                       CHECK (status IN ('created','scheduled','uploading','published','failed','delete_pending','cleaned')),
    
    upload_status      TEXT,
    
    schedule_time      TIMESTAMPTZ,
    scheduled_at       TIMESTAMPTZ DEFAULT now(),
    uploaded_at        TIMESTAMPTZ,
    
    youtube_video_id   TEXT,
    youtube_url        TEXT,
    
    storage_path       TEXT,
    storage_deleted_at TIMESTAMPTZ,
    
    delete_after       TIMESTAMPTZ,
    error_message      TEXT,
    
    metadata           JSONB DEFAULT '{}'::jsonb,
    
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add library_video_id to scheduled_videos
ALTER TABLE scheduled_videos 
ADD COLUMN IF NOT EXISTS library_video_id UUID REFERENCES video_library(id) ON DELETE SET NULL;

-- Create activity log
CREATE TABLE IF NOT EXISTS video_activity_log (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id    UUID NOT NULL REFERENCES video_library(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Trigger for updated_at on video_library
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_video_library_modtime ON video_library;
CREATE TRIGGER update_video_library_modtime
BEFORE UPDATE ON video_library
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
