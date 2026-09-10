-- =============================================================
-- ReelGrab Cloud Schema Migration
-- AI Posting Intelligence Upgrade
-- =============================================================

-- =============================================================
-- TABLE: analytics_snapshots
-- Stores historical performance data for published Shorts
-- =============================================================
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id                      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id                TEXT        NOT NULL,
    captured_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    views                   INT         DEFAULT 0,
    likes                   INT         DEFAULT 0,
    comments                INT         DEFAULT 0,
    shares                  INT         DEFAULT 0,
    avg_view_duration       INT         DEFAULT 0, -- in seconds
    avg_percentage_viewed   FLOAT       DEFAULT 0.0,
    subscribers_gained      INT         DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_analytics_video_id ON analytics_snapshots (video_id);

-- =============================================================
-- TABLE: historical_shorts_data
-- Core metadata + performance summary for posting calculations
-- =============================================================
CREATE TABLE IF NOT EXISTS historical_shorts_data (
    id                      UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    youtube_video_id        TEXT        NOT NULL UNIQUE,
    published_at            TIMESTAMPTZ NOT NULL,
    timezone                TEXT        NOT NULL DEFAULT 'UTC',
    day_of_week             INT         NOT NULL, -- 0-6 (Mon-Sun)
    hour                    INT         NOT NULL, -- 0-23
    duration                INT         NOT NULL, -- in seconds
    topic                   TEXT,
    category                TEXT,
    title                   TEXT,
    performance_score       FLOAT       DEFAULT 0.0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================
-- TABLE: posting_slot_scores (Optional cache/audit)
-- Tracks the deterministic scoring logic for historical tracking
-- =============================================================
CREATE TABLE IF NOT EXISTS posting_slot_scores (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_date     DATE        NOT NULL,
    hour            INT         NOT NULL,
    timezone        TEXT        NOT NULL,
    topic           TEXT,
    score           FLOAT       NOT NULL,
    confidence      TEXT        NOT NULL,
    data_points     JSONB       DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
