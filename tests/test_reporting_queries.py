import sqlite3

from shiva_discovery.reporting import (
    DISTRICT_COUNTS_SQL,
    NATIONAL_SUMMARY_SQL,
    STATE_COUNTS_SQL,
)


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE temple_search_tasks (
            status TEXT NOT NULL,
            result_count INTEGER NOT NULL
        );

        CREATE TABLE temple_candidates (
            google_place_id TEXT NOT NULL,
            confidence TEXT NOT NULL,
            state TEXT,
            district TEXT
        );
        """
    )
    return conn


def test_national_summary_query_reports_discovery_not_census_counts():
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO temple_search_tasks (status, result_count) VALUES (?, ?);",
        [("done", 5), ("done", 4), ("failed", 20)],
    )
    conn.executemany(
        """
        INSERT INTO temple_candidates (google_place_id, confidence, state, district)
        VALUES (?, ?, ?, ?);
        """,
        [
            ("p1", "high", "Maharashtra", "Pune"),
            ("p2", "high", "Maharashtra", "Pune"),
            ("p3", "medium", "Gujarat", "Gir Somnath"),
            ("p4", "low", "Gujarat", "Gir Somnath"),
        ],
    )

    row = conn.execute(NATIONAL_SUMMARY_SQL).fetchone()

    assert row == (
        "India",
        "Google Places API",
        9,
        4,
        2,
        1,
        1,
        5,
        "discovery_count_not_final_cultural_count",
    )


def test_state_and_district_queries_group_unique_candidates_by_confidence():
    conn = _make_conn()
    conn.executemany(
        """
        INSERT INTO temple_candidates (google_place_id, confidence, state, district)
        VALUES (?, ?, ?, ?);
        """,
        [
            ("p1", "high", "Maharashtra", "Pune"),
            ("p2", "medium", "Maharashtra", "Pune"),
            ("p3", "low", "Maharashtra", "Nashik"),
            ("p4", "high", "Gujarat", "Gir Somnath"),
        ],
    )

    state_rows = conn.execute(STATE_COUNTS_SQL).fetchall()
    district_rows = conn.execute(DISTRICT_COUNTS_SQL).fetchall()

    assert ("Gujarat", 1, 1, 0, 0) in state_rows
    assert ("Maharashtra", 3, 1, 1, 1) in state_rows
    assert ("Maharashtra", "Pune", 2, 1, 1, 0) in district_rows
    assert ("Maharashtra", "Nashik", 1, 0, 0, 1) in district_rows
