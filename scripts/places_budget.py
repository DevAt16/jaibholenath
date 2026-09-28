"""Manage operator-confirmed billing usage. Never calls Google Places."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import _bootstrap  # noqa: F401
from shiva_discovery.db import connect
from shiva_discovery.request_budget import RequestBudget, BudgetBlocked, budget_scope_from_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    configure = sub.add_parser('configure')
    configure.add_argument('--month', required=True, help='Pacific billing month YYYY-MM; no automatic rollover.')
    configure.add_argument('--observed-account-usage', required=True, type=int,
                           help='Current-month Text Search Pro usage across ALL projects on the billing account.')
    configure.add_argument('--external-reserve', required=True, type=int,
                           help='Allowance reserved for future usage outside this ledger; explicitly set 0 if none.')
    configure.add_argument('--checked-at', required=True, help='ISO 8601 timestamp with timezone of billing-console check.')
    configure.add_argument('--ceiling', default=30000, type=int)
    configure.add_argument('--confirm-india-pricing', action='store_true', required=True)
    args = parser.parse_args()
    try:
        with connect() as conn:
            budget = RequestBudget(conn, budget_scope_from_env())
            if args.command == 'configure':
                result = budget.configure(month=args.month, observed_usage=args.observed_account_usage,
                    external_reserve=args.external_reserve, ceiling=args.ceiling,
                    checked_at=datetime.fromisoformat(args.checked_at.replace('Z', '+00:00')),
                    india_pricing_confirmed=args.confirm_india_pricing)
            else:
                result = budget.status()
            print(json.dumps(result, default=str, indent=2))
        return 0
    except (ValueError, BudgetBlocked) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
