# Phase 1.1 District Baseline

## Purpose

Phase 1.1 should establish a clean district-level baseline for Shiva temple
candidate discovery across India.

This phase is intentionally narrower than the broader Phase 1 pipeline. The goal
is a defensible, comparable, government-readable baseline built only from
district-level search tasks.

## Current Decision

Use only:

```text
location_type = district
```

Do not include these in Phase 1.1 task generation:

```text
town
urban_local_body
sub_district
village
```

District-only is the right baseline because:

- Districts are official, widely understood administrative units.
- District reports are easier to explain to researchers, government teams, and
  stakeholders.
- Search volume is controlled and comparable.
- It avoids mixing district, town, ULB, tehsil, and village boundary concepts too
  early.
- It gives us a national benchmark before adding deeper geographic detail.

## Source Of Truth For District Names

Use the Data.gov.in LGD catalog:

```text
Local Government Directory (LGD) - Districts
```

Direct resource page:

```text
https://www.data.gov.in/resource/local-government-directory-lgd-districts
```

As checked on May 12, 2026, the Data.gov.in resource page lists:

```text
Catalog: Local Government Directory (LGD)
Ministry / Department: Ministry of Panchayati Raj
Published On: 22/07/2022
Updated On: 06/05/2026
License: Government Open Data License - India
```

Save the downloaded file as:

```text
data/source/lgd_districts.csv
```

LGD district data should be treated as the administrative source for district
names and LGD district codes. Google Places remains only a discovery source for
temple candidates.

## What We Already Learned

The file currently named:

```text
data/source/census_towns_2011.csv
```

is not a town file. Its headers and rows indicate Uttar Pradesh sub-district
data:

```text
state_code
state_name_english
district_code
district_name_english
subdistrict_code
subdistrict_name_english
```

It generated:

```text
350 Uttar Pradesh sub_district rows across 75 districts
```

This is useful for hierarchy and later sub-district work, but not for town-level
task expansion.

The file:

```text
data/source/lgd_local_bodies.csv
```

is useful for Phase 1.2, not Phase 1.1. It contains local body coverage rows,
mostly rural panchayats, and can be filtered to urban local bodies.

For Uttar Pradesh it produced:

```text
770 unique urban_local_body rows
```

This is valuable later, but it should not be mixed into the Phase 1.1 district
baseline.

## Phase Roadmap

```text
Phase 1.1 = District-only national baseline
Phase 1.2 = Town + urban local body expansion
Phase 1.3 = Sub-district / tehsil expansion
Phase 1.4 = Selective village-level pilots
```

## District Verification Plan

After downloading `data/source/lgd_districts.csv`, verify district coverage
before generating or running new tasks.

### 1. Normalize District Source File

```powershell
python scripts/prepare_location_sources.py `
  --lgd-districts data/source/lgd_districts.csv `
  --output data/prepared_locations_lgd_districts.csv `
  --dry-run
```

If the dry-run looks correct:

```powershell
python scripts/prepare_location_sources.py `
  --lgd-districts data/source/lgd_districts.csv `
  --output data/prepared_locations_lgd_districts.csv
```

Expected output type:

```text
district
```

### 2. Review Prepared Districts

Check that the prepared file contains:

```text
location_type
name
state_name
district_name
state_lgd_code
district_lgd_code
source
```

No towns, ULBs, sub-districts, or villages should be present in the Phase 1.1
district source file.

### 3. Compare Against Existing Database

Compare:

```text
prepared LGD districts
```

against:

```text
india_locations where location_type = 'district'
```

We need to identify:

- Districts present in LGD but missing from the database.
- Districts present in the database but not in LGD.
- Duplicate district rows.
- District rows with missing `state_name`.
- LGD code mismatches where codes are available.

Use:

```powershell
python scripts/align_lgd_districts.py `
  --lgd-districts data/prepared_locations_lgd_districts.csv `
  --output reports/location_verification/district_alignment_review.csv
```

This writes a review CSV with:

```text
auto
review
missing_in_db
db_only
```

Only apply auto-safe alignments after reviewing the summary:

```powershell
python scripts/align_lgd_districts.py `
  --lgd-districts data/prepared_locations_lgd_districts.csv `
  --output reports/location_verification/district_alignment_review.csv `
  --apply-auto
```

Before the first apply, export a district snapshot for audit/rollback:

```text
reports/location_verification/db_districts_before_lgd_alignment.csv
```

Alignment result after applying auto-safe rows:

```text
LGD district rows: 785
DB district rows: 784
DB district rows with LGD codes: 783
remaining LGD missing in DB: 2
remaining DB-only districts: 1
manual review rows: 0
```

