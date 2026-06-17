-- Open Aura — minimal local schema.
-- Just enough for a single local user + scored sessions. The hosted edition
-- uses VibeLevel's full User table; OSS needs only these columns.
-- Applied automatically by docker-compose (mounted into the Postgres init dir).

-- Minimal user (TEXT id so the default local user 'local' works without UUIDs).
CREATE TABLE IF NOT EXISTS "User" (
    id               TEXT PRIMARY KEY,
    email            TEXT,
    "firstName"      TEXT,
    "lastName"       TEXT,
    display_name     TEXT,
    aura_handle      TEXT UNIQUE,
    aura_visibility  TEXT NOT NULL DEFAULT 'private',
    aura_likes_count INTEGER NOT NULL DEFAULT 0
);

-- One row per scored session. `id` is auto-generated — the scorer's upsert
-- omits it and relies on this default; dedup is on (user_id, fingerprint).
CREATE TABLE IF NOT EXISTS "AuraSession" (
    id                       TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id                  TEXT NOT NULL REFERENCES "User"(id),
    fingerprint              TEXT NOT NULL,
    source                   TEXT,
    modality                 TEXT,
    title                    TEXT,
    evidence                 JSONB,
    aura_score               DOUBLE PRECISION,
    aura_level               TEXT,
    archetype                TEXT,
    dimension_scores         JSONB,
    cards                    JSONB,
    human_contribution_label TEXT,
    engagement_level         TEXT,
    model_version            TEXT,
    telemetry                JSONB,
    ingested_via             TEXT,
    status                   TEXT NOT NULL DEFAULT 'scored',
    started_at               TIMESTAMPTZ,
    ended_at                 TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS aura_session_user_idx ON "AuraSession" (user_id, status);

-- The single local user (matches AURA_LOCAL_USER_ID default 'local').
INSERT INTO "User" (id, display_name, aura_visibility)
VALUES ('local', 'Local Builder', 'private')
ON CONFLICT (id) DO NOTHING;
