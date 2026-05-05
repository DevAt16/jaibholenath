from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
import csv


NATIONAL_SUMMARY_SQL = """
WITH task_totals AS (
    SELECT COALESCE(SUM(result_count), 0) AS total_discovered_candidates
    FROM temple_search_tasks
    WHERE status = 'done'
),
candidate_totals AS (
    SELECT
        COUNT(*) AS unique_google_place_ids,
        COUNT(*) FILTER (WHERE confidence = 'high') AS high_confidence_shiva,
        COUNT(*) FILTER (WHERE confidence = 'medium') AS medium_confidence_shiva_candidates,
        COUNT(*) FILTER (WHERE confidence = 'low') AS low_confidence_possible_temples
    FROM temple_candidates
)
SELECT
    'India' AS country,
    'Google Places API' AS source,
    task_totals.total_discovered_candidates,
    candidate_totals.unique_google_place_ids,
    candidate_totals.high_confidence_shiva,
    candidate_totals.medium_confidence_shiva_candidates,
    candidate_totals.low_confidence_possible_temples,
    CASE
        WHEN task_totals.total_discovered_candidates > candidate_totals.unique_google_place_ids
        THEN task_totals.total_discovered_candidates - candidate_totals.unique_google_place_ids
        ELSE 0
    END AS duplicates_removed,
    'discovery_count_not_final_cultural_count' AS status
FROM task_totals
CROSS JOIN candidate_totals;
"""

STATE_COUNTS_SQL = """
SELECT
    COALESCE(state, 'Unknown') AS state,
    COUNT(*) AS unique_google_place_ids,
    COUNT(*) FILTER (WHERE confidence = 'high') AS high_confidence_shiva,
    COUNT(*) FILTER (WHERE confidence = 'medium') AS medium_confidence_shiva_candidates,
    COUNT(*) FILTER (WHERE confidence = 'low') AS low_confidence_possible_temples
FROM temple_candidates
GROUP BY COALESCE(state, 'Unknown')
ORDER BY state;
"""

DISTRICT_COUNTS_SQL = """
SELECT
    COALESCE(state, 'Unknown') AS state,
    COALESCE(district, 'Unknown') AS district,
    COUNT(*) AS unique_google_place_ids,
    COUNT(*) FILTER (WHERE confidence = 'high') AS high_confidence_shiva,
    COUNT(*) FILTER (WHERE confidence = 'medium') AS medium_confidence_shiva_candidates,
    COUNT(*) FILTER (WHERE confidence = 'low') AS low_confidence_possible_temples
FROM temple_candidates
GROUP BY COALESCE(state, 'Unknown'), COALESCE(district, 'Unknown')
ORDER BY state, district;
"""

CANDIDATE_EXPORT_SQL = """
SELECT
    google_place_id,
    google_maps_uri,
    discovered_name,
    discovered_address,
    latitude,
    longitude,
    COALESCE(state, 'Unknown') AS state,
    COALESCE(district, 'Unknown') AS district,
    source_query,
    confidence,
    confidence_score,
    classification_reason,
    first_seen_at,
    last_seen_at
FROM temple_candidates
ORDER BY
    CASE confidence
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        ELSE 3
    END,
    confidence_score DESC,
    state,
    district,
    discovered_name
LIMIT %s;
"""


def cursor_rows_as_dicts(cursor) -> list[dict[str, object]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_report_queries(
    conn,
    *,
    include_candidates: bool = False,
    candidate_limit: int = 5000,
) -> dict[str, list[dict[str, object]]]:
    reports: dict[str, list[dict[str, object]]] = {}
    with conn.cursor() as cursor:
        cursor.execute(NATIONAL_SUMMARY_SQL)
        reports["national_summary"] = cursor_rows_as_dicts(cursor)

        cursor.execute(STATE_COUNTS_SQL)
        reports["state_counts"] = cursor_rows_as_dicts(cursor)

        cursor.execute(DISTRICT_COUNTS_SQL)
        reports["district_counts"] = cursor_rows_as_dicts(cursor)

        if include_candidates:
            cursor.execute(CANDIDATE_EXPORT_SQL, (candidate_limit,))
            reports["candidate_review"] = cursor_rows_as_dicts(cursor)

    return reports
