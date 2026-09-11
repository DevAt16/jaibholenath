# Visitor API — Hostinger Express deployment

This Node.js service replaces the Python visitor API for hosted deployments.
Temple discovery remains Python + MySQL. Existing counter tables and session
hashes are compatible; do not reset totals when switching API implementations.

## Deploy alongside jaibholenath.com

1. Push the repository including visitor-api/package-lock.json. Keep the existing
   frontend deployment configured as Vite with root `frontend`.
2. Add a separate Hostinger Node.js web app from the same GitHub repository.
   Select the production branch and configure:

   | Setting | Value |
   |---|---|
   | Framework | Express |
   | Root directory | visitor-api |
   | Node version | 24.x |
   | Package manager | npm |
   | Build command | npm run build |
   | Output directory | dist |
   | Entry file, relative to output | server.js |
   | Start command, if requested | npm start |

   The source entry is `src/server.js`; the build entry is `dist/server.js`.
   If the entry-file field is relative to the project root, use `dist/server.js`.
   The build needs no database credentials and never runs migrations.
3. Set backend environment variables before starting the deployment:

   ```dotenv
   VISITS_DATABASE_URL=mysql://USER:PASSWORD@HOST:3306/DATABASE
   VISITS_ALLOWED_ORIGIN=https://jaibholenath.com
   ```

   Use the actual database hostname, username and full database name provided by
   Hostinger. Percent-encode special characters in URL credentials (`@` → `%40`).
   Use a dedicated counter account: SELECT/INSERT on portal_visit_sessions and
   SELECT/UPDATE on portal_visit_totals. Do not use the discovery database user.
   Hostinger supplies PORT; the service binds to that port on 0.0.0.0.
   Never put credentials in frontend VITE variables or GitHub source files.
4. If the counter tables do not exist, select the counter database in
   phpMyAdmin/DBeaver and run `migrations/004_portal_visits.sql` from the repository
   using the database owner account. It preserves an existing counter total.
5. Connect `api.jaibholenath.com` to this Express app using Hostinger's custom
   domain flow, complete its DNS instructions, and confirm HTTPS is active.
   Keep jaibholenath.com assigned to the existing Vite app.
6. Open `https://api.jaibholenath.com/api/visits`. Expect JSON with a numeric total,
   not HTML. `/health` checks only that the process is alive; `/api/visits` checks
   the database too. A new database returns `{"total":0}`.
7. Set **on the Vite frontend deployment**:

   ```dotenv
   VITE_VISITS_API_URL=https://api.jaibholenath.com/api/visits
   ```

   Rebuild/redeploy the frontend. Visit jaibholenath.com and open the footprints
   tooltip. A new tab session registers once; reloading the same tab reuses it.

If the app cannot connect to MySQL, check the host and account permissions and,
where required, allow the app server in Hostinger Remote MySQL settings. For
remote TLS configure `VISITS_MYSQL_SSL_CA` to a deployed CA certificate file;
certificate and hostname verification stay enabled. Do not disable verification.
Only the exact allowed origin is accepted; www.jaibholenath.com must redirect to
jaibholenath.com if that is the configured canonical origin.

Configure request-rate limits on /api/visits at the host/proxy. CORS is a browser
access rule, not authentication, and anyone able to forge requests can influence
this lightweight session counter. It is not a unique-person or audited metric.
Pool size, waiting queue, request body size, and database waits are bounded.

## API contract

GET /api/visits → {"total": number}, without incrementing.
POST /api/visits with Origin and JSON {"session_id": "UUIDv4"} records one session.
OPTIONS supports the configured frontend origin; no credentials/cookies needed.
Tokens are canonicalized to lowercase and SHA-256 hashed exactly as in Python.
Registrations lock the total row and commit the token and total atomically.
Failures return generic JSON and never invent a zero or disclose SQL credentials.

## Local verification

From visitor-api: `npm ci`, `npm test`, `npm run build`.
HTTP tests use an in-memory store. For real MySQL coverage set
MYSQL_TEST_DATABASE_URL to a disposable MySQL server account with CREATE/DROP
DATABASE privileges. The test creates/removes only a random shiva_node_test_*
database, including testing rollback after a simulated update failure.
The GitHub MySQL workflow runs these tests against MySQL 8.4.

For local development copy .env.example to .env and run `npm run dev`.
Production `npm start` reads variables provided by Hostinger, not a .env file.

Hostinger reference:
https://www.hostinger.com/support/how-to-deploy-a-nodejs-website-in-hostinger/
