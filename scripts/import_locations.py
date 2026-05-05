from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import REPO_ROOT
from shiva_discovery.csv_import import LOCATION_TYPES, read_location_csv
from shiva_discovery.db import connect
from shiva_discovery.repositories import upsert_location


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Indian location CSV files.")
    parser.add_argument("csv_files", nargs="+", help="CSV file paths to import.")
    parser.add_argument("--source", default="csv", help="Source label stored with each row.")
    parser.add_argument(
        "--location-type",
        choices=sorted(LOCATION_TYPES),
        help="Force all rows to a location type when the CSV has no type column.",
    )
    parser.add_argument("--limit", type=int, help="Maximum rows to import from each CSV.")
    args = parser.parse_args()

    imported = 0
    with connect() as conn:
        with conn.transaction():
            for csv_file in args.csv_files:
                path = Path(csv_file)
                records = read_location_csv(
                    path,
                    source=args.source,
                    forced_location_type=args.location_type,
                    limit=args.limit,
                )
                for record in records:
                    upsert_location(conn, record)
                imported += len(records)
                print(f"Imported {len(records)} rows from {path}")

    print(f"Imported or updated {imported} location records.")
    print(f"Sample format: {REPO_ROOT / 'data' / 'sample_locations.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
