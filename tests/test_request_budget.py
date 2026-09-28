from datetime import datetime, timedelta, timezone
import pytest
from shiva_discovery.request_budget import billing_month, remaining, account_key, BudgetBlocked, budget_scope_from_env


@pytest.mark.parametrize('stamp,month', [
    ('2026-10-01T06:59:59+00:00', '2026-09'), ('2026-10-01T07:00:00+00:00', '2026-10'),
    ('2026-12-01T07:59:59+00:00', '2026-11'), ('2026-12-01T08:00:00+00:00', '2026-12'),
])
def test_billing_month_uses_pacific_dst_boundary(stamp, month):
    assert billing_month(datetime.fromisoformat(stamp)) == month


def test_missing_stale_future_and_wrong_month_fail_closed():
    now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    row = dict(billing_month='2026-09', usage_checked_at=now, request_ceiling=30000,
               accounted_external_usage=20000, external_reserve=1000, reserved_requests=500)
    assert remaining(row, now) == 8500
    assert remaining({**row, 'reserved_requests': 20000}, now) == 0
    for bad in [None, {**row, 'billing_month': '2026-08'},
                {**row, 'usage_checked_at': now - timedelta(hours=25)},
                {**row, 'usage_checked_at': now + timedelta(seconds=1)},
                {**row, 'usage_checked_at': now.replace(tzinfo=None)}]:
        with pytest.raises(BudgetBlocked):
            remaining(bad, now)
    with pytest.raises(ValueError):
        billing_month(now.replace(tzinfo=None))


def test_account_identity_is_required_and_hashed():
    assert len(account_key('AAAAAA-BBBBBB-CCCCCC')) == 64
    for value in ['', 'some-project', 'key-secret']:
        with pytest.raises(ValueError):
            account_key(value)


def test_local_scope_is_stable_and_survives_adding_account_id():
    env = {'GOOGLE_MAPS_BUDGET_SCOPE': 'local:shiva-discovery'}
    key = account_key(budget_scope_from_env(env))
    env['GOOGLE_MAPS_BILLING_ACCOUNT_ID'] = 'AAAAAA-BBBBBB-CCCCCC'
    assert account_key(budget_scope_from_env(env)) == key
    assert key != account_key(env['GOOGLE_MAPS_BILLING_ACCOUNT_ID'])
    del env['GOOGLE_MAPS_BUDGET_SCOPE']
    assert budget_scope_from_env(env) == env['GOOGLE_MAPS_BILLING_ACCOUNT_ID']


@pytest.mark.parametrize('scope', ['', 'local:', 'local:MixedCase', 'local:has space', 'local:' + 'a' * 65])
def test_invalid_local_scope_fails_closed(scope):
    with pytest.raises(ValueError):
        budget_scope_from_env({'GOOGLE_MAPS_BUDGET_SCOPE': scope})
