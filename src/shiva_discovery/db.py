from __future__ import annotations

import os
from pathlib import Path


def connect():
    """Create a PostgreSQL connection from DATABASE_URL or PG* environment variables."""
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for database access. Install with `pip install -e .`."
        ) from exc

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)

    kwargs = {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "shiva_temple_discovery"),
        "user": os.getenv("PGUSER", "postgres"),
    }
    password = os.getenv("PGPASSWORD")
    if password:
        kwargs["password"] = password

    return psycopg.connect(**kwargs)


def _ensure_schema_migrations(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute("SELECT version FROM schema_migrations;")
        return {row[0] for row in cursor.fetchall()}


def apply_migrations(conn, migrations_dir: Path) -> list[str]:
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        return []

    applied_now: list[str] = []
    with conn.transaction():
        _ensure_schema_migrations(conn)
        applied = _applied_versions(conn)

        for migration in migrations:
            version = migration.name
            if version in applied:
                continue

            sql = migration.read_text(encoding="utf-8")
            with conn.cursor() as cursor:
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);",
                    (version,),
                )
            applied_now.append(version)

    return applied_now
