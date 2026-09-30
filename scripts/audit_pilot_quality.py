"""Audit saved candidate CSVs offline; no Google or database calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import _bootstrap  # noqa: F401
from shiva_discovery.pilot_audit import audit_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file; never overwrites.')
    args = parser.parse_args()
    try:
        for path in (args.baseline, args.pilot):
            if path.stat().st_size > 100 * 1024 * 1024:
                raise ValueError('Candidate CSV exceeds 100 MiB audit limit.')
        with args.baseline.open(encoding='utf-8-sig', newline='') as handle:
            baseline = list(csv.DictReader(handle))
        with args.pilot.open(encoding='utf-8-sig', newline='') as handle:
            pilot = list(csv.DictReader(handle))
        result = audit_candidates(baseline, pilot)
        result['baseline_sha256'] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
        result['pilot_sha256'] = hashlib.sha256(args.pilot.read_bytes()).hexdigest()
        result['note'] = ('Overlap compares saved Google Place IDs only. Confidence is a name-only '
                          'candidate signal; query geography and temple identity still require review.')
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        print(json.dumps({key: value for key, value in result.items() if key != 'changed_candidates'}, indent=2))
    except (OSError, KeyError, ValueError) as error:
        parser.exit(2, f'Audit failed: {error}\n')


if __name__ == '__main__':
    main()
