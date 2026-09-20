-- =============================================================
-- Migration 007: Add oauth_tokens table
-- Stores persistent OAuth tokens in Supabase across ephemeral restarts
-- =============================================================

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE,  -- e.g. 'youtube', 'instagram', 'facebook'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT DEFAULT 'Bearer',
    expires_at TIMESTAMPTZ,
    channel_name TEXT,
    scope TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast provider lookups
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_provider 
ON oauth_tokens (provider);

-- -------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- Restricts anonymous public API access while preserving full service-key backend access.
-- In Supabase, the service_role key automatically bypasses RLS.
-- -------------------------------------------------------------
ALTER TABLE IF EXISTS oauth_tokens ENABLE ROW LEVEL SECURITY;
