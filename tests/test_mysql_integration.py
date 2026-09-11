"""Opt-in tests against MySQL 8.0.16+ (CI uses MySQL 8.4).

MYSQL_TEST_DATABASE_URL must allow CREATE DATABASE. Each test uses and removes
only its own random database; no existing discovery/visitor tables are touched.
"""
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import pytest
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
                assert len(apply_migrations(conn, ROOT / 'migrations')) == 4
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
