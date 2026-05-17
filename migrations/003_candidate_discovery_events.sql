CREATE TABLE IF NOT EXISTS candidate_discovery_events (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL REFERENCES temple_candidates(id) ON DELETE CASCADE,
    google_place_id TEXT NOT NULL,
    search_task_id BIGINT REFERENCES temple_search_tasks(id) ON DELETE SET NULL,
    source_location_id BIGINT REFERENCES india_locations(id) ON DELETE SET NULL,
    source_location_type TEXT,
    source_location_name TEXT,
    state_name TEXT,
    district_name TEXT,
    keyword TEXT,
    search_query TEXT NOT NULL,
    search_level TEXT,
    result_position INTEGER CHECK (
        result_position IS NULL OR result_position >= 1
    ),
    discovered_name TEXT NOT NULL,
    discovered_address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    google_maps_uri TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_candidate_discovery_events_task_place
    ON candidate_discovery_events(search_task_id, google_place_id)
    WHERE search_task_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_candidate_discovery_events_candidate
    ON candidate_discovery_events(candidate_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_candidate_discovery_events_place
    ON candidate_discovery_events(google_place_id);

CREATE INDEX IF NOT EXISTS idx_candidate_discovery_events_location
    ON candidate_discovery_events(source_location_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_candidate_discovery_events_level
    ON candidate_discovery_events(search_level, observed_at);
