"""Opt-in tests against MySQL 8.0.16+ (CI uses MySQL 8.4).

MYSQL_TEST_DATABASE_URL must allow CREATE DATABASE. Each test uses and removes
only its own random database; no existing discovery/visitor tables are touched.
"""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import pytest
from datetime import datetime, timezone, timedelta
from shiva_discovery.db import apply_migrations, connect
from shiva_discovery.csv_import import LocationRecord
from shiva_discovery.repositories import (
    upsert_location, create_search_task, fetch_and_mark_pending_tasks,
    upsert_candidate, record_candidate_discovery_event, complete_task,
)
from shiva_discovery.reporting import run_report_queries
from shiva_discovery.visits_api import MySQLVisitStore

ROOT = Path(__file__).parents[1]
pytestmark = pytest.mark.skipif(not os.getenv('MYSQL_TEST_DATABASE_URL'), reason='No disposable MySQL test server configured')


@pytest.fixture
def database(monkeypatch):
    url = os.environ['MYSQL_TEST_DATABASE_URL']
    name = 'shiva_test_' + uuid4().hex
    with connect(url) as admin:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        test_url = urlunsplit(urlsplit(url)._replace(path='/' + name))
        try:
            monkeypatch.setenv('VISITS_DATABASE_URL', test_url)
            with connect(test_url) as conn:
                assert apply_migrations(conn, ROOT / 'migrations') == [
                    path.name for path in sorted((ROOT / 'migrations').glob('*.sql'))
                ]
                assert apply_migrations(conn, ROOT / 'migrations') == []
            yield test_url
        finally:
            with admin.cursor() as cur:
                cur.execute(f'DROP DATABASE `{name}`')


