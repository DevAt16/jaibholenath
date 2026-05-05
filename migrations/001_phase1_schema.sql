CREATE TABLE IF NOT EXISTS india_locations (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    location_type TEXT NOT NULL CHECK (
        location_type IN (
            'state',
            'district',
            'sub_district',
            'city',
            'town',
            'village',
            'urban_local_body'
        )
    ),
    parent_id BIGINT REFERENCES india_locations(id) ON DELETE SET NULL,
    state_name TEXT,
    district_name TEXT,
    sub_district_name TEXT,
    state_lgd_code TEXT,
    district_lgd_code TEXT,
    sub_district_lgd_code TEXT,
    village_lgd_code TEXT,
    source TEXT NOT NULL DEFAULT 'unknown',
    full_path TEXT,
    search_priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_india_locations_type_active
    ON india_locations(location_type, is_active, search_priority);

CREATE INDEX IF NOT EXISTS idx_india_locations_parent
    ON india_locations(parent_id);

CREATE INDEX IF NOT EXISTS idx_india_locations_state_district
    ON india_locations(state_name, district_name);

CREATE INDEX IF NOT EXISTS idx_india_locations_lgd_codes
    ON india_locations(state_lgd_code, district_lgd_code, sub_district_lgd_code, village_lgd_code);

CREATE TABLE IF NOT EXISTS location_aliases (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES india_locations(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_location_aliases_unique
    ON location_aliases(location_id, normalized_alias);

CREATE TABLE IF NOT EXISTS temple_search_tasks (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES india_locations(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    search_query TEXT NOT NULL,
    search_level TEXT NOT NULL CHECK (
        search_level IN (
            'state',
            'district',
            'sub_district',
            'city',
            'town',
            'village',
            'urban_local_body'
        )
    ),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'done', 'failed', 'skipped')
    ),
    attempts INTEGER NOT NULL DEFAULT 0,
    result_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_temple_search_tasks_location_keyword
    ON temple_search_tasks(location_id, keyword);

CREATE INDEX IF NOT EXISTS idx_temple_search_tasks_pending
    ON temple_search_tasks(status, created_at, id);

CREATE TABLE IF NOT EXISTS temple_candidates (
    id BIGSERIAL PRIMARY KEY,
    google_place_id TEXT NOT NULL UNIQUE,
    discovered_name TEXT NOT NULL,
    discovered_address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    state TEXT,
    district TEXT,
    source_query TEXT,
    source_location_id BIGINT REFERENCES india_locations(id) ON DELETE SET NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    confidence_score NUMERIC(4, 2) NOT NULL CHECK (
        confidence_score >= 0 AND confidence_score <= 1
    ),
    classification_reason TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_temple_candidates_confidence
    ON temple_candidates(confidence);

CREATE INDEX IF NOT EXISTS idx_temple_candidates_state_district
    ON temple_candidates(state, district);

CREATE INDEX IF NOT EXISTS idx_temple_candidates_source_location
    ON temple_candidates(source_location_id);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_india_locations_updated_at ON india_locations;
CREATE TRIGGER trg_india_locations_updated_at
BEFORE UPDATE ON india_locations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_temple_search_tasks_updated_at ON temple_search_tasks;
CREATE TRIGGER trg_temple_search_tasks_updated_at
BEFORE UPDATE ON temple_search_tasks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
