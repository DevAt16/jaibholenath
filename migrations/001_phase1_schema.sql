CREATE TABLE IF NOT EXISTS india_locations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    location_type VARCHAR(255) NOT NULL CHECK (
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
    parent_id BIGINT,
    state_name VARCHAR(255),
    district_name VARCHAR(255),
    sub_district_name TEXT,
    state_lgd_code VARCHAR(32),
    district_lgd_code VARCHAR(32),
    sub_district_lgd_code VARCHAR(32),
    village_lgd_code VARCHAR(32),
    source VARCHAR(255) NOT NULL DEFAULT 'unknown',
    full_path TEXT,
    search_priority INTEGER NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    KEY idx_india_locations_type_active (location_type, is_active, search_priority),
    KEY idx_india_locations_parent (parent_id),
    KEY idx_india_locations_state_district (state_name, district_name),
    KEY idx_india_locations_lgd_codes (state_lgd_code, district_lgd_code, sub_district_lgd_code, village_lgd_code),
    FOREIGN KEY (parent_id) REFERENCES india_locations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS location_aliases (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    location_id BIGINT NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL DEFAULT 'manual',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY idx_location_aliases_unique (location_id, normalized_alias),
    FOREIGN KEY (location_id) REFERENCES india_locations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS temple_search_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    location_id BIGINT NOT NULL,
    keyword VARCHAR(255) NOT NULL,
    search_query TEXT NOT NULL,
    search_level VARCHAR(255) NOT NULL CHECK (
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
    status VARCHAR(255) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'done', 'failed', 'skipped')
    ),
    attempts INTEGER NOT NULL DEFAULT 0,
    result_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    UNIQUE KEY idx_temple_search_tasks_location_keyword (location_id, keyword),
    KEY idx_temple_search_tasks_pending (status, created_at, id),
    FOREIGN KEY (location_id) REFERENCES india_locations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS temple_candidates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    google_place_id VARCHAR(255) NOT NULL UNIQUE,
    discovered_name TEXT NOT NULL,
    discovered_address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    state VARCHAR(255),
    district VARCHAR(255),
    source_query TEXT,
    source_location_id BIGINT,
    confidence VARCHAR(255) NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    confidence_score NUMERIC(4, 2) NOT NULL CHECK (
        confidence_score >= 0 AND confidence_score <= 1
    ),
    classification_reason TEXT NOT NULL,
    first_seen_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    last_seen_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_temple_candidates_confidence (confidence),
    KEY idx_temple_candidates_state_district (state, district),
    KEY idx_temple_candidates_source_location (source_location_id),
    FOREIGN KEY (source_location_id) REFERENCES india_locations(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