def location(conn):
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO india_locations (name, normalized_name, location_type, state_name, district_name)
                       VALUES ('पुणे', 'पुणे', 'district', 'Maharashtra', 'Pune')""")
        return cur.lastrowid


def expansion_tasks(conn, count=3):
    from shiva_discovery.queries import build_search_query
    from shiva_discovery.repositories import create_search_task
    with conn.cursor() as cur:
        for index in range(count):
            name = f'Pilot Town {index}'
            cur.execute("INSERT INTO india_locations (name, normalized_name, location_type, state_name, district_name) VALUES (%s,%s,'urban_local_body','Uttar Pradesh','Agra')", (name, name.lower()))
            location_id = cur.lastrowid
            for keyword in ('Shiva temple', 'Shiv Mandir'):
                query = build_search_query(keyword, dict(name=name, state_name='Uttar Pradesh',
                    district_name='Agra', location_type='urban_local_body'))
                create_search_task(conn, location_id=location_id, keyword=keyword,
                    search_query=query, search_level='urban_local_body')


def test_expansion_daily_idempotency_page_limits_export_and_lock(database, tmp_path):
    from shiva_discovery.expansion import expansion_lock, run_daily_discovery, export_snapshot
    from shiva_discovery.request_budget import RequestBudget, BudgetBlocked, billing_month
    now = datetime.now(timezone.utc)
    calls = []
    class Client:
        def __init__(self, before_request):
            self.before_request = before_request
        def iter_text_pages(self, query, **kwargs):
            for page in range(2):
                self.before_request()
                calls.append(query)
                yield [dict(id=f'place-{page}', displayName={'text':'Shiva temple'},
                            formattedAddress='Pilot Town 0, Uttar Pradesh, India',
                            location={'latitude':27.1, 'longitude':78.1})]
    with connect(database) as conn:
        expansion_tasks(conn)
        RequestBudget(conn, 'local:test').configure(month=billing_month(now), observed_usage=0,
            external_reserve=0, ceiling=30, checked_at=now, india_pricing_confirmed=True)
        with expansion_lock(conn):
            with connect(database) as second:
                with pytest.raises(BudgetBlocked, match='Another'):
                    with expansion_lock(second):
                        pass
            result = run_daily_discovery(conn, 'local:test', max_requests=3, client_factory=Client)
            assert result['requests'] == 2
            assert result['completed'] == 1
            assert result['stop_reason'] == 'request_limit'
            again = run_daily_discovery(conn, 'local:test', client_factory=Client)
            assert again['status'] == 'already_ran'
            assert again['requests'] == 0
            assert len(calls) == 2
            baseline = [dict(google_place_id='place-0', discovered_name='Old Shiva temple',
                confidence='high', confidence_score=0.9, first_seen_at='2025-01-01', last_seen_at='2025-01-02')]
            manifest = export_snapshot(conn, baseline, tmp_path, {'Uttar Pradesh'})
            assert manifest['combined_candidates'] == 2
            assert manifest['added_since_baseline'] == manifest['overlapping_place_ids'] == 1
            snapshot = json.loads((tmp_path/'snapshots'/f"{manifest['snapshot_id']}.json").read_text())
            assert snapshot['reports']['candidates'][0]['first_seen_at'].startswith('2025-01-01')
            assert export_snapshot(conn, baseline, tmp_path, {'Uttar Pradesh'}) == manifest
            with pytest.raises(ValueError):
                export_snapshot(conn, baseline * 2, tmp_path, {'Uttar Pradesh'})
            assert json.loads((tmp_path/'latest.json').read_text()) == manifest


def test_expansion_failure_stops_after_one_request_and_does_not_retry_same_day(database):
    from shiva_discovery.expansion import expansion_lock, run_daily_discovery
    from shiva_discovery.request_budget import RequestBudget, billing_month
    from shiva_discovery.places_client import GooglePlacesError
    now = datetime.now(timezone.utc)
    class FailingClient:
        def __init__(self, before_request):
            self.before_request = before_request
        def iter_text_pages(self, *args, **kwargs):
            self.before_request()
            raise GooglePlacesError('HTTP 403')
            yield []
    with connect(database) as conn, expansion_lock(conn):
        expansion_tasks(conn)
        RequestBudget(conn, 'local:test').configure(month=billing_month(now), observed_usage=0,
            external_reserve=0, ceiling=30, checked_at=now, india_pricing_confirmed=True)
        result = run_daily_discovery(conn, 'local:test', client_factory=FailingClient)
        assert result['status'] == 'failed'
        assert result['requests'] == 1
        assert result['failed'] == 1
        assert run_daily_discovery(conn, 'local:test', client_factory=FailingClient)['status'] == 'needs_review'
        assert RequestBudget(conn, 'local:test').status()['reserved_requests'] == 1


def test_expansion_unconfirmed_budget_claims_nothing_and_never_creates_client(database):
    from shiva_discovery.expansion import expansion_lock, run_daily_discovery
    from shiva_discovery.request_budget import BudgetBlocked
    def forbidden(**kwargs):
        pytest.fail('Client must not be constructed without a confirmed budget')
    with connect(database) as conn, expansion_lock(conn):
        expansion_tasks(conn)
        with pytest.raises(BudgetBlocked):
            run_daily_discovery(conn, 'local:test', client_factory=forbidden)
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM discovery_expansion_batches')
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM temple_search_tasks WHERE status != 'pending'")
            assert cur.fetchone()[0] == 0


def test_expansion_interrupted_previous_day_blocks_new_spending(database):
    from shiva_discovery.expansion import expansion_lock, run_daily_discovery
    from shiva_discovery.request_budget import BudgetBlocked
    with connect(database) as conn, expansion_lock(conn):
        with conn.cursor() as cur:
            cur.execute("INSERT INTO discovery_expansion_batches (run_date,budget_run_id,status) VALUES ('2020-01-01',%s,'running')", (str(uuid4()),))
        with pytest.raises(BudgetBlocked, match='interrupted'):
            run_daily_discovery(conn, 'local:test')


def test_counter_concurrent_retries_and_migration_preserve_total(database):
    store = MySQLVisitStore()
    tokens = [hashlib.sha256(uuid4().bytes).hexdigest() for _ in range(10)]
    assert store.total() == 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(store.total, tokens * 3))
    assert store.total() == 10
    assert store.total(tokens[0]) == 10
    with connect(database) as conn, conn.cursor() as cur:
        for sql in (ROOT / 'migrations/004_portal_visits.sql').read_text().split(';'):
            if sql.strip(): cur.execute(sql)
    assert store.total() == 10


def test_discovery_claims_upserts_reports_and_constraints(database):
    with connect(database) as conn:
        loc = location(conn)
        for i in range(6):
            assert create_search_task(conn, location_id=loc, keyword=f'Shiva {i}', search_query=f'query {i}', search_level='district')
        assert not create_search_task(conn, location_id=loc, keyword='Shiva 0', search_query='query 0', search_level='district')
    def claim(_):
        with connect(database) as conn:
            return fetch_and_mark_pending_tasks(conn, limit=2)
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = [task for batch in pool.map(claim, range(3)) for task in batch]
    assert len(tasks) == len({task['id'] for task in tasks}) == 6
    assert all(task['attempts'] == 1 for task in tasks)
    with connect(database) as conn:
        candidate = dict(google_place_id='CaseSensitiveID', discovered_name='Shiva Mandir',
                         state='Maharashtra', district='Pune', source_query='query 0', source_location_id=loc,
                         google_maps_uri='https://maps.google.com/?cid=1')
        with conn.transaction():
            candidate_id = upsert_candidate(conn, candidate)
            assert upsert_candidate(conn, {**candidate, 'google_maps_uri': None}) == candidate_id
            assert upsert_candidate(conn, {**candidate, 'google_place_id': 'casesensitiveid'}) != candidate_id
            event = record_candidate_discovery_event(conn, candidate_id=candidate_id, candidate=candidate, task=tasks[0], result_position=1)
            assert record_candidate_discovery_event(conn, candidate_id=candidate_id, candidate=candidate, task=tasks[0], result_position=2) == event
            complete_task(conn, task_id=tasks[0]['id'], status='done', result_count=3)
        summary = run_report_queries(conn, include_candidates=True, location_type='district')
        assert summary['national_summary'][0]['unique_google_place_ids'] == 2
        assert summary['national_summary'][0]['duplicates_removed'] == 1
        assert len(summary['candidate_review']) == 2
        assert summary['candidate_review'][0]['first_seen_at'].utcoffset().total_seconds() == 0
        with pytest.raises(RuntimeError):
            with conn.transaction():
                upsert_candidate(conn, {**candidate, 'google_place_id': 'rollback'})
                raise RuntimeError('roll back this candidate')
        assert run_report_queries(conn)['national_summary'][0]['unique_google_place_ids'] == 2
        with conn.cursor() as cur:
            cur.execute('SELECT google_maps_uri FROM temple_candidates WHERE id = %s', (candidate_id,))
            assert cur.fetchone()[0] == candidate['google_maps_uri']
            cur.execute('DELETE FROM temple_candidates WHERE id = %s', (candidate_id,))
            cur.execute('SELECT COUNT(*) FROM candidate_discovery_events WHERE id = %s', (event,))
            assert cur.fetchone()[0] == 0


def test_keyword_scoped_claim_samples_distinct_locations(database):
    with connect(database) as conn:
        first = location(conn)
        with conn.cursor() as cursor:
            cursor.execute("""INSERT INTO india_locations
                (name, normalized_name, location_type, state_name, district_name)
                VALUES ('Other town', 'other town', 'district', 'Maharashtra', 'Other')""")
            second = cursor.lastrowid
        for location_id in (first, second):
            for keyword in ('Shiva temple', 'Mahadev temple'):
                create_search_task(conn, location_id=location_id, keyword=keyword,
                    search_query=f'{keyword} at {location_id}', search_level='district')
        claimed = fetch_and_mark_pending_tasks(conn, limit=2, state='Maharashtra',
            location_type='district', keyword='Shiva temple')
        assert {task['location_id'] for task in claimed} == {first, second}
        assert {task['keyword'] for task in claimed} == {'Shiva temple'}
        with conn.cursor() as cursor:
            cursor.execute("SELECT keyword, COUNT(*) FROM temple_search_tasks WHERE status='pending' GROUP BY keyword")
            assert cursor.fetchall() == (('Mahadev temple', 2),)


def test_location_import_backfill_and_interrupted_migration_retry(database, monkeypatch):
    import runpy
    import sys
    import types
    from dataclasses import replace
    # The test imports the CLI helpers without loading any developer .env file.
    monkeypatch.setitem(sys.modules, '_bootstrap', types.ModuleType('_bootstrap'))
    backfill = runpy.run_path(str(ROOT / 'scripts/backfill_discovery_events.py'))['_backfill']
    record = LocationRecord(name='महाराष्ट्र', normalized_name='महाराष्ट्र', location_type='state',
                            parent_id=None, state_name='Maharashtra', district_name=None,
                            sub_district_name=None, state_lgd_code='27', district_lgd_code=None,
                            sub_district_lgd_code=None, village_lgd_code=None, source='test',
                            full_path='India/Maharashtra', search_priority=1, is_active=True)
    with connect(database) as conn:
        with conn.transaction():
            state_id = upsert_location(conn, record)
            assert upsert_location(conn, replace(record, name='Maharashtra')) == state_id
            district_id = upsert_location(conn, replace(record, name='पुणे', normalized_name='पुणे',
                                          location_type='district', district_name='Pune', district_lgd_code='521'))
            with conn.cursor() as cur:
                cur.execute('SELECT parent_id FROM india_locations WHERE id = %s', (district_id,))
                assert cur.fetchone()[0] == state_id
            create_search_task(conn, location_id=district_id, keyword='Shiva', search_query='Shiva Pune', search_level='district')
            upsert_candidate(conn, dict(google_place_id='backfill', discovered_name='Shiva temple',
                                       source_location_id=district_id, source_query='Shiva Pune'))
            assert backfill(conn, location_type='district', limit=2) == 1
            assert backfill(conn, location_type='district', limit=2) == 0
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schema_migrations WHERE version = '002_add_google_maps_uri.sql'")
        assert apply_migrations(conn, ROOT / 'migrations') == ['002_add_google_maps_uri.sql']
        assert apply_migrations(conn, ROOT / 'migrations') == []


@pytest.mark.parametrize('account', ['AAAAAA-BBBBBB-CCCCCC', 'local:shiva-discovery'])
def test_request_budget_concurrent_workers_and_reconfiguration_cannot_overspend(database, account):
    from shiva_discovery.request_budget import RequestBudget, BudgetBlocked, billing_month
    now = datetime.now(timezone.utc)
    with connect(database) as conn:
        budget = RequestBudget(conn, account)
        with pytest.raises(BudgetBlocked):
            budget.reserve()
        budget.configure(month=billing_month(now), observed_usage=29990, external_reserve=3,
                         ceiling=30000, checked_at=now, india_pricing_confirmed=True)
    def attempt(_):
        with connect(database) as conn:
            try:
                RequestBudget(conn, account).reserve()
                return True
            except BudgetBlocked:
                return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 7
    with connect(database) as conn:
        budget = RequestBudget(conn, account)
        assert budget.status()['remaining_requests'] == 0
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM places_request_reservations')
            assert cursor.fetchone()[0] == 7
        # A lagged/incorrectly lower console observation must not erase usage.
        budget.configure(month=billing_month(now), observed_usage=0, external_reserve=3,
                         ceiling=30000, checked_at=now, india_pricing_confirmed=True)
        assert budget.status()['remaining_requests'] == 0
        with pytest.raises(BudgetBlocked):
            RequestBudget(conn, account, clock=lambda: now + timedelta(hours=25)).reserve()
        with conn.transaction(), pytest.raises(RuntimeError):
            budget.reserve()


def test_budget_stop_keeps_received_page_and_pending_task_without_double_inserting(database, monkeypatch):
    import io
    import json
    from shiva_discovery.places_client import GooglePlacesClient
    from shiva_discovery.request_budget import RequestBudget, billing_month
    from shiva_discovery.discovery_runner import process_task
    now = datetime.now(timezone.utc)
    calls = []
    def send(request, **kwargs):
        payload = json.loads(request.data)
        calls.append(payload)
        if payload.get('pageToken'):
            result = {'places': [{'id': 'second', 'displayName': {'text': 'Mahadev temple'}}]}
        else:
            result = {'places': [{'id': 'first', 'displayName': {'text': 'Shiva temple'}}], 'nextPageToken': 'page2'}
        return io.BytesIO(json.dumps(result).encode())
    monkeypatch.setattr('urllib.request.urlopen', send)
    with connect(database) as conn:
        loc = location(conn)
        create_search_task(conn, location_id=loc, keyword='Shiva', search_query='Shiva Pune', search_level='district')
        # Scope filters must not consume unrelated pending work.
        assert fetch_and_mark_pending_tasks(conn, limit=1, state='Other') == []
        assert fetch_and_mark_pending_tasks(conn, limit=1, location_type='town') == []
        task = fetch_and_mark_pending_tasks(conn, limit=1, state='Maharashtra', location_type='district')[0]
        budget = RequestBudget(conn, 'AAAAAA-BBBBBB-CCCCCC', max_requests=1)
        budget.configure(month=billing_month(now), observed_usage=0, external_reserve=0,
                         ceiling=3, checked_at=now, india_pricing_confirmed=True)
        client = GooglePlacesClient('test-only', before_request=lambda: budget.reserve(task['id']))
        assert process_task(conn, client, task, page_size=20, max_pages=3) == ('paused', 1, 1)
        assert len(calls) == 1
        assert run_report_queries(conn)['national_summary'][0]['unique_google_place_ids'] == 1
        task = fetch_and_mark_pending_tasks(conn, limit=1)[0]
        budget = RequestBudget(conn, 'AAAAAA-BBBBBB-CCCCCC', max_requests=2)
        client = GooglePlacesClient('test-only', before_request=lambda: budget.reserve(task['id']))
        assert process_task(conn, client, task, page_size=20, max_pages=3) == ('done', 2, 2)
        assert len(calls) == 3  # restart from page 1 intentionally counts again
        assert budget.status()['remaining_requests'] == 0
        assert run_report_queries(conn)['national_summary'][0]['unique_google_place_ids'] == 2
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM candidate_discovery_events')
            assert cursor.fetchone()[0] == 2


@pytest.mark.parametrize('account', ['AAAAAA-BBBBBB-CCCCCC', 'local:shiva-discovery'])
def test_budget_audit_failure_rolls_back_reservation_and_dry_run_never_claims(database, monkeypatch, capsys, account):
    import runpy
    import sys
    import types
    from shiva_discovery.request_budget import RequestBudget, billing_month, BudgetBlocked
    now = datetime.now(timezone.utc)
    with connect(database) as conn:
        budget = RequestBudget(conn, account)
        with pytest.raises(BudgetBlocked):
            budget.configure(month=billing_month(now), observed_usage=0, external_reserve=0,
                             ceiling=10, checked_at=now, india_pricing_confirmed=False)
        with pytest.raises(ValueError):
            budget.configure(month=billing_month(now), observed_usage=0, external_reserve=0,
                             ceiling=35000, checked_at=now, india_pricing_confirmed=True)
        budget.configure(month=billing_month(now), observed_usage=0, external_reserve=0,
                         ceiling=10, checked_at=now, india_pricing_confirmed=True)
        with conn.cursor() as cursor:
            cursor.execute("CREATE TRIGGER fail_budget_audit BEFORE INSERT ON places_request_reservations FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit unavailable'")
        with pytest.raises(Exception, match='audit unavailable'):
            budget.reserve()
        assert budget.status()['remaining_requests'] == 10
        assert budget.requests == 0
        with conn.cursor() as cursor:
            cursor.execute('DROP TRIGGER fail_budget_audit')
        loc = location(conn)
        create_search_task(conn, location_id=loc, keyword='Shiva', search_query='Shiva Pune', search_level='district')
    monkeypatch.setitem(sys.modules, '_bootstrap', types.ModuleType('_bootstrap'))
    monkeypatch.setenv('DATABASE_URL', database)
    monkeypatch.delenv('GOOGLE_MAPS_BUDGET_SCOPE', raising=False)
    monkeypatch.delenv('GOOGLE_MAPS_BILLING_ACCOUNT_ID', raising=False)
    monkeypatch.setenv('GOOGLE_MAPS_BUDGET_SCOPE' if account.startswith('local:') else 'GOOGLE_MAPS_BILLING_ACCOUNT_ID', account)
    monkeypatch.delenv('GOOGLE_PLACES_API_KEY', raising=False)
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **kw: pytest.fail('Dry run sent HTTP'))
    monkeypatch.setattr(sys, 'argv', ['run_discovery.py', '--dry-run', '--state', 'Maharashtra'])
    main = runpy.run_path(str(ROOT / 'scripts/run_discovery.py'))['main']
    assert main() == 0
    assert 'Matching pending tasks: 1' in capsys.readouterr().out
    with connect(database) as conn, conn.cursor() as cursor:
        cursor.execute('SELECT status, attempts FROM temple_search_tasks')
        assert cursor.fetchone() == ('pending', 0)
        cursor.execute('SELECT COUNT(*) FROM places_request_reservations')
        assert cursor.fetchone()[0] == 0
