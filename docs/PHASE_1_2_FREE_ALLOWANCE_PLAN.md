# Phase 1.2 dry-run expansion plan — 28 September 2026

Scope: improve likely Shiva candidate discovery using the existing Python/MySQL
pipeline and an operator-confirmed free monthly allowance. No Google calls,
location imports, task generation, hosted migrations or billing configuration
were performed for this plan. The Phase 1.1 release remains frozen.

## Available source and findings

The existing `data/prepared_locations_uttar_pradesh_ulbs.csv` contains 770 rows.
Its SHA-256 is `332cd03c9b4546b91c48f293ff9d2047c5139a36a3659168bbfe1615e683bcb7`.
Two Akbarpur records share the current import identity but have inconsistent
sub-district attribution. Both are withheld until their identifiers/geography
are resolved; they must not be silently merged.

| Measure | Full source preview | Initial pilot preview |
| --- | ---: | ---: |
| Eligible locations selected | 768 | 50 |
| Keywords per location | 9 | 9 |
| Potential search tasks | 6,912 | 450 |
| First-page requests | 6,912 | 450 |
| Maximum requests at three pages, before retries | 20,736 | 1,350 |
| Selected locations missing district attribution | 275 | 0 |

The 30,000-request figure used for planning assumes an otherwise unused eligible
account allowance. Actual available requests can be lower because of current
usage or reservations for other consumers. Existing database tasks are not
deducted by this offline planner, so actual newly generated tasks can also be
lower. No candidate-count forecast is justified by these request estimates.

## Recommended first run

1. Confirm the billing account has India pricing and inspect current Text Search
   Pro usage across all linked projects. Set a reserve for other consumers.
2. Apply migration 006 to the intended discovery database and configure the
   allowance using the actual usage observation. See the [runbook](FREE_ALLOWANCE_DISCOVERY.md).
3. Review the selected 50-location pilot, source provenance and collection/storage
   permissions. Resolve the ambiguous Akbarpur entries before including them.
4. Import/generate only the reviewed pilot scope in a later execution step, then
   start with 10 tasks and at most 30 HTTP attempts. Check new unique candidates,
   overlaps and result quality before increasing the batch size.
5. Keep Phase 1.2 outputs separate. Expand to other town/ULB sources after this
   pilot provides measured yield and request-cost evidence.

The generated full and pilot JSON plans are local files under
`reports/phase_1_2/`; regenerate them with `scripts/plan_expansion.py`. They contain
location-derived query plans, not new Google data. The planner prioritizes rows
with district attribution, but that attribution is not proof of actual temple
geography. Regional-language search and adaptive geographic subdivision remain
later increments; they have not been implemented by this request-budget change.
