# Uttar Pradesh pilot geography triage — 29 September 2026

The saved Phase 1.2 pilot has 206 distinct Google Place IDs from searches in
Achhnera and Bah, Agra district. The discovery export assigns the query district
to every result; that assignment is not proof of each place's real location.

The offline [review CSV](../../tmp/phase_1_2_pilot/geography_review_2026_09_29_v3.csv)
lists high-priority rows first. The [summary JSON](../../tmp/phase_1_2_pilot/geography_audit_2026_09_29_v3.json)
includes the source CSV hash and the inferred locality anchors.

| Triage result | Candidates |
| --- | ---: |
| High priority | 27 |
| Medium priority | 140 |
| Routine review | 39 |
| Address explicitly names another state | 8 |
| More than 50 km from the inferred query-town anchor | 27 |

The eight other-state addresses name Rajasthan (4), Karnataka (3) and Odisha
(1). These results may still be useful for India-wide discovery. Their current
Agra attribution should not be interpreted as actual location.

Anchors are medians of returned coordinates for records whose formatted address
names the queried town: 31 records for Achhnera and 10 for Bah. The 25 km and
50 km thresholds only prioritize review. They are not administrative boundaries,
and a result without a flag is not verified. The 165 addresses that omit the
query-town name are a weaker, separate review signal. No candidates were deleted
or moved between districts by this audit.

Regenerate both outputs from the current saved pilot, choosing new paths because
the script never overwrites existing audit files:

```sh
python scripts/audit_pilot_geography.py \
  --candidates tmp/phase_1_2_pilot/reclassified_results/candidate_review.csv \
  --locations tmp/phase_1_2_pilot/selected_locations.csv \
  --districts data/prepared_locations_lgd_districts.csv \
  --summary tmp/phase_1_2_pilot/new_geography_audit.json \
  --review-csv tmp/phase_1_2_pilot/new_geography_review.csv
```

The analysis UI can load the saved pilot from its local Reports & data view.
That switch replaces the browser's active dataset for the session and leaves the
frozen Phase 1.1 CSVs untouched. Pilot CSVs are served by the Vite development
server only; they are excluded from public builds.
