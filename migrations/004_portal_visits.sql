-- MySQL 8.0.16+ / MariaDB 10.6+, independent of discovery tables.
CREATE TABLE IF NOT EXISTS portal_visit_sessions (
    session_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    recorded_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS portal_visit_totals (
    singleton TINYINT PRIMARY KEY DEFAULT 1 CHECK (singleton = 1),
    total BIGINT NOT NULL DEFAULT 0 CHECK (total >= 0)
) ENGINE=InnoDB;
INSERT INTO portal_visit_totals (singleton, total) VALUES (1, 0)
ON DUPLICATE KEY UPDATE singleton = 1;
