import sqlite3

from shiva_discovery.reporting import (
    DISTRICT_COUNTS_SQL,
    NATIONAL_SUMMARY_SQL,
    STATE_COUNTS_SQL,
    run_report_queries,
)


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE temple_search_tasks (
            location_id INTEGER,
            status TEXT NOT NULL,
            result_count INTEGER NOT NULL
        );

        CREATE TABLE india_locations (
            id INTEGER PRIMARY KEY,
            location_type TEXT NOT NULL,
            is_active INTEGER NOT NULL
        );

        CREATE TABLE temple_candidates (
            google_place_id TEXT NOT NULL,
            confidence TEXT NOT NULL,
            state TEXT,
            district TEXT,
            source_location_id INTEGER
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


def test_scoped_reports_use_active_source_location_type():
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO india_locations (id, location_type, is_active) VALUES (?, ?, ?);",
        [
            (1, "district", 1),
            (2, "town", 1),
            (3, "district", 0),
        ],
    )
    conn.executemany(
        "INSERT INTO temple_search_tasks (location_id, status, result_count) VALUES (?, ?, ?);",
        [
            (1, "done", 9),
            (2, "done", 5),
            (3, "done", 4),
            (1, "failed", 20),
        ],
    )
    conn.executemany(
        """
        INSERT INTO temple_candidates (
            google_place_id,
            confidence,
            state,
            district,
            source_location_id
        )
        VALUES (?, ?, ?, ?, ?);
        """,
        [
            ("p1", "high", "Assam", "Bajali", 1),
            ("p2", "medium", "Assam", "Bajali", 1),
            ("p3", "low", "Assam", "Bajali", 2),
            ("p4", "high", "Assam", "Inactive District", 3),
        ],
    )

    reports = run_report_queries(conn, location_type="district")

    assert reports["national_summary"][0]["source"] == (
        "Google Places API (district active locations only)"
    )
    assert reports["national_summary"][0]["total_discovered_candidates"] == 9
    assert reports["national_summary"][0]["unique_google_place_ids"] == 2
    assert reports["national_summary"][0]["high_confidence_shiva"] == 1
    assert reports["national_summary"][0]["medium_confidence_shiva_candidates"] == 1
    assert reports["national_summary"][0]["low_confidence_possible_temples"] == 0
    assert reports["state_counts"] == [
        {
            "state": "Assam",
            "unique_google_place_ids": 2,
            "high_confidence_shiva": 1,
            "medium_confidence_shiva_candidates": 1,
            "low_confidence_possible_temples": 0,
        }
    ]
    assert reports["district_counts"] == [
        {
            "state": "Assam",
            "district": "Bajali",
            "unique_google_place_ids": 2,
            "high_confidence_shiva": 1,
            "medium_confidence_shiva_candidates": 1,
            "low_confidence_possible_temples": 0,
        }
    ]
