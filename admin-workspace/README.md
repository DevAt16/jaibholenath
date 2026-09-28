# Jai Bholenath research workspace

Local first milestone, v0.2.0 Preview: owner authentication, pilot dashboard,
paginated candidate queue, evidence-backed review revisions and audit history.
The public portal, visitor API and Python discovery runner stay separate.

## Run locally

Requires Node.js 22+ and MySQL 8.4. Use a **separate development database**.
The migration creates only new `admin_*` tables. No paid discovery calls run.

```sh
cd admin-workspace
npm ci
cp .env.example .env
# Edit ADMIN_DATABASE_URL to point to your development database.
npm run migrate
npm run owner
npm run seed
npm run dev
```

Open http://127.0.0.1:5176. Owner setup asks for an email and a hidden password
(14–256 characters, twice). Use `pawar.devashish@gmail.com` for this pilot.
Running `npm run owner` again for the same email resets the password and revokes
all sessions. There is no public registration or default password.

The actual database is selected by `ADMIN_DATABASE_URL`; do not assume the
example port or a temporary server is active. As checked on 28 September 2026,
this workspace points to a persistent hosted development database running
MariaDB 11.8.9, with 52 pilot candidates. The supported CI target remains MySQL
8.4; JSON documents are decoded consistently for both servers. Hosting-provider
backup retention has not been independently checked.

The old `/tmp/shiva-admin-mysql` preview is no longer present on this machine.
Do not use temporary directories for ongoing research data. If using
`scripts/local-setup.js`, it is a one-time convenience for an isolated
localhost:33316 server and refuses existing `.env` files/databases. It is not a
production provisioner. Replace its generated owner password with `npm run
owner`, then delete `.local-owner-password`. The server never reads that file.

## Private backups and recovery

Back up before a migration or review batch and after a working session:

```sh
mkdir -p private-backups
npm run backup -- private-backups/pilot-YYYY-MM-DD.json
```

The command uses a consistent read-only transaction. It saves owner account
password hashes, original candidate snapshots, all revisions and audit events.
Active sessions and login throttles are excluded; recovered users must sign in
again. Files are created exclusively (no overwrite), with owner-only file
permissions, and are ignored by Git. They are **private, unencrypted backups**,
not public review exports. Keep an additional copy in your own protected backup
storage; this command does not configure off-machine retention. The pilot limit
is 10,000 rows per table and 64 MiB; exceeding it fails without saving a partial
backup. Avoid schema changes while a backup is running.

Use a disposable local MySQL server with CREATE/DROP DATABASE privileges to
test recovery. Its URL is separate from the source workspace URL:

```sh
export ADMIN_RESTORE_DATABASE_URL='mysql://LOCAL_TEST_USER:ENCODED_PASSWORD@127.0.0.1:33317/mysql'
npm run restore-check -- private-backups/pilot-YYYY-MM-DD.json
```

This creates a random recovery database, restores the fixed admin table set,
compares every durable row using a SHA-256 checksum, and drops only that new
database. Corruption, foreign-key failures and nonempty admin tables fail safely.
Checksums detect accidental changes; they are not signatures of authenticity.

For actual local recovery, `npm run restore -- FILE` keeps the newly created
database after verification and prints its name. Provision a local runtime user
with the privileges below, then point a local app's `ADMIN_DATABASE_URL` at that
database. Neither restore command overwrites the source or restores to a remote
host. Keep the source backup until the recovered workspace has been inspected.

## Data and review behavior

- Seeding reads only the existing public CSV, scoped by both state (Madhya
  Pradesh) and source district (Ujjain, Khandwa, Gwalior), at most 2,000 rows.
  Currently 52 candidates match. Repeat runs retain existing snapshots/reviews.
- Each candidate preserves its Place ID, original JSON and SHA-256 digest.
  Reviewed geography starts blank; query attribution is not actual geography.
- Each save creates a full revision containing evidence, methodology, author
  and date, plus an audit event in the same transaction. Stale saves return 409
  and the UI retains unsaved input. Expanded history shows the full document.
- Outcomes: in review, needs evidence, owner verified, rejected. Revising a final
  outcome requires a reopening reason. Possible duplicates stay needs evidence
  with a matching-record reference until linked duplicate decisions are added.
- Verification requires supported identity/geography, a checked temple pin,
  duplicate check, rationale, and two independent origins including an official,
  institutional or firsthand reference. Validation checks completeness; the owner
  must assess truth and independence. This is proposed pilot standard v1, not
  institutional certification or independent peer review.
- Evidence remains private even when marked as an intended public citation.
  Cultural documentation, linked duplicates, release/export/publishing, uploads
  and Python job controls are later increments. No fake publish/job actions exist.

## Security and future hosting

Express serves a lightweight HTML/CSS/JavaScript UI and API on the same origin,
with no frontend build step. Hostinger entry file would be `src/server.js`,
project root `admin-workspace`. Production provisioning/deployment is a separate
step; this work does not access any hosted database or deploy the app.

For hosting set `NODE_ENV=production`, `HOST=0.0.0.0`, the assigned `PORT`, and
`ADMIN_ORIGIN=https://admin.jaibholenath.com`. Never expose local HTTP settings
publicly. MySQL credentials belong only in server environment variables;
URL-encode special password characters. Use `ADMIN_MYSQL_SSL_CA` when a verified
TLS database connection is required by the host.

Passwords use salted scrypt. Opaque session tokens are hashed in MySQL and expire
after eight hours; cookies are HttpOnly, SameSite=Strict and Secure in production.
Every private API route authenticates on the server. Mutations require exact
Origin and a session CSRF token. The persistent account-wide login limit is ten
attempts per fifteen minutes. It does not trust forwarded IP headers; hostile
attempts can temporarily lock out the owner. Add correctly configured edge rate
limiting before broad public exposure. Responses are no-store with a restrictive
CSP; database error details are not returned. Evidence is text, never fetched or
executed as markup.

Use a separate migration/bootstrap account. Production runtime privileges:

| Tables | Privileges |
| --- | --- |
| admin_users | SELECT |
| admin_sessions, admin_login_limits | SELECT, INSERT, UPDATE, DELETE |
| admin_candidates | SELECT, UPDATE |
| admin_record_revisions, admin_review_events | SELECT, INSERT |

The runtime should have no DDL or revision update/delete access. The local
development account permits setup commands and is not a production privilege
template. Retain review/audit history and back it up before migrations. Expired
session/login rows are cleaned on subsequent login activity.

## Tests

```sh
npm test
# Creates and drops disposable databases on a test server:
MYSQL_TEST_DATABASE_URL=mysql://TEST_USER:TEST_PASSWORD@127.0.0.1:33316/mysql npm test
```

Without that URL, integration is explicitly skipped. Tests cover evidence gates,
input validation, hashing, authentication, CSRF, persistent throttling, concurrency,
UTC audit timestamps, transaction rollback, filtering and logout. CI runs both.

Earlier local browser QA covered login, search, blocked verification, evidence saving
and history retrieval using a disposable fixture, which was then removed. No
pilot candidate was substantively reviewed by QA.
