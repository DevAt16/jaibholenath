# Phase 1.1 District Baseline Release

Release date: May 17, 2026

## Purpose

This release freezes the Phase 1.1 district-only discovery baseline for likely
Shiva temple candidates in India.

It is designed as a research and review baseline, not as an exact real-world
temple count or an official cultural census.

## Scope

Included:

- Active LGD district rows only
- Google Places Text Search discovery results
- Deduplicated candidate view by Google Place ID
- Candidate discovery event ledger for query-to-place attribution
- District baseline reports, methodology/work report, social cards, and audit
  files

Excluded:

- Towns
- Urban local bodies
- Sub-districts / tehsils
- Villages
- Final manual temple verification

## Source Of Truth

District names and district codes:

- Local Government Directory (LGD)
- Data.gov.in LGD district resource
- Ministry of Panchayati Raj context

Temple candidate names:

- Google Places `displayName`
- Treated as discovery evidence only, not canonical temple-name truth

## Final Baseline Numbers

```text
active LGD district rows: 785
active districts with LGD codes: 785
district search tasks completed: 7,065 / 7,065
failed active district tasks: 0
raw district-level discovered occurrences: 229,495
unique district-attributed Google Place IDs: 74,117
high-confidence Shiva candidates: 43,877
medium-confidence Shiva candidates: 7,366
low-confidence possible temple candidates: 22,874
duplicates removed: 155,378
district discovery events: 74,137
district source locations with at least one candidate event: 772
```

## Final Retry Note

The previous failed district task:

```text
Mahadev temple in Rohtas district, Bihar, India
```

was rerun successfully on May 17, 2026:

```text
20 raw results
20 response-unique results
```

After this retry, all active Phase 1.1 district tasks are complete.

## Folder Contents

```text
csv/
  national_summary.csv
  state_counts.csv
  district_counts.csv
  candidate_review.csv

pdf/
  consolidated_phase1_1_district_baseline_report.pdf
  phase_1_1_consolidated_work_report.pdf

html/
  consolidated_phase1_1_district_baseline_report.html
  phase_1_1_consolidated_work_report.html

social_cards/
  LinkedIn and square PNG/HTML social cards

audit/location_verification/
  district alignment and manual exception review files

data/
  prepared_locations_lgd_districts.csv

docs/
  README.md
  PHASE_1_1_DISTRICT_BASELINE.md
```

## Interpretation Warning

Use this release as:

```text
An uncertainty-aware district-level discovery baseline of likely Shiva temple
candidates in India, generated from official Indian district data and Google
Places discovery results.
```

Do not describe it as:

```text
the exact number of Shiva temples
an official census of temples
a complete temple database
```

## Recommended Next Step

Start Phase 1.2 separately:

```text
town + urban local body expansion
```

Do not mix Phase 1.2 outputs into this frozen Phase 1.1 district baseline.
