# Daily discovery expansion

`scripts/run_expansion_batch.py` connects the existing Python/MySQL discovery
queue to the local analysis portal. It defaults to Uttar Pradesh urban local
bodies, at most ten tasks and thirty HTTP attempts per India calendar day.
Each task may use up to three pages. It works through the existing reviewed
queue: `Shiva temple` searches first, then the other Phase 1 keywords. It does
not automatically import new states or widen the pilot scope.

## Commands

Run from the repository root with the existing `.env` configuration:

```sh
.venv/bin/python scripts/run_expansion_batch.py --dry-run
.venv/bin/python scripts/run_expansion_batch.py --export-only
.venv/bin/python scripts/run_expansion_batch.py
```

The dry run validates the baseline, reads the budget and counts pending tasks.
It never claims tasks, sends Google requests or writes reports. Export-only
publishes already-saved candidates without an API key or fresh billing check.
Normal execution runs a bounded batch and then publishes a snapshot only if
discovery completed successfully. Apply migration 007 before live execution.

The current schedule uses the defaults. `--limit`, `--max-requests`,
`--max-pages`, `--state` and `--location-type` allow deliberate campaign changes.
The command does not raise the configured monthly ceiling or refresh billing
observations. See [the budget runbook](FREE_ALLOWANCE_DISCOVERY.md).

## Budget and daily retries

The Google request ledger remains authoritative for cooperating workers. It
counts every HTTP attempt, including pagination and failures, and stops when
the monthly allowance is exhausted or the billing observation is stale. A new
Pacific billing month requires explicit configuration. Daily run keys use
Asia/Kolkata; these are intentionally distinct from Google's billing months.

Migration 007 adds `discovery_expansion_batches`, with one row per India date.
A MySQL advisory lock serializes expansion jobs against the same database.
After a day has started, another invocation on that day never spends again,
even if the prior process crashed or its report export failed. A completed day
can retry its export without another search. Failed/paused days require review
or an explicit export-only refresh of retained results. A still-running journal
row blocks future discovery until an operator investigates the interrupted run.
Do not delete journal rows or reset request reservations to force another batch.

The command stops on the first task failure. It does not retry failed tasks or
steal running tasks. Each new task requires enough remaining per-run allowance
for its maximum page count. An empty queue is reported without creating more
tasks; review measured yield and geography before extending the pilot.

Exit codes: 0 for completion, export-only, already completed, or dry run; 1 for
failure/needs-review; 2 for budget/worker-lock blocks. JSON output reports the
outcome without printing database credentials or API keys.

## Atomic portal updates

The baseline CSV remains the historical input. A consistent MySQL export is
merged by Place ID; the newest observation supplies fields, first-observed is
the earliest date, and last-observed is the latest date. Source files and the
database discovery-event history retain original attribution. A geographic
audit of the database candidates accompanies each snapshot. It flags review
needs, not verified boundaries or automatic exclusions.

Generated, git-ignored files live in `reports/expansion/`:

- `snapshots/<content-hash>.json`: a complete report set and geographic audit.
- `latest.json`: a small atomic pointer with counts and generation time.
- `last_run.json`: the most recent nonblocked run's outcome. Blocked runs report
  their reason on stderr; this file must not be interpreted as current billing status.

The snapshot file is fully written before the pointer changes. A malformed
source, incomplete export or write failure leaves the previous pointer intact.
The exporter refuses more than 250,000 candidates or files above 250 MiB rather
than silently truncating them. Identical data retains its previous snapshot and
generation time. Previous snapshots are retained for rollback.

Merged national-summary `total_discovered_candidates` counts input candidate
rows, and `duplicates_removed` counts overlapping IDs between those inputs.
These values are not raw Google search-occurrence counts. Confidence and
geographic summaries are recomputed from the deduplicated union. None of these
counts establishes a verified or exhaustive temple total.

The local Vite portal loads the latest expansion on startup, falling back to
the baseline when unavailable. While expansion is selected it checks the small
manifest every minute and downloads candidates only when the content hash
changes. It preserves filters during refresh. Manual baseline, pilot, sample,
or imported datasets suspend automatic replacement until expansion is selected
again. The Reports page shows the update time and additions since baseline.

## Scheduling and remaining setup

The published Dell n8n workflow, **Jai Bhole Nath - Daily Discovery**
(`jbnDailyDiscovery`), invokes the same bounded worker at 09:00 Asia/Kolkata.
The former Mac automation `daily-shiva-discovery-expansion` is paused. The
existing remote MySQL database, budget scope, reviewed queue and daily journal
remain authoritative. See [the Dell deployment runbook](DELL_DISCOVERY_NODE.md)
for private control endpoints, startup, validation and rollback.

The local Mac portal pulls snapshots over pinned SSH in the background when
the expansion view checks its manifest, at most once per minute while open.
It validates the content hash and publishes the snapshot before its pointer;
offline or failed sync keeps the last successful local dataset. Private SSH
configuration lives in git-ignored `.node-access/`, excluded from the Vite
server and Docker build context. No discovery work is scheduled on the Mac.

The current budget ledger still requires a real account-usage observation from
within 24 hours. The schedule must never stamp yesterday's number with today's
time, assume zero usage, raise the cap, or bypass this check. Fully unattended
billing reconciliation needs an authenticated read-only usage source covering
the billing account; that connection is not configured by this change.

This increment updates the local analysis portal. Public builds still use their
release snapshot. Hosting the expansion feed and configuring permitted data
retention/display is a separate deployment step; no credentials or private
research records are copied into `frontend/public/` or `dist`.

## Verification

Core tests cover merge provenance, malformed inputs, atomic-write failures,
daily idempotency, concurrent-worker locks, request caps, failures, interrupted
days and missing budgets. MySQL tests use disposable databases and mocked
Google responses. Frontend tests cover manifest polling, snapshot consistency,
path validation and unavailable updates.
