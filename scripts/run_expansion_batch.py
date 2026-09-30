"""Run one daily discovery batch and refresh the local expanded portal dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.expansion import (atomic_json, expansion_lock, export_snapshot,
    merge_candidates, read_csv, run_daily_discovery)
from shiva_discovery.request_budget import BudgetBlocked, RequestBudget, budget_scope_from_env

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Read-only validation and budget check; no writes or API calls.')
    mode.add_argument('--export-only', action='store_true', help='Publish already-saved data without Google requests.')
    parser.add_argument('--state', default='Uttar Pradesh')
    parser.add_argument('--location-type', choices=['town', 'urban_local_body', 'district', 'city'], default='urban_local_body')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--max-requests', type=int, default=30)
    parser.add_argument('--max-pages', type=int, default=3)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'reports/phase_1_1_district_baseline/candidate_review.csv')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports/expansion')
    args = parser.parse_args()
    if not 1 <= args.limit <= 100 or not 1 <= args.max_pages <= 3 or not args.max_pages <= args.max_requests <= 300:
        parser.error('Use 1–100 tasks, 1–3 pages, and max-pages–300 requests.')
    result = {}
    try:
        baseline = read_csv(args.baseline)
        if not baseline:
            raise ValueError('Baseline is empty; refusing to replace the portal dataset.')
        merge_candidates(baseline, [])  # Fail before any Google requests if the baseline is malformed.
        known_states = {row['state_name'] for row in read_csv(ROOT / 'data/prepared_locations_lgd_districts.csv')}
        with connect() as conn:
            if args.dry_run:
                status = RequestBudget(conn, budget_scope_from_env(), max_requests=args.max_requests).status()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM temple_search_tasks t JOIN india_locations l ON l.id=t.location_id WHERE t.status='pending' AND l.is_active=TRUE AND l.state_name=%s AND t.search_level=%s",
                                   (args.state, args.location_type))
                    pending = cursor.fetchone()[0]
                print(json.dumps(dict(status='dry_run', remaining_requests=status['remaining_requests'],
                    max_requests=args.max_requests, matching_pending_tasks=pending)))
                return 0
            with expansion_lock(conn):
                if args.export_only:
                    result = dict(status='export_only', requests=0)
                else:
                    result = run_daily_discovery(conn, budget_scope_from_env(), state=args.state,
                        location_type=args.location_type, limit=args.limit,
                        max_requests=args.max_requests, max_pages=args.max_pages)
                if result['status'] in ('completed', 'export_only', 'already_ran'):
                    result['snapshot'] = export_snapshot(conn, baseline, args.output_dir, known_states)
                atomic_json(args.output_dir / 'last_run.json', result)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result['status'] in ('failed', 'paused', 'needs_review') else 0
    except BudgetBlocked as error:
        print(json.dumps(dict(status='blocked', reason=str(error))), file=sys.stderr)
        return 2
    except Exception as error:
        # Driver/network exception strings can include endpoints or credentials.
        # Detailed diagnostics belong in an interactive investigation, not a scheduled log.
        print(json.dumps(dict(status='failed', error_type=type(error).__name__,
            reason=str(error) if isinstance(error, ValueError) else 'Batch failed; inspect the run journal and latest manifest before retrying.')), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
