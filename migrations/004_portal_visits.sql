-- Separate from discovery data. Tokens are random session hashes, not identities.
CREATE TABLE IF NOT EXISTS portal_visit_sessions (
    session_hash TEXT PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portal_visit_totals (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    total BIGINT NOT NULL DEFAULT 0 CHECK (total >= 0)
);
INSERT INTO portal_visit_totals (singleton, total) VALUES (TRUE, 0)
ON CONFLICT (singleton) DO NOTHING;
