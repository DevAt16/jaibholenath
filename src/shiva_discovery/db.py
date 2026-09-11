from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def connection_options(database_url: str | None = None, *, prefix: str = "MYSQL") -> dict:
    """Read credentials without exposing them in errors. All stored dates use UTC."""
    options = {
        "host": os.getenv(f"{prefix}_HOST", "localhost"),
        "port": int(os.getenv(f"{prefix}_PORT", "3306")),
        "database": os.getenv(f"{prefix}_DATABASE", "shiva_temple_discovery"),
        "user": os.getenv(f"{prefix}_USER", "root"),
        "password": os.getenv(f"{prefix}_PASSWORD", ""),
        "charset": "utf8mb4",
        "autocommit": True,
        "connect_timeout": 5,
        "read_timeout": 30,
        "write_timeout": 30,
        "init_command": "SET time_zone = '+00:00', innodb_lock_wait_timeout = 5, "
                        "sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'",
    }
    if database_url:
        try:
            url = urlsplit(database_url)
            if url.scheme != "mysql" or not url.hostname or not url.path.strip("/") or url.query or url.fragment:
                raise ValueError
            options.update(host=url.hostname, port=url.port or 3306,
                           database=unquote(url.path[1:]), user=unquote(url.username or ""),
                           password=unquote(url.password or ""))
        except ValueError:
            raise ValueError("Use a mysql://user:password@host:3306/database URL; configure TLS through environment variables.") from None
    ca = os.getenv(f"{prefix}_SSL_CA")
    if ca:
        options.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)
    return options


class Connection:
    """PyMySQL connection with explicit transactions and nested savepoints."""
    def __init__(self, raw):
        self.raw = raw
        self.depth = 0

    def cursor(self):
        return self.raw.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.raw.close()

    @contextmanager
    def transaction(self):
        savepoint = f"shiva_savepoint_{self.depth}"
        nested = self.depth > 0
        if nested:
            with self.cursor() as cursor:
                cursor.execute(f"SAVEPOINT {savepoint}")
        else:
            self.raw.begin()
        self.depth += 1
        try:
            yield self
            if nested:
                with self.cursor() as cursor:
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.raw.commit()
        except BaseException:
            if nested:
                with self.cursor() as cursor:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            else:
                self.raw.rollback()
            raise
        finally:
            self.depth -= 1


def connect(database_url: str | None = None, *, prefix: str = "MYSQL") -> Connection:
    import pymysql
    from pymysql.constants import FIELD_TYPE
    from pymysql.converters import conversions

    if database_url is None:
        database_url = os.getenv("DATABASE_URL")
    converters = conversions.copy()
    converters[FIELD_TYPE.DATETIME] = _utc_datetime
    converters[FIELD_TYPE.TIMESTAMP] = _utc_datetime
    return Connection(pymysql.connect(conv=converters, **connection_options(database_url, prefix=prefix)))


def _utc_datetime(value):
    from pymysql.converters import convert_datetime

    parsed = convert_datetime(value)
    # The connection fixes the server session to UTC. Keep exported CSV dates
    # explicit so browsers in other time zones do not reinterpret naive values.
    return parsed.replace(tzinfo=timezone.utc) if isinstance(parsed, datetime) else parsed


def apply_migrations(conn, migrations_dir: Path) -> list[str]:
    """Apply checked-in, plain SQL migrations. MySQL DDL cannot be rolled back.

    Serialize installers using a database-scoped advisory lock. CREATE TABLEs
    are idempotent and the sole ALTER is checked for interrupted-install retries.
    Migrations contain no routines or semicolons within string literals.
    """
    if conn.depth:
        raise RuntimeError("Run migrations outside a transaction: MySQL DDL commits implicitly.")
    applied_now = []
    with conn.cursor() as cursor:
        cursor.execute("SELECT CONCAT('shiva_migrations_', LEFT(SHA2(DATABASE(), 256), 40))")
        lock_name = cursor.fetchone()[0]
        cursor.execute("SELECT GET_LOCK(%s, 10)", (lock_name,))
        if cursor.fetchone()[0] != 1:
            raise RuntimeError("Another migration process holds the database lock.")
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ) ENGINE=InnoDB""")
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            for migration in sorted(migrations_dir.glob("*.sql")):
                if migration.name in applied:
                    continue
                sql = re.sub(r"--[^\n]*", "", migration.read_text(encoding="utf-8"))
                for statement in sql.split(";"):
                    if not statement.strip():
                        continue
                    if migration.name == "002_add_google_maps_uri.sql":
                        cursor.execute("""SELECT COUNT(*) FROM information_schema.columns
                            WHERE table_schema = DATABASE() AND table_name = 'temple_candidates'
                            AND column_name = 'google_maps_uri'""")
                        if cursor.fetchone()[0]:
                            continue
                    cursor.execute(statement)
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
                applied_now.append(migration.name)
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
    return applied_now
