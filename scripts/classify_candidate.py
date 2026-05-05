from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
from shiva_discovery.classification import classify_candidate_name
from shiva_discovery.db import connect
from shiva_discovery.repositories import update_candidate_classification


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify Shiva confidence for candidate names.")
    parser.add_argument("names", nargs="*", help="Names to classify without touching the database.")
    parser.add_argument("--update-db", action="store_true", help="Reclassify stored candidates.")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum DB candidates to update.")
    args = parser.parse_args()

    for name in args.names:
        result = classify_candidate_name(name)
        print(
            f"{name}: {result.confidence} "
            f"({result.confidence_score}) - {result.classification_reason}"
        )

    if not args.update_db:
        return 0

    updated = 0
    with connect() as conn:
        with conn.transaction():
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, discovered_name
                    FROM temple_candidates
                    ORDER BY id
                    LIMIT %s;
                    """,
                    (args.limit,),
                )
                candidates = cursor.fetchall()
            for candidate_id, discovered_name in candidates:
                update_candidate_classification(conn, int(candidate_id), str(discovered_name))
                updated += 1

    print(f"Reclassified {updated} candidates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
