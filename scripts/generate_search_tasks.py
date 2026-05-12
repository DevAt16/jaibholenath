from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.keywords import PHASE1_KEYWORDS
from shiva_discovery.queries import build_search_query, eligible_location_types
from shiva_discovery.repositories import create_search_task, fetch_locations_for_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Google Places temple search tasks.")
    parser.add_argument(
        "--district-only",
        action="store_true",
        help="Generate tasks for active district rows only. Use for Phase 1.1 baseline runs.",
    )
    parser.add_argument("--include-cities", action="store_true", help="Also generate city tasks.")
    parser.add_argument(
        "--include-villages",
        action="store_true",
        help="Also generate village-level tasks. Off by default for safety.",
    )
    parser.add_argument("--limit", type=int, help="Maximum locations to read before keyword expansion.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without inserting tasks.")
    args = parser.parse_args()
    if args.district_only and (args.include_cities or args.include_villages):
        parser.error("--district-only cannot be combined with --include-cities or --include-villages.")

    location_types = eligible_location_types(
        district_only=args.district_only,
        include_cities=args.include_cities,
        include_villages=args.include_villages,
    )

    with connect() as conn:
        locations = fetch_locations_for_tasks(
            conn,
            location_types=location_types,
            limit=args.limit,
        )
        potential_tasks = len(locations) * len(PHASE1_KEYWORDS)
        if args.dry_run:
            print(f"Would generate up to {potential_tasks} tasks from {len(locations)} locations.")
            print(f"Location types: {', '.join(location_types)}")
            return 0

        created = 0
        with conn.transaction():
            for location in locations:
                for keyword in PHASE1_KEYWORDS:
                    search_query = build_search_query(keyword, location)
                    if create_search_task(
                        conn,
                        location_id=int(location["id"]),
                        keyword=keyword,
                        search_query=search_query,
                        search_level=str(location["location_type"]),
                    ):
                        created += 1

    skipped = potential_tasks - created
    print(f"Created {created} search tasks.")
    print(f"Skipped {skipped} existing tasks.")
    print(f"Location types: {', '.join(location_types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
