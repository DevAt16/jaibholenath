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

### 4. Import Verified Districts

After review:

```powershell
python scripts/import_locations.py data/prepared_locations_lgd_districts.csv --source lgd
```

### 5. Generate Phase 1.1 District Tasks Only

The current generator defaults to district, town, and urban local body. For a
strict Phase 1.1 run, add or use a district-only generation option before
creating tasks.

Target behavior:

```text
district locations × 9 Phase 1 keywords
```

No town or ULB tasks should be included in the Phase 1.1 baseline.

### 6. Run Discovery With Safe Limits

Example:

```powershell
python scripts/run_discovery.py --limit 25 --page-size 20 --max-pages 1
```

Increase gradually only after reviewing result quality and API costs.

### 7. Generate Reports

```powershell
python scripts/report_counts.py --output-dir reports --include-candidates --candidate-limit 5000
python scripts/generate_consolidated_pdf_report.py
```

All Phase 1.1 reports must clearly say:

```text
discovery counts, not exact real-world temple counts
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

## Immediate Next Step

Download from Data.gov.in:

```text
Local Government Directory (LGD) - Districts
```

Save it as:

```text
data/source/lgd_districts.csv
```

Then run the district normalization dry-run and compare the results before
importing.
