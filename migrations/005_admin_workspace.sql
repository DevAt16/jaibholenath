CREATE TABLE IF NOT EXISTS admin_users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(254) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admin_sessions (
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  csrf_token CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  expires_at DATETIME(3) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES admin_users(id),
  INDEX (expires_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admin_login_limits (
  bucket_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  attempts INT UNSIGNED NOT NULL,
  reset_at DATETIME(3) NOT NULL,
  INDEX (reset_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admin_candidates (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  google_place_id VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
  name VARCHAR(500) NOT NULL,
  source_state VARCHAR(255) NOT NULL,
  source_district VARCHAR(255) NOT NULL,
  confidence VARCHAR(20) NOT NULL,
  snapshot JSON NOT NULL,
  snapshot_sha256 CHAR(64) CHARACTER SET ascii NOT NULL,
  imported_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  status VARCHAR(32) NOT NULL DEFAULT 'unreviewed',
  revision INT UNSIGNED NOT NULL DEFAULT 0,
  updated_at DATETIME(3) NULL,
  INDEX (source_state, source_district, status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admin_record_revisions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  candidate_id BIGINT UNSIGNED NOT NULL,
  revision INT UNSIGNED NOT NULL,
  author_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(32) NOT NULL,
  methodology VARCHAR(50) NOT NULL,
  document JSON NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  UNIQUE KEY candidate_revision (candidate_id, revision),
  FOREIGN KEY (candidate_id) REFERENCES admin_candidates(id),
  FOREIGN KEY (author_id) REFERENCES admin_users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS admin_review_events (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  candidate_id BIGINT UNSIGNED NOT NULL,
  revision_id BIGINT UNSIGNED NOT NULL,
  author_id BIGINT UNSIGNED NOT NULL,
  previous_status VARCHAR(32) NOT NULL,
  new_status VARCHAR(32) NOT NULL,
  reason TEXT NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  FOREIGN KEY (candidate_id) REFERENCES admin_candidates(id),
  FOREIGN KEY (revision_id) REFERENCES admin_record_revisions(id),
  FOREIGN KEY (author_id) REFERENCES admin_users(id)
) ENGINE=InnoDB;
