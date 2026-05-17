from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.dedupe import deduplicate_places
from shiva_discovery.places_client import (
    GooglePlacesClient,
    GooglePlacesError,
    place_to_candidate,
)
from shiva_discovery.repositories import (
    complete_task,
    fetch_and_mark_pending_tasks,
    record_candidate_discovery_event,
    upsert_candidate,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run limited Google Places discovery tasks.")
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=10,
        help="Maximum pending tasks to run. Defaults to 10 for safety.",
    )
    parser.add_argument(
        "--allow-large-limit",
        action="store_true",
        help="Allow --limit above 100.",
    )
    parser.add_argument("--page-size", type=_positive_int, default=20, help="Places page size, max 20.")
    parser.add_argument("--max-pages", type=_positive_int, default=1, help="Pages per task, max 3.")
    args = parser.parse_args()

    if args.limit > 100 and not args.allow_large_limit:
        parser.error("--limit above 100 requires --allow-large-limit.")
    if args.page_size > 20:
        parser.error("--page-size cannot exceed 20.")
    if args.max_pages > 3:
        parser.error("--max-pages cannot exceed 3.")

    client = GooglePlacesClient.from_env()
    processed = 0
    failed = 0
    raw_results = 0
    unique_results_seen = 0

    with connect() as conn:
        with conn.transaction():
            tasks = fetch_and_mark_pending_tasks(conn, limit=args.limit)

        if not tasks:
            print("No pending search tasks found.")
            return 0

        for task in tasks:
            task_id = int(task["id"])
            try:
                places = client.search_text(
                    str(task["search_query"]),
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                deduped = deduplicate_places(places)
                with conn.transaction():
                    for result_position, place in enumerate(deduped.unique_places, start=1):
                        candidate = place_to_candidate(
                            place,
                            source_query=str(task["search_query"]),
                            source_location_id=int(task["location_id"]),
                            state=task.get("state_name"),
                            district=task.get("district_name"),
                        )
                        if candidate["google_place_id"]:
                            candidate_id = upsert_candidate(conn, candidate)
                            record_candidate_discovery_event(
                                conn,
                                candidate_id=candidate_id,
                                candidate=candidate,
                                task=task,
                                result_position=result_position,
                            )
                    complete_task(
                        conn,
                        task_id=task_id,
                        status="done",
                        result_count=len(places),
                    )

                processed += 1
                raw_results += len(places)
                unique_results_seen += len(deduped.unique_places)
                print(
                    f"Task {task_id} done: {len(places)} raw results, "
                    f"{len(deduped.unique_places)} unique in response."
                )
            except (GooglePlacesError, ValueError) as exc:
                with conn.transaction():
                    complete_task(
                        conn,
                        task_id=task_id,
                        status="failed",
                        result_count=0,
                        last_error=str(exc)[:2000],
                    )
                failed += 1
                print(f"Task {task_id} failed: {exc}")

    print(
        f"Processed {processed} tasks, failed {failed}, "
        f"observed {raw_results} raw results and {unique_results_seen} response-unique places."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
