from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from shiva_discovery.db import connect


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _count_backfillable(conn, *, location_type: str | None) -> int:
    location_filter = ""
    params: tuple[object, ...] = ()
    if location_type:
        location_filter = "AND loc.location_type = %s AND loc.is_active = TRUE"
        params = (location_type,)

    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM temple_candidates AS candidate
            JOIN india_locations AS loc ON loc.id = candidate.source_location_id
            LEFT JOIN temple_search_tasks AS task
              ON task.location_id = candidate.source_location_id
             AND task.search_query = candidate.source_query
            LEFT JOIN candidate_discovery_events AS event
              ON event.candidate_id = candidate.id
             AND event.search_query = candidate.source_query
             AND event.source_location_id = candidate.source_location_id
            WHERE candidate.source_location_id IS NOT NULL
              AND candidate.source_query IS NOT NULL
              AND event.id IS NULL
              {location_filter};
            """,
            params,
        )
        return int(cursor.fetchone()[0])


def _backfill(conn, *, location_type: str | None, limit: int | None) -> int:
    location_filter = ""
    params: list[object] = []
    if location_type:
        location_filter = "AND loc.location_type = %s AND loc.is_active = TRUE"
        params.append(location_type)

    limit_sql = ""
    if limit is not None:
        limit_sql = "LIMIT %s"
        params.append(limit)

    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            WITH candidate_rows AS (
                SELECT
                    candidate.id AS candidate_id,
                    candidate.google_place_id,
                    task.id AS search_task_id,
                    candidate.source_location_id,
                    loc.location_type AS source_location_type,
                    loc.name AS source_location_name,
                    candidate.state AS state_name,
                    candidate.district AS district_name,
                    task.keyword,
                    candidate.source_query,
                    COALESCE(task.search_level, loc.location_type) AS search_level,
                    candidate.discovered_name,
                    candidate.discovered_address,
                    candidate.latitude,
                    candidate.longitude,
                    candidate.google_maps_uri,
                    candidate.last_seen_at AS observed_at
                FROM temple_candidates AS candidate
                JOIN india_locations AS loc ON loc.id = candidate.source_location_id
                LEFT JOIN temple_search_tasks AS task
                  ON task.location_id = candidate.source_location_id
                 AND task.search_query = candidate.source_query
                LEFT JOIN candidate_discovery_events AS event
                  ON event.candidate_id = candidate.id
                 AND event.search_query = candidate.source_query
                 AND event.source_location_id = candidate.source_location_id
                WHERE candidate.source_location_id IS NOT NULL
                  AND candidate.source_query IS NOT NULL
                  AND event.id IS NULL
                  {location_filter}
                ORDER BY candidate.id
                {limit_sql}
            )
            INSERT INTO candidate_discovery_events (
                candidate_id,
                google_place_id,
                search_task_id,
                source_location_id,
                source_location_type,
                source_location_name,
                state_name,
                district_name,
                keyword,
                search_query,
                search_level,
                result_position,
                discovered_name,
                discovered_address,
                latitude,
                longitude,
                google_maps_uri,
                observed_at
            )
            SELECT
                candidate_id,
                google_place_id,
                search_task_id,
                source_location_id,
                source_location_type,
                source_location_name,
                state_name,
                district_name,
                keyword,
                source_query,
                search_level,
                NULL,
                discovered_name,
                discovered_address,
                latitude,
                longitude,
                google_maps_uri,
                observed_at
            FROM candidate_rows
            ON CONFLICT (search_task_id, google_place_id)
                WHERE search_task_id IS NOT NULL
            DO UPDATE
            SET candidate_id = EXCLUDED.candidate_id,
                source_location_id = EXCLUDED.source_location_id,
                source_location_type = EXCLUDED.source_location_type,
                source_location_name = EXCLUDED.source_location_name,
                state_name = EXCLUDED.state_name,
                district_name = EXCLUDED.district_name,
                keyword = EXCLUDED.keyword,
                search_query = EXCLUDED.search_query,
                search_level = EXCLUDED.search_level,
                discovered_name = EXCLUDED.discovered_name,
                discovered_address = EXCLUDED.discovered_address,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                google_maps_uri = COALESCE(
                    EXCLUDED.google_maps_uri,
                    candidate_discovery_events.google_maps_uri
                ),
                observed_at = EXCLUDED.observed_at;
            """,
            tuple(params),
        )
        return int(cursor.rowcount)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill candidate_discovery_events from each candidate's current "
            "source attribution. This is not full historical attribution."
        )
    )
    parser.add_argument(
        "--location-type",
        choices=[
            "state",
            "district",
            "sub_district",
            "city",
            "town",
            "village",
            "urban_local_body",
        ],
        help="Restrict backfill to candidates currently attributed to one active location type.",
    )
    parser.add_argument(
        "--district-only",
        action="store_true",
        help="Shortcut for --location-type district.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=1000,
        help="Maximum candidate events to backfill. Defaults to 1000 for safety.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all matching candidates instead of using --limit.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts without inserting.")
    args = parser.parse_args()

    if args.district_only and args.location_type and args.location_type != "district":
        parser.error("--district-only cannot be combined with a non-district --location-type.")
    location_type = "district" if args.district_only else args.location_type
    limit = None if args.all else args.limit

    with connect() as conn:
        total = _count_backfillable(conn, location_type=location_type)
        print(f"Backfillable current candidate attributions: {total}")
        if args.dry_run:
            return 0
        with conn.transaction():
            inserted = _backfill(conn, location_type=location_type, limit=limit)

    scope = f" for active {location_type} locations" if location_type else ""
    limit_note = "all" if limit is None else str(limit)
    print(f"Backfilled {inserted} candidate discovery events{scope} (limit {limit_note}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
