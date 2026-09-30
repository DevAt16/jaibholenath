# Uttar Pradesh pilot quality audit — 29 September 2026

The first 10 searches returned 294 result occurrences, deduplicated to 206
Google Place IDs. This audit compares the saved pilot CSV with the frozen Phase
1.1 district baseline CSV, which has 74,117 distinct IDs. Four pilot IDs are
already in that baseline; 202 are new to the saved baseline. This does not mean
202 newly identified real-world Shiva temples. Names, temple identity and actual
geography still require review.

The classifier change affects nine saved pilot rows:

| Previous | Revised | Rows | Reason |
| --- | --- | ---: | --- |
| Low | High | 6 | Hindi शिव/महादेव names and the `Siv mandir` spelling |
| High | Low | 3 | `Shiva house/home` names without a temple word |

The nine audited rows were updated in the live discovery database after their
names and previous classifications were checked. Its name-only confidence totals
are now 144 high, 15 medium and 47 low. The previous values are backed up in
`tmp/phase_1_2_pilot/before_reclassification_20260929T064728Z.json`; the first
pilot export remains a historical snapshot. No further Google calls were needed.

The reproducible [audit JSON](../../tmp/phase_1_2_pilot/quality_audit_2026_09_29.json)
records each changed Place ID, both CSV SHA-256 hashes and the transition counts.
Regenerate it with:

```sh
python scripts/audit_pilot_quality.py \
  --baseline reports/phase_1_1_district_baseline/candidate_review.csv \
  --pilot tmp/phase_1_2_pilot/results/candidate_review.csv \
  --output tmp/phase_1_2_pilot/new_quality_audit.json
```

The first queries for Achhnera also returned some listings in other towns. The
stored district is the search location's district, not independent proof of a
result's geography. Review place addresses or coordinates before treating
district-level counts as precise. Keep the frozen Phase 1.1 release unchanged.
