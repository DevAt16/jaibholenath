# Discovery within the India free allowance

The target is no paid Places usage. This increment adds conservative request
accounting and offline expansion planning. It does not activate a Google campaign,
configure a real billing account, apply hosted migrations or schedule recurring runs.

## Billing assumptions

As checked on 28 September 2026, Google lists 35,000 free monthly requests for
Places API Text Search Pro (India). The current field mask selects that SKU. The
project ceiling is at most 30,000 accounted requests, leaving 5,000 below the
published free threshold. This is a project policy, not a Google-enforced spend
cap. India pricing must be confirmed for the billing account containing the API
key's project. Searching Indian places does not establish account eligibility.

- [India pricing](https://developers.google.com/maps/billing-and-pricing/pricing-india)
- [Billing aggregation and Pacific monthly resets](https://developers.google.com/maps/billing-and-pricing/overview)
- [Cost controls: budget alerts do not stop spending](https://developers.google.com/maps/billing-and-pricing/manage-costs)

This ledger is not connected to Cloud Billing. Every cooperating discovery
worker for the same billing account must share ONE database and account ID.
Separate databases, other projects and other software cannot be constrained by
this runner. Check total usage across all projects and reserve headroom for other
consumers. Billing reports can lag; an inaccurate usage observation or unexpected
external usage can still lead to charges. Configure appropriate Google Cloud
quotas too. The tool does not claim a guarantee about the account's final bill.

Free usage does not change the [Places storage policies](https://developers.google.com/maps/documentation/places/web-service/policies)
or [Maps terms](https://cloud.google.com/maps-platform/terms). Confirm that the
intended collection and retained fields are permitted before scaling; the current
candidate storage/export design has not been certified as compliant by this work.

## Configure after checking the billing console

Apply the checked-in migrations to the intended discovery database using the
existing migration process. Migration 006 adds only budget and reservation tables.
Then set `GOOGLE_MAPS_BILLING_ACCOUNT_ID` in the environment alongside the existing
database URL and API key. No real account ID or usage values are committed.

```sh
python scripts/init_db.py
python scripts/places_budget.py configure \
  --month YYYY-MM \
  --observed-account-usage ACTUAL_TEXT_SEARCH_PRO_MONTHLY_USAGE \
  --external-reserve EXPECTED_OTHER_CONSUMERS_REQUESTS \
  --checked-at ACTUAL_CHECK_TIME_WITH_TIMEZONE \
  --confirm-india-pricing
python scripts/places_budget.py status
```

Replace placeholders with actual values, not zeros by assumption. `--checked-at`
accepts ISO 8601 with a timezone, for example `2026-09-28T12:00:00+05:30`. The
check must be in the current Pacific billing month, not in the future, and no
older than 24 hours. The explicit confirmation flag is an operator attestation;
it does not ask Google to verify eligibility. Use `--ceiling` for a lower cap.

On first configuration, console usage becomes the already-used allowance. Later
observations can increase accounted usage but never erase reservations or reduce
the previous usage floor. The allowance is:

```text
remaining = max(0, ceiling - accounted external/past usage
                          - reserved future external usage
                          - this ledger's HTTP reservations)
```

Recheck and refresh at least every 24 hours before running. A new month requires
a new explicit configuration; previous-month eligibility/usage is not silently
carried forward. Do not create another account key to reset usage. If restoring
an older discovery database backup, reconcile billing usage before resuming so
lost ledger rows do not become spendable allowance.

## Offline expansion planning

This requires neither database access nor an API key:

```sh
python scripts/plan_expansion.py data/prepared_locations_uttar_pradesh_ulbs.csv \
  --state 'Uttar Pradesh' --limit 50 --max-pages 3 \
  --request-budget 30000 --output reports/phase_1_2/up_pilot_plan.json
```

Create the output directory first. Output files cannot be overwritten. The
default scope is towns and urban local bodies; cities require `--include-cities`.
The default planning allowance is zero/unconfirmed. `--request-budget` changes
only the estimate, never authorizes requests or creates a monthly allowance.
`--all` plans all eligible rows without executing them. Missing-district rows
sort after rows with district attribution. Conflicting location identities are
withheld and included in the report for source cleanup.

The planner does not inspect the existing task database or claim these are new
queries. All-page estimates exclude retries and interrupted-query restarts.
Request counts cannot predict new unique candidates or verified temple counts.

## Run only after configuring allowance and preparing scoped tasks

```sh
python scripts/run_discovery.py --state 'Uttar Pradesh' \
  --location-type urban_local_body --limit 10 --max-pages 3 \
  --max-requests 30 --dry-run
```

The dry run reads budget status and matching pending-task count, without claims,
Google requests or writes. Removing `--dry-run` executes only existing pending
tasks matching the selected state/type. It does not import source locations or
generate expansion tasks. Defaults remain 10 tasks, 10 requests and one page.

Every HTTP attempt is atomically reserved under a MySQL row lock before network
I/O. Each pagination request counts separately. Concurrent workers cannot spend
the same remaining ledger allowance. Failed requests, uncertain outcomes and a
crash after reservation are conservatively counted; there are no automatic
refunds or HTTP retries. A changed field mask blocks requests until its billing
category is reviewed. There is no unguarded path in the provided Places client.

The runner claims one task at a time and commits each received result page. If a
budget limit is reached mid-query, the task goes back to pending and received
candidates/events remain saved. On retry, an interrupted query starts at page 1
because page tokens are not treated as durable across months. Those repeated
requests consume allowance again; Place IDs and discovery-event keys prevent
duplicate stored candidates/events. Use a per-run cap of at least `--max-pages`
when retrying to avoid repeatedly stopping at the same page.

A hard process kill or database outage can leave one claimed task `running`.
After confirming its worker has stopped, inspect and deliberately reset that
task to pending; the runner does not steal running tasks automatically. Ordinary
API failures remain `failed`, with any earlier received pages retained. A `done`
task means its configured page limit was processed, not exhaustive coverage.

## Verification

Unit tests cover Pacific summer/winter rollover, stale observations, missing
configuration, SKU changes, HTTP failures, offline estimates and ambiguous
source rows. MySQL tests cover concurrent workers racing for the final seven
requests, non-resettable usage, scoped claims and saving/resuming between pages.
All HTTP traffic in tests is mocked. Real Google calls are never needed.
