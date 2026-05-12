from __future__ import annotations

import argparse
from pathlib import Path

import _bootstrap  # noqa: F401
from shiva_discovery.location_sources import (
    STANDARD_LOCATION_FIELDNAMES,
    append_unique_location_rows,
    build_sub_district_lookup,
    dedupe_location_rows,
    normalize_census_town_rows,
    normalize_lgd_district_rows,
    normalize_lgd_local_body_rows,
    normalize_lgd_sub_district_rows,
    read_source_rows,
    write_standard_location_csv,
)


def _load_and_normalize(
    label: str,
    paths: list[str] | None,
    normalizer,
    *,
    state_filter: str | None,
) -> list[dict[str, str]]:
    if not paths:
        return []

    output: list[dict[str, str]] = []
    for raw_path in paths:
        path = Path(raw_path)
        rows = read_source_rows(path)
        normalized, stats = normalizer(rows, state_filter=state_filter)
        output.extend(normalized)
        print(
            f"{label}: {path} -> read {stats.read_rows}, "
            f"emitted {stats.emitted_rows}, skipped {stats.skipped_rows}, "
            f"duplicates {stats.duplicate_rows}"
        )
    return output


def _load_raw_rows(paths: list[str] | None) -> list[dict[str, object]]:
    if not paths:
        return []
    output: list[dict[str, object]] = []
    for raw_path in paths:
        output.extend(read_source_rows(Path(raw_path)))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize official LGD/Census location source files into the "
            "project's standard data/locations.csv format."
        )
    )
    parser.add_argument("--state", help="Only include rows for this state/UT name.")
    parser.add_argument(
        "--lgd-districts",
        action="append",
        help="LGD districts CSV/JSON file. May be passed more than once.",
    )
    parser.add_argument(
        "--lgd-sub-districts",
        action="append",
        help="LGD sub-districts CSV/JSON file. May be passed more than once.",
    )
    parser.add_argument(
        "--lgd-local-bodies",
        action="append",
        help=(
            "LGD local bodies CSV/JSON file. Rural bodies are skipped when a "
            "local body type/category column is present."
        ),
    )
    parser.add_argument(
        "--census-towns",
        action="append",
        help="Census town/PCA CSV/JSON file. May be passed more than once.",
    )
    parser.add_argument(
        "--output",
        default="data/prepared_locations.csv",
        help="Where to write the normalized CSV output.",
    )
    parser.add_argument(
        "--append-to",
        help=(
            "Optionally append unique normalized rows to an existing locations CSV, "
            "for example data/locations.csv."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts but do not write output or append rows.",
    )
    args = parser.parse_args()

    sub_district_raw_rows = _load_raw_rows(args.lgd_sub_districts)
    sub_district_lookup = build_sub_district_lookup(sub_district_raw_rows)
    if sub_district_lookup:
        print(f"Built sub-district lookup with {len(sub_district_lookup)} LGD codes")

    rows: list[dict[str, str]] = []
    rows.extend(
        _load_and_normalize(
            "LGD districts",
            args.lgd_districts,
            normalize_lgd_district_rows,
            state_filter=args.state,
        )
    )
    if sub_district_raw_rows:
        normalized, stats = normalize_lgd_sub_district_rows(
            sub_district_raw_rows,
            state_filter=args.state,
        )
        rows.extend(normalized)
        print(
            f"LGD sub-districts: combined input -> read {stats.read_rows}, "
            f"emitted {stats.emitted_rows}, skipped {stats.skipped_rows}, "
            f"duplicates {stats.duplicate_rows}"
        )
    if args.lgd_local_bodies:
        for raw_path in args.lgd_local_bodies:
            path = Path(raw_path)
            raw_rows = read_source_rows(path)
            normalized, stats = normalize_lgd_local_body_rows(
                raw_rows,
                state_filter=args.state,
                sub_district_lookup=sub_district_lookup,
            )
            rows.extend(normalized)
            missing_districts = sum(1 for row in normalized if not row.get("district_name"))
            print(
                f"LGD local bodies: {path} -> read {stats.read_rows}, "
                f"emitted {stats.emitted_rows}, skipped {stats.skipped_rows}, "
                f"duplicates {stats.duplicate_rows}, "
                f"missing district {missing_districts}"
            )
    rows.extend(
        _load_and_normalize(
            "Census towns",
            args.census_towns,
            normalize_census_town_rows,
            state_filter=args.state,
        )
    )

    deduped, duplicate_rows = dedupe_location_rows(rows)
    print(f"Combined output rows: {len(deduped)}")
    print(f"Combined duplicates removed: {duplicate_rows}")
    if args.state:
        print(f"State filter: {args.state}")
    print(f"Output fields: {', '.join(STANDARD_LOCATION_FIELDNAMES)}")

    if args.dry_run:
        return 0

    output_path = Path(args.output)
    write_standard_location_csv(output_path, deduped)
    print(f"Wrote {output_path}")

    if args.append_to:
        appended = append_unique_location_rows(Path(args.append_to), deduped)
        print(f"Appended {appended} unique rows to {args.append_to}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
