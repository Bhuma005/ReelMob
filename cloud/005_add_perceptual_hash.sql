-- =============================================================
-- Migration 005: Add Perceptual Hash for Duplicate Detection
-- Stores 64-bit dHash string to identify duplicate & near-duplicate videos
-- =============================================================

-- Add perceptual_hash column to video_library if it does not already exist
ALTER TABLE video_library 
ADD COLUMN IF NOT EXISTS perceptual_hash TEXT;

-- Index on perceptual_hash for fast lookup and deduplication
CREATE INDEX IF NOT EXISTS idx_video_library_perceptual_hash 
ON video_library (perceptual_hash)
WHERE perceptual_hash IS NOT NULL;
