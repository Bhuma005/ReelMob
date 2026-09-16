-- =============================================================
-- Migration 006: Add tags column to video_library
-- Stores text array of custom creator tags for content organization and analytics
-- =============================================================

-- Add tags column to video_library if it does not already exist
ALTER TABLE video_library 
ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';

-- GIN index on tags for fast array containment queries (e.g. tags @> ARRAY['viral'])
CREATE INDEX IF NOT EXISTS idx_video_library_tags 
ON video_library USING GIN (tags);
