from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import REPO_ROOT
from shiva_discovery.db import apply_migrations, connect


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply PostgreSQL schema migrations.")
    parser.add_argument(
        "--migrations-dir",
        default=str(REPO_ROOT / "migrations"),
        help="Directory containing .sql migration files.",
    )
    args = parser.parse_args()
    migrations_dir = Path(args.migrations_dir)
    if not migrations_dir.is_absolute():
        migrations_dir = REPO_ROOT / migrations_dir

    with connect() as conn:
        applied = apply_migrations(conn, migrations_dir)

    if applied:
        print("Applied migrations:")
        for migration in applied:
            print(f"- {migration}")
    else:
        print("Database schema is already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
