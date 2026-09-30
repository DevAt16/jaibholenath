CREATE TABLE IF NOT EXISTS discovery_expansion_batches (
    run_date DATE PRIMARY KEY,
    budget_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    finished_at DATETIME(6),
    result_json JSON,
    CHECK (status IN ('running', 'completed', 'failed', 'paused'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
