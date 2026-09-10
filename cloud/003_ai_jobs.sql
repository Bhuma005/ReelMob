-- =============================================================
-- Migration 003: AI Analysis Jobs & Cache
-- =============================================================

CREATE TABLE IF NOT EXISTS ai_analysis_jobs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash   TEXT UNIQUE,
    source_url     TEXT,
    
    status         TEXT NOT NULL DEFAULT 'QUEUED' 
                   CHECK (status IN ('QUEUED','DOWNLOADING','TRANSCRIBING','ANALYZING','GENERATING_METADATA','COMPLETED','FAILED','CANCELLED')),
    
    progress       INT NOT NULL DEFAULT 0,
    current_step   TEXT DEFAULT 'Queued for processing',
    
    result         JSONB DEFAULT '{}'::jsonb,
    error_message  TEXT,
    
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_analysis_jobs_content_hash ON ai_analysis_jobs(content_hash);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_jobs_status ON ai_analysis_jobs(status);

DROP TRIGGER IF EXISTS update_ai_analysis_jobs_modtime ON ai_analysis_jobs;
CREATE TRIGGER update_ai_analysis_jobs_modtime
BEFORE UPDATE ON ai_analysis_jobs
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
