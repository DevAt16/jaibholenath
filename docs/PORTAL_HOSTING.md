# Portal release and visitor counter

The portal remains local until deployment is requested. Its footer shows the
version from `frontend/package.json`; changing that value and rebuilding updates
the displayed version. `Preview` describes the current portal release stage,
while `Phase 1` describes the discovery project.

## Hostinger deployment options

Upload only the contents of `frontend/dist` for the static portal. Build with
`npm run build` from `frontend`. Hash navigation needs no server route rewrites.
Never upload the repository, `.env` files, database credentials, or Python source
into the public web directory. Report CSV files inside `dist` are public downloads.

Hostinger documents Python support on VPS hosting, not Web/Cloud plans:
[Hostinger supported languages](https://www.hostinger.com/support/which-programming-languages-and-frameworks-are-supported-at-hostinger/).
The static portal can be hosted separately from the counter. A Web/Cloud plan
therefore needs the Python API on another suitable host; a VPS can run both.
No hosting service has been provisioned by these changes.

## What a visit means

The Footprints icon opens on mouse hover, keyboard focus, or tap/click; Escape,
clicking outside, or tapping again dismisses it. It displays the shared recorded
visit total, not unique people. One random token is stored in sessionStorage per
browser tab session. Refreshes and hash navigation reuse it. Tabs duplicated by
the browser can inherit the same token. If storage is blocked, deduplication lasts
only for the current page load. Bots and clients that block JavaScript can make
the figure differ from hosting analytics. This is a lightweight counter, not an
audited audience metric.

The API stores a SHA-256 hash of a random UUID and a recording timestamp. It does
not store names, IP addresses, fingerprints, locations, or browsing paths in its
counter tables. Hosting access logs have their own settings.

An empty `VITE_VISITS_API_URL` disables collection and displays “Not connected
yet”. An API failure displays “Visits unavailable”; it never invents a zero.
Keep the endpoint empty in local development to avoid inflating production totals.

## Counter backend setup (before enabling collection)

Use Python 3.10+ and PostgreSQL. On the API host:

1. Install this project (`python -m pip install -e .`) and Gunicorn in its virtual
   environment. Configure a dedicated PostgreSQL database and restricted API role.
2. Apply **only** `migrations/004_portal_visits.sql` to the counter database as its
   migration/owner role. The runtime role needs SELECT/INSERT on
   `portal_visit_sessions` and SELECT/UPDATE on `portal_visit_totals`. It needs no
   access to discovery tables, schema creation, deletion, or migrations.
3. Set server-side environment variables using the host's secret configuration:
   `VISITS_DATABASE_URL` (the runtime role's connection URL) and
   `VISITS_ALLOWED_ORIGIN` (the exact public portal origin, such as
   `https://your-domain.example`, without a trailing slash).
4. Run the WSGI app behind HTTPS using a managed service, for example:

   ```sh
   gunicorn --bind 127.0.0.1:8001 --workers 2 shiva_discovery.visits_api:application
   ```

   [Gunicorn running instructions](https://docs.gunicorn.org/en/21.0.1/run.html).
   Configure the reverse proxy to forward `/api/visits` to that service, preserving
   the path and Origin header. Use request-body limits and rate limiting on that
   route (for example, a small burst with one request per second per client).
   The public Origin check is not authentication or a bot-proof rate limit.
5. For a same-origin deployment set `VITE_VISITS_API_URL=/api/visits` in the
   frontend build environment. For a separately hosted API use its full HTTPS
   `/api/visits` URL. The configured public origin is allowed by the API's CORS
   response. Rebuild and upload the resulting frontend assets.
6. Verify GET returns `{"total":0}` for a newly initialized database. A POST with
   a random UUIDv4 `session_id` and the configured Origin increments once; a
   retry with that same token does not increment. Test on a staging database so
   test requests are not counted in the production total.

The PostgreSQL insert and total increment commit together in one transaction.
A unique session hash prevents concurrent retries from double counting. The
singleton total is updated atomically, including across multiple server workers.
Retain the counter tables across deployments; do not reset them when replacing
static files. Removing old session hashes would change retry behavior.

## Validation

- Frontend: `npm test` and `npm run build` from `frontend`.
- API: `python -m pytest tests/test_visits_api.py` from the repository root.
- PostgreSQL integration: install development dependencies, point
  `VISITS_TEST_DATABASE_URL` to a disposable test database, and run
  `python -m pytest tests/test_visits_postgres.py`. The test creates an isolated
  temporary schema, checks concurrent sessions/retries, then removes that schema.

The actual Hostinger account, domain, and production database still need to be
configured. Backend request tests use a test store; they do not by themselves
establish a working PostgreSQL deployment.
