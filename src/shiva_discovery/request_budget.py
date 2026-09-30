"""Conservative, account-wide Text Search Pro reservations, committed before I/O.

This ledger controls cooperating runners, not Google billing. All runners for a
billing account must share this database. Operator-supplied console usage and
reserved allowance for other consumers are required; no account access is inferred.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
from uuid import uuid4
from zoneinfo import ZoneInfo

SKU = 'places-text-search-pro-india'
FREE_ALLOWANCE = 35000
MAX_CEILING = 30000
USAGE_MAX_AGE = timedelta(hours=24)
PACIFIC = ZoneInfo('America/Los_Angeles')


class BudgetBlocked(RuntimeError):
    pass


def billing_month(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError('Billing timestamps must include a timezone.')
    return now.astimezone(PACIFIC).strftime('%Y-%m')


def account_key(account: str) -> str:
    if not (re.fullmatch(r'[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}', account)
            or re.fullmatch(r'local:[a-z0-9][a-z0-9_-]{0,63}', account)):
        raise ValueError('Set GOOGLE_MAPS_BUDGET_SCOPE to a stable local:name, or set GOOGLE_MAPS_BILLING_ACCOUNT_ID.')
    return hashlib.sha256(account.encode()).hexdigest()


def budget_scope_from_env(env=None) -> str:
    """Explicit local scope wins so adding an account ID cannot reset its ledger.

    Keep the same scope and database for all cooperating workers. Neither this
    name nor an account ID grants Cloud Billing access or verifies free usage.
    """
    env = os.environ if env is None else env
    scope = env.get('GOOGLE_MAPS_BUDGET_SCOPE') or env.get('GOOGLE_MAPS_BILLING_ACCOUNT_ID', '')
    account_key(scope)
    return scope


def validate_observation(month, checked_at, now):
    if billing_month(now) != month:
        raise BudgetBlocked('Configure the current Pacific billing month explicitly; allowances do not auto-renew.')
    if checked_at.tzinfo is None or checked_at > now or now - checked_at > USAGE_MAX_AGE:
        raise BudgetBlocked('Account usage must have been checked within the last 24 hours, with an explicit timezone.')
    if billing_month(checked_at) != month:
        raise BudgetBlocked('The usage observation belongs to another billing month.')


def remaining(row, now):
    if row is None:
        raise BudgetBlocked('No confirmed monthly allowance. Run places_budget.py configure after checking Google Cloud Billing.')
    validate_observation(row['billing_month'], row['usage_checked_at'], now)
    return max(0, row['request_ceiling'] - row['accounted_external_usage']
               - row['external_reserve'] - row['reserved_requests'])


class RequestBudget:
    def __init__(self, conn, account, *, max_requests=10, clock=None):
        if not isinstance(max_requests, int) or max_requests < 1:
            raise ValueError('max_requests must be positive.')
        self.conn = conn
        self.account_key = account_key(account)
        self.max_requests = max_requests
        self.requests = 0
        self.run_id = str(uuid4())
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _row(self, cursor, month, *, lock=False):
        cursor.execute('''SELECT billing_month, request_ceiling, accounted_external_usage,
            external_reserve, reserved_requests, usage_checked_at FROM places_monthly_budgets
            WHERE account_key = %s AND billing_month = %s AND sku = %s''' + (' FOR UPDATE' if lock else ''),
            (self.account_key, month, SKU))
        row = cursor.fetchone()
        return dict(zip([column[0] for column in cursor.description], row)) if row else None

    def configure(self, *, month, observed_usage, external_reserve, ceiling,
                  checked_at, india_pricing_confirmed):
        now = self.clock()
        validate_observation(month, checked_at, now)
        if not india_pricing_confirmed:
            raise BudgetBlocked('Confirm India pricing eligibility in Google Cloud before configuring an allowance.')
        if any(type(value) is not int or value < 0 or value > 2**32 - 1 for value in (observed_usage, external_reserve, ceiling)) or not 1 <= ceiling <= MAX_CEILING:
            raise ValueError('Usage/reserve must be nonnegative integers; ceiling must be between 1 and 30000.')
        if self.conn.depth:
            raise RuntimeError('Budget configuration must commit independently.')
        with self.conn.transaction(), self.conn.cursor() as cursor:
            # Insert under the unique key, then lock so concurrent initializers
            # cannot reset or overwrite accumulated reservations.
            cursor.execute('''INSERT INTO places_monthly_budgets
                (account_key, billing_month, sku, request_ceiling, accounted_external_usage,
                 external_reserve, usage_checked_at) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE account_key = account_key''',
                (self.account_key, month, SKU, ceiling, observed_usage, external_reserve,
                 checked_at.astimezone(timezone.utc).replace(tzinfo=None)))
            row = self._row(cursor, month, lock=True)
            if checked_at < row['usage_checked_at']:
                raise BudgetBlocked('Cannot replace a usage observation with an older one.')
            # Never lower already accounted usage, even if billing reporting lags.
            external = max(row['accounted_external_usage'], observed_usage - row['reserved_requests'])
            cursor.execute('''UPDATE places_monthly_budgets SET request_ceiling=%s,
                accounted_external_usage=%s, external_reserve=%s, usage_checked_at=%s
                WHERE account_key=%s AND billing_month=%s AND sku=%s''',
                (ceiling, external, external_reserve, checked_at.astimezone(timezone.utc).replace(tzinfo=None),
                 self.account_key, month, SKU))
        return self.status()

    def status(self):
        now = self.clock()
        with self.conn.cursor() as cursor:
            row = self._row(cursor, billing_month(now))
        available = remaining(row, now)
        return {**row, 'sku': SKU, 'remaining_requests': available,
                'run_remaining': min(available, self.max_requests - self.requests)}

    def reserve(self, task_id=None):
        if self.requests >= self.max_requests:
            raise BudgetBlocked('Per-run HTTP request limit reached; unfinished task remains pending.')
        if self.conn.depth:
            raise RuntimeError('Request reservations must commit before network I/O, outside other transactions.')
        now = self.clock()
        month = billing_month(now)
        with self.conn.transaction(), self.conn.cursor() as cursor:
            row = self._row(cursor, month, lock=True)
            if remaining(row, self.clock()) < 1:
                raise BudgetBlocked('Monthly request allowance exhausted; unfinished task remains pending.')
            cursor.execute('''UPDATE places_monthly_budgets SET reserved_requests=reserved_requests+1
                WHERE account_key=%s AND billing_month=%s AND sku=%s''', (self.account_key, month, SKU))
            cursor.execute('''INSERT INTO places_request_reservations
                (account_key, billing_month, sku, run_id, task_id) VALUES (%s,%s,%s,%s,%s)''',
                (self.account_key, month, SKU, self.run_id, task_id))
        self.requests += 1
