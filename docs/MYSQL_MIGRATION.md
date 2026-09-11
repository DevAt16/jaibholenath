# Switching discovery and portal visits to MySQL

Both Python database paths now use PyMySQL. The frontend still reads the same
CSV exports and uses the same visitor API JSON contract. No PHP is needed.

## New databases

Target MySQL 8.0.16 or newer, preferably 8.4, with InnoDB and utf8mb4. Check the
actual server version with `SELECT VERSION()`; a product labeled "MySQL" may be
MariaDB. The discovery integration suite targets MySQL, not MariaDB.

Install `python -m pip install -e '.[dev]'` and set `DATABASE_URL` as shown in
`.env.example`. PostgreSQL URLs are rejected rather than silently redirected.
`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` are
alternatives when DATABASE_URL is unset. The CLI loads .env; Gunicorn needs the
variables supplied by its service manager. Connections set UTC and strict SQL
mode so oversized values fail instead of being silently truncated.

Create an empty database, then run `python scripts/init_db.py`. The migration
runner applies 001–004. A counter-only database needs only 004, which can also
be run in phpMyAdmin. Give the public counter a dedicated user restricted to its
two tables. Keep migration privileges separate from application credentials.

MySQL DDL implicitly commits. The migration runner serializes installers with
GET_LOCK, records each completed file, and supports retrying an interrupted
CREATE TABLE or the known 002 column addition. Do not run unrelated DDL through
this runner or change its files after applying them. For manual SQL imports,
002 is a one-time ALTER; the Python runner checks whether its column exists.

## Existing PostgreSQL data

Changing source files does not convert, copy, or delete any existing database.
These rewritten migrations are a fresh MySQL baseline, not an in-place upgrade
of PostgreSQL or of unknown partially-created MySQL tables. Existing PostgreSQL
migration history remains available in Git.

Keep the PostgreSQL database and a backup until a separate data transfer is
validated. Preserve primary keys, parent/source relationships, candidate Place
IDs, search tasks and discovery events; convert timestamps to UTC. Report CSVs
alone do not contain all of that history and cannot restore a discovery database.
Audit indexed text values before transfer: most indexed names/keywords/Place IDs
are VARCHAR(255), LGD codes VARCHAR(32). Unique keys use case-sensitive collation.
Compare table counts, distinct Place IDs, task statuses, reports and relationships
before changing production connections. No production data transfer has been run.

## Tests

`python -m pytest` runs the unit tests and report query tests. To additionally run
real database tests, set `MYSQL_TEST_DATABASE_URL` to a disposable MySQL server
account with CREATE/DROP DATABASE permission (e.g. mysql://root:TEST_PASSWORD@127.0.0.1:3306/mysql).
Tests create and drop only randomly named shiva_test_* databases. The GitHub
workflow runs this suite against a disposable MySQL 8.4 service.

The tests cover schema installation/retry, Unicode, candidate deduplication,
foreign keys, transaction rollback, task claiming across workers, reports,
visitor retries and preservation of totals. They make no Google Places calls.

## Hosting

MySQL storage does not supply a Python runtime. Keep Python scripts on your
computer or a suitable server, and run the public WSGI API on a Python-capable
host. For a remote MySQL server, allow only the client server's IP and configure
verified TLS with the provider CA using MYSQL_SSL_CA / VISITS_MYSQL_SSL_CA.
