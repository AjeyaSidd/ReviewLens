-- 001_init.sql — Foundation schema for App Review Intelligence

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- catalog_apps: Registry of apps being tracked
-- ============================================================
CREATE TABLE catalog_apps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    country         CHAR(2) NOT NULL DEFAULT 'in',
    play_package    TEXT,
    ios_app_id      TEXT,
    is_active       BOOLEAN DEFAULT true,
    scrape_status   TEXT DEFAULT 'pending'
                        CHECK (scrape_status IN ('pending', 'running', 'ready', 'failed')),
    last_synced_at  TIMESTAMPTZ,
    review_count    INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),

    -- At least one store identifier must be provided
    CONSTRAINT at_least_one_store CHECK (play_package IS NOT NULL OR ios_app_id IS NOT NULL)
);

-- ============================================================
-- reviews: Normalized reviews from both stores
-- ============================================================
CREATE TABLE reviews (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_app_id      UUID NOT NULL REFERENCES catalog_apps(id) ON DELETE CASCADE,
    platform            TEXT NOT NULL CHECK (platform IN ('play_store', 'app_store')),
    platform_review_id  TEXT NOT NULL,
    rating              SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title               TEXT DEFAULT '',
    body                TEXT DEFAULT '',
    review_date         DATE,
    language            TEXT,
    app_version         TEXT,
    sentiment_label     TEXT CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    sentiment_score     FLOAT,
    embedding           vector(1536),
    scraped_at          TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate reviews per app+platform
    UNIQUE (catalog_app_id, platform, platform_review_id)
);

-- ============================================================
-- daily_rollups: Pre-aggregated daily metrics per app
-- ============================================================
CREATE TABLE daily_rollups (
    catalog_app_id  UUID NOT NULL REFERENCES catalog_apps(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    review_count    INT DEFAULT 0,
    avg_rating      FLOAT,
    avg_sentiment   FLOAT,
    star_1          INT DEFAULT 0,
    star_2          INT DEFAULT 0,
    star_3          INT DEFAULT 0,
    star_4          INT DEFAULT 0,
    star_5          INT DEFAULT 0,

    PRIMARY KEY (catalog_app_id, date)
);

-- ============================================================
-- Indexes
-- ============================================================

-- Speed up queries filtering by app + date range
CREATE INDEX idx_reviews_app_date ON reviews (catalog_app_id, review_date DESC);

-- Speed up queries filtering by app + rating
CREATE INDEX idx_reviews_app_rating ON reviews (catalog_app_id, rating);

-- HNSW index for fast approximate nearest-neighbor search on embeddings
CREATE INDEX idx_reviews_embedding_hnsw ON reviews
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
