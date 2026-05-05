from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.reporting import run_report_queries, write_csv


FIELDNAMES = {
    "national_summary": [
        "country",
        "source",
        "total_discovered_candidates",
        "unique_google_place_ids",
        "high_confidence_shiva",
        "medium_confidence_shiva_candidates",
        "low_confidence_possible_temples",
        "duplicates_removed",
        "status",
    ],
    "state_counts": [
        "state",
        "unique_google_place_ids",
        "high_confidence_shiva",
        "medium_confidence_shiva_candidates",
        "low_confidence_possible_temples",
    ],
    "district_counts": [
        "state",
        "district",
        "unique_google_place_ids",
        "high_confidence_shiva",
        "medium_confidence_shiva_candidates",
        "low_confidence_possible_temples",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Phase 1 discovery count reports.")
    parser.add_argument("--output-dir", default="reports", help="Directory for CSV report outputs.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    with connect() as conn:
        reports = run_report_queries(conn)

    for report_name, rows in reports.items():
        path = output_dir / f"{report_name}.csv"
        write_csv(path, rows, FIELDNAMES[report_name])
        print(f"Wrote {path}")

    summary = reports["national_summary"][0] if reports["national_summary"] else {}
    if summary:
        print("National discovery summary:")
        for key in FIELDNAMES["national_summary"]:
            print(f"- {key}: {summary.get(key)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
