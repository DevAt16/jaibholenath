from __future__ import annotations

import argparse
import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.places_client import GooglePlacesClient
from shiva_discovery.keywords import PHASE1_KEYWORDS
from shiva_discovery.request_budget import RequestBudget, BudgetBlocked, budget_scope_from_env
from shiva_discovery.discovery_runner import process_task
from shiva_discovery.repositories import fetch_and_mark_pending_tasks


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError('value must be at least 1')
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description='Run discovery within a confirmed monthly request allowance.')
    parser.add_argument('--limit', type=_positive_int, default=10, help='Maximum tasks to claim (default 10).')
    parser.add_argument('--allow-large-limit', action='store_true')
    parser.add_argument('--max-requests', type=_positive_int, default=10,
                        help='Hard per-run HTTP-attempt limit, including every page (default 10).')
    parser.add_argument('--page-size', type=_positive_int, default=20)
    parser.add_argument('--max-pages', type=_positive_int, default=1)
    parser.add_argument('--dry-run', action='store_true', help='Read budget/queue only; no claims or Google calls.')
    parser.add_argument('--state', help='Restrict claims to an exact state name.')
    parser.add_argument('--location-type', choices=['district', 'town', 'urban_local_body', 'city', 'sub_district', 'village'])
    parser.add_argument('--keyword', choices=PHASE1_KEYWORDS,
                        help='Run one specific search term; useful for sampling distinct locations.')
    args = parser.parse_args()
    if args.limit > 100 and not args.allow_large_limit:
        parser.error('--limit above 100 requires --allow-large-limit.')
    if args.page_size > 20 or args.max_pages > 3:
        parser.error('--page-size must be at most 20; --max-pages at most 3.')
    processed = failed = 0
    try:
        with connect() as conn:
            budget = RequestBudget(conn, budget_scope_from_env(), max_requests=args.max_requests)
            status = budget.status()  # fail closed before claiming any tasks
            print(f"Monthly requests remaining: {status['remaining_requests']}; per-run maximum: {args.max_requests}.")
            if args.dry_run:
                clauses = ["t.status = 'pending'", 'l.is_active = TRUE']
                params = []
                if args.state:
                    clauses.append('l.state_name = %s')
                    params.append(args.state)
                if args.location_type:
                    clauses.append('t.search_level = %s')
                    params.append(args.location_type)
                if args.keyword:
                    clauses.append('t.keyword = %s')
                    params.append(args.keyword)
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) FROM temple_search_tasks t JOIN india_locations l ON l.id=t.location_id WHERE {' AND '.join(clauses)}", tuple(params))
                    pending = cursor.fetchone()[0]
                print(f'Matching pending tasks: {pending}.')
                print(f'No mutations or Google calls. Selected-task upper bound: {args.limit * args.max_pages} page requests; requests are also limited by remaining allowance.')
                return 0
            # Check API credentials before marking the first task running.
            GooglePlacesClient.from_env(before_request=budget.reserve)
            for _ in range(args.limit):
                if budget.status()['run_remaining'] < 1:
                    print('Stopped at request allowance; unclaimed tasks remain pending.')
                    break
                tasks = fetch_and_mark_pending_tasks(conn, limit=1, state=args.state,
                    location_type=args.location_type, keyword=args.keyword)
                if not tasks:
                    print('No matching pending search tasks.')
                    break
                task = tasks[0]
                client = GooglePlacesClient.from_env(before_request=lambda: budget.reserve(task['id']))
                outcome, raw, unique = process_task(conn, client, task, page_size=args.page_size, max_pages=args.max_pages)
                print(f"Task {task['id']}: {outcome}, {raw} results, {unique} unique in this attempt.")
                if outcome == 'paused':
                    break
                processed += outcome == 'done'
                failed += outcome == 'failed'
            print(f'Completed {processed}, failed {failed}; reserved {budget.requests} HTTP requests in this run.')
        return 1 if failed else 0
    except (BudgetBlocked, ValueError) as error:
        parser.exit(2, f'Discovery blocked: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