Remaining manual decisions:

```text
LGD-only: Assam / Bajali
LGD-only: Assam / Tamulpur
DB-only: Arunachal Pradesh / Itanagar Capital Complex
```

These should be handled deliberately before declaring Phase 1.1 district
coverage complete.

Final manual exception handling completed:

```text
Inserted LGD-only: Assam / Bajali
Inserted LGD-only: Assam / Tamulpur
Marked inactive: Arunachal Pradesh / Itanagar Capital Complex
```

Final active district coverage:

```text
LGD district rows: 785
active DB district rows: 785
active DB district rows with LGD codes: 785
LGD districts missing from active DB rows: 0
active DB districts not in LGD: 0
```

The inactive `Itanagar Capital Complex` row is retained for audit/history, but
it is outside the LGD district baseline and should not be used for Phase 1.1 task
generation.

### 4. Import Verified Districts

After review:

```powershell
python scripts/import_locations.py data/prepared_locations_lgd_districts.csv --source lgd
```

### 5. Generate Phase 1.1 District Tasks Only

The default generator still supports the broader Phase 1 scope: district, town,
and urban local body. For a strict Phase 1.1 run, use `--district-only`.

Target behavior:

```text
district locations x 9 Phase 1 keywords
```

No town or ULB tasks should be included in the Phase 1.1 baseline.

Preview:

```powershell
python scripts/generate_search_tasks.py --district-only --dry-run
```

Insert missing district-only tasks:

```powershell
python scripts/generate_search_tasks.py --district-only
```

### 6. Run Discovery With Safe Limits

Example:

```powershell
python scripts/run_discovery.py --limit 25 --page-size 20 --max-pages 1
```

Increase gradually only after reviewing result quality and API costs.

### 7. Generate Reports

```powershell
python scripts/report_counts.py `
  --district-only `
  --output-dir reports/phase_1_1_district_baseline `
  --include-candidates `
  --candidate-limit 100000

python scripts/generate_consolidated_pdf_report.py `
  --report-dir reports/phase_1_1_district_baseline `
  --html-output reports/phase_1_1_district_baseline/consolidated_phase1_1_district_baseline_report.html `
  --pdf-output reports/phase_1_1_district_baseline/consolidated_phase1_1_district_baseline_report.pdf `
  --report-kicker "Phase 1.1 District Baseline" `
  --report-title "Shiva Temple Discovery`nDistrict Baseline Insights" `
  --report-subtitle "A district-only baseline generated from active LGD district locations, Google Places discovery output, deduplication, and Shiva-confidence classification."

python scripts/generate_phase1_1_work_report.py

python scripts/generate_phase1_1_social_cards.py
```

All Phase 1.1 reports must clearly say:

```text
discovery counts, not exact real-world temple counts
```

### 8. Maintain Discovery Attribution History

The deduped `temple_candidates` table stores the latest candidate view. The
`candidate_discovery_events` table stores the query-to-place ledger:

```text
candidate
Google Place ID
search task
keyword
search query
source location
source location type
result position
observed place name/address/coordinates
```

New discovery runs write to this table automatically.

Backfill the Phase 1.1 district baseline as latest-known attribution events:

```powershell
python scripts/backfill_discovery_events.py --district-only --dry-run
python scripts/backfill_discovery_events.py --district-only --all
```

Current Phase 1.1 attribution result after the Rohtas retry:

```text
district discovery events: 74,137
distinct district-attributed candidates: 74,117
events linked to search tasks: 74,137
district source locations with at least one candidate event: 772
```

Use `candidate_discovery_events` for multi-query and multi-location attribution
analysis. Keep `temple_candidates` as the deduped latest candidate table.

## Phase 1.1 Freeze Status

As of May 17, 2026, Phase 1.1 is ready to freeze as a district-only release:

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
district discovery events: 74,137
```

The previous failed task for:

```text
Mahadev temple in Rohtas district, Bihar, India
```

was rerun successfully on May 17, 2026 and returned:

```text
20 raw results
20 response-unique results
```

The frozen release artifacts should be copied under:

```text
reports/releases/phase_1_1_2026_05_17/
```

## Wording For External Use

Recommended phrase:

```text
An uncertainty-aware district-level discovery baseline of likely Shiva temple
candidates in India, generated from official Indian district data and Google
Places discovery results.
```

Avoid:

```text
exact number of Shiva temples
official census of temples
complete temple database
```

## Next Step After Freeze

Start Phase 1.2 as a separate scoped expansion:

```text
town + urban local body discovery
```

Do not mix Phase 1.2 outputs into the frozen Phase 1.1 district baseline.
