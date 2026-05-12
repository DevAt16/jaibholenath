from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
import csv


REPORT_LOCATION_TYPES = {
    "state",
    "district",
    "sub_district",
    "city",
    "town",
    "village",
    "urban_local_body",
}


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


def _validate_location_type(location_type: str | None) -> str | None:
    if location_type is None:
        return None
    if location_type not in REPORT_LOCATION_TYPES:
        valid = ", ".join(sorted(REPORT_LOCATION_TYPES))
        raise ValueError(f"Unsupported report location type {location_type!r}. Use one of: {valid}.")
    return location_type


def _task_totals_sql(location_type: str | None) -> str:
    if location_type is None:
        return """
            SELECT COALESCE(SUM(result_count), 0) AS total_discovered_candidates
            FROM temple_search_tasks
            WHERE status = 'done'
        """

    return f"""
            SELECT COALESCE(SUM(task.result_count), 0) AS total_discovered_candidates
            FROM temple_search_tasks AS task
            JOIN india_locations AS loc ON loc.id = task.location_id
            WHERE task.status = 'done'
              AND loc.is_active = TRUE
              AND loc.location_type = '{location_type}'
        """


def _candidate_from_sql(location_type: str | None) -> str:
    if location_type is None:
        return "temple_candidates AS candidate"

    return f"""
        temple_candidates AS candidate
        JOIN india_locations AS loc ON loc.id = candidate.source_location_id
           AND loc.is_active = TRUE
           AND loc.location_type = '{location_type}'
    """


def national_summary_sql(location_type: str | None = None) -> str:
    location_type = _validate_location_type(location_type)
    source = "Google Places API"
    status = "discovery_count_not_final_cultural_count"
    if location_type:
        label = location_type.replace("_", " ")
        source = f"Google Places API ({label} active locations only)"
        status = f"{location_type}_level_discovery_count_not_final_cultural_count"

    return f"""
WITH task_totals AS (
    {_task_totals_sql(location_type)}
),
candidate_totals AS (
    SELECT
        COUNT(*) AS unique_google_place_ids,
        COUNT(*) FILTER (WHERE candidate.confidence = 'high') AS high_confidence_shiva,
        COUNT(*) FILTER (WHERE candidate.confidence = 'medium') AS medium_confidence_shiva_candidates,
        COUNT(*) FILTER (WHERE candidate.confidence = 'low') AS low_confidence_possible_temples
    FROM {_candidate_from_sql(location_type)}
)
SELECT
    'India' AS country,
    '{source}' AS source,
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
    '{status}' AS status
FROM task_totals
CROSS JOIN candidate_totals;
"""


def state_counts_sql(location_type: str | None = None) -> str:
    location_type = _validate_location_type(location_type)
    return f"""
SELECT
    COALESCE(candidate.state, 'Unknown') AS state,
    COUNT(*) AS unique_google_place_ids,
    COUNT(*) FILTER (WHERE candidate.confidence = 'high') AS high_confidence_shiva,
    COUNT(*) FILTER (WHERE candidate.confidence = 'medium') AS medium_confidence_shiva_candidates,
    COUNT(*) FILTER (WHERE candidate.confidence = 'low') AS low_confidence_possible_temples
FROM {_candidate_from_sql(location_type)}
GROUP BY COALESCE(candidate.state, 'Unknown')
ORDER BY state;
"""


def district_counts_sql(location_type: str | None = None) -> str:
    location_type = _validate_location_type(location_type)
    return f"""
SELECT
    COALESCE(candidate.state, 'Unknown') AS state,
    COALESCE(candidate.district, 'Unknown') AS district,
    COUNT(*) AS unique_google_place_ids,
    COUNT(*) FILTER (WHERE candidate.confidence = 'high') AS high_confidence_shiva,
    COUNT(*) FILTER (WHERE candidate.confidence = 'medium') AS medium_confidence_shiva_candidates,
    COUNT(*) FILTER (WHERE candidate.confidence = 'low') AS low_confidence_possible_temples
FROM {_candidate_from_sql(location_type)}
GROUP BY COALESCE(candidate.state, 'Unknown'), COALESCE(candidate.district, 'Unknown')
ORDER BY state, district;
"""


def candidate_export_sql(location_type: str | None = None) -> str:
    location_type = _validate_location_type(location_type)
    return f"""
SELECT
    candidate.google_place_id,
    candidate.google_maps_uri,
    candidate.discovered_name,
    candidate.discovered_address,
    candidate.latitude,
    candidate.longitude,
    COALESCE(candidate.state, 'Unknown') AS state,
    COALESCE(candidate.district, 'Unknown') AS district,
    candidate.source_query,
    candidate.confidence,
    candidate.confidence_score,
    candidate.classification_reason,
    candidate.first_seen_at,
    candidate.last_seen_at
FROM {_candidate_from_sql(location_type)}
ORDER BY
    CASE candidate.confidence
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        ELSE 3
    END,
    candidate.confidence_score DESC,
    candidate.state,
    candidate.district,
    candidate.discovered_name
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
    location_type: str | None = None,
) -> dict[str, list[dict[str, object]]]:
    location_type = _validate_location_type(location_type)
    reports: dict[str, list[dict[str, object]]] = {}
    cursor = conn.cursor()
    try:
        cursor.execute(national_summary_sql(location_type))
        reports["national_summary"] = cursor_rows_as_dicts(cursor)

        cursor.execute(state_counts_sql(location_type))
        reports["state_counts"] = cursor_rows_as_dicts(cursor)

        cursor.execute(district_counts_sql(location_type))
        reports["district_counts"] = cursor_rows_as_dicts(cursor)

        if include_candidates:
            cursor.execute(candidate_export_sql(location_type), (candidate_limit,))
            reports["candidate_review"] = cursor_rows_as_dicts(cursor)
    finally:
        cursor.close()

    return reports
