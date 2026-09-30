from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import _bootstrap  # noqa: F401
from shiva_discovery.expansion_plan import build_expansion_plan


def main():
    parser = argparse.ArgumentParser(description='Plan town/ULB queries offline. Never calls Google or changes the database.')
    parser.add_argument('csv', type=Path, help='Prepared location CSV, not a candidate export.')
    parser.add_argument('--state')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--limit', type=int, default=50)
    group.add_argument('--all', action='store_true', help='Plan every eligible location, still without executing.')
    parser.add_argument('--include-cities', action='store_true')
    parser.add_argument('--max-pages', type=int, default=3)
    parser.add_argument('--request-budget', type=int, default=0, help='Hypothetical available requests; defaults to zero/unconfirmed.')
    parser.add_argument('--output', type=Path, help='New JSON file; existing files are never overwritten.')
    args = parser.parse_args()
    try:
        if args.csv.stat().st_size > 100 * 1024 * 1024:
            raise ValueError('Source exceeds the 100 MiB planning limit.')
        content = args.csv.read_bytes()
        rows = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        required = {'location_type', 'name', 'state_name'}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError('Use a prepared location CSV with location_type, name and state_name.')
        plan = build_expansion_plan(rows, state=args.state,
            location_types=('town', 'urban_local_body', 'city') if args.include_cities else ('town', 'urban_local_body'),
            limit=None if args.all else args.limit, max_pages=args.max_pages, request_budget=args.request_budget)
        plan['source_file'] = str(args.csv)
        plan['source_sha256'] = hashlib.sha256(content).hexdigest()
        if args.output:
            with args.output.open('x', encoding='utf-8') as handle:
                json.dump(plan, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
        print(json.dumps({key: value for key, value in plan.items() if key != 'tasks'}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
