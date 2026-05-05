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
    "candidate_review": [
        "google_place_id",
        "google_maps_uri",
        "discovered_name",
        "discovered_address",
        "latitude",
        "longitude",
        "state",
        "district",
        "source_query",
        "confidence",
        "confidence_score",
        "classification_reason",
        "first_seen_at",
        "last_seen_at",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Phase 1 discovery count reports.")
    parser.add_argument("--output-dir", default="reports", help="Directory for CSV report outputs.")
    parser.add_argument(
        "--include-candidates",
        action="store_true",
        help="Also export candidate_review.csv for the analysis UI.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=5000,
        help="Maximum candidates to export when --include-candidates is used.",
    )
    args = parser.parse_args()
    if args.candidate_limit < 1:
        parser.error("--candidate-limit must be at least 1.")

    output_dir = Path(args.output_dir)
    with connect() as conn:
        reports = run_report_queries(
            conn,
            include_candidates=args.include_candidates,
            candidate_limit=args.candidate_limit,
        )

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
