CREATE TABLE IF NOT EXISTS places_monthly_budgets (
    account_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    billing_month CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    sku VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    request_ceiling INT UNSIGNED NOT NULL,
    accounted_external_usage INT UNSIGNED NOT NULL,
    external_reserve INT UNSIGNED NOT NULL,
    reserved_requests INT UNSIGNED NOT NULL DEFAULT 0,
    usage_checked_at DATETIME(6) NOT NULL,
    PRIMARY KEY (account_key, billing_month, sku),
    CHECK (request_ceiling <= 30000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS places_request_reservations (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    billing_month CHAR(7) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    sku VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    task_id BIGINT,
    reserved_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_places_reservations_budget (account_key, billing_month, sku),
    FOREIGN KEY (account_key, billing_month, sku)
        REFERENCES places_monthly_budgets (account_key, billing_month, sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
