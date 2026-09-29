"""Flag possible geographic mismatches in a saved pilot CSV, without API calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import _bootstrap  # noqa: F401
from shiva_discovery.geography_audit import audit_geography


def _rows(path):
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('CSV exceeds 100 MiB audit limit.')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--locations', type=Path, required=True)
    parser.add_argument('--districts', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--review-csv', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.summary == args.review_csv or args.summary.exists() or args.review_csv.exists():
            raise ValueError('Use two new output paths; audit files are never overwritten.')
        candidate_rows, locations, districts = (_rows(path) for path in
                                                 (args.candidates, args.locations, args.districts))
        result = audit_geography(candidate_rows, locations, {row['state_name'] for row in districts})
        records = result.pop('records')
        result['candidate_csv_sha256'] = hashlib.sha256(args.candidates.read_bytes()).hexdigest()
        with args.summary.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        with args.review_csv.open('x', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]) if records else
                ['google_place_id', 'discovered_name', 'google_maps_uri', 'returned_address',
                 'query_locality', 'query_district', 'query_state', 'address_state_hint',
                 'distance_from_inferred_locality_km', 'review_priority', 'flags'])
            writer.writeheader()
            writer.writerows(records)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, KeyError, ValueError) as error:
        parser.exit(2, f'Geography audit failed: {error}\n')


if __name__ == '__main__':
    main()
