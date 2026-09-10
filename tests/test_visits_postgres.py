"""Opt-in integration test: requires a disposable PostgreSQL test database."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from shiva_discovery.visits_api import PostgresVisitStore


@pytest.mark.skipif(not os.environ.get("VISITS_TEST_DATABASE_URL"), reason="No PostgreSQL test database configured")
def test_atomic_counting_and_retry_deduplication(monkeypatch):
    import psycopg
    from psycopg import sql

    dsn = os.environ["VISITS_TEST_DATABASE_URL"]
    schema = "portal_test_" + uuid4().hex
    connect = psycopg.connect
    with connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            admin.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            admin.execute((Path(__file__).parents[1] / "migrations/004_portal_visits.sql").read_text())
            def isolated_connection(*args, **kwargs):
                kwargs["options"] = f"-c search_path={schema} -c statement_timeout=5000"
                return connect(*args, **kwargs)
            monkeypatch.setattr(psycopg, "connect", isolated_connection)
            monkeypatch.setenv("VISITS_DATABASE_URL", dsn)
            store = PostgresVisitStore()
            assert store.total() == 0
            sessions = [uuid4().hex for _ in range(10)]
            with ThreadPoolExecutor(max_workers=5) as workers:
                list(workers.map(store.total, sessions * 3))
            assert store.total() == 10
            for session in sessions:
                assert store.total(session) == 10
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
