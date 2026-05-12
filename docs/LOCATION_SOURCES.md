# Location Sources

Phase 1 can grow location coverage by normalizing official location source files
into the project CSV format used by `scripts/import_locations.py`.

This document is about location names only. It does not claim temple counts.

For the district-only baseline plan, see `docs/PHASE_1_1_DISTRICT_BASELINE.md`.

## Recommended Sources

### LGD

Use Local Government Directory (LGD) for current administrative entities and
urban local bodies.

- Ministry page: https://panchayat.gov.in/en/lgd/
- LGD site: https://lgdirectory.gov.in/
- Data.gov catalog: https://www.data.gov.in/catalog/local-government-directory-lgd

Useful LGD downloads:

- Districts
- Sub-Districts
- Local Bodies

LGD local bodies include rural and urban bodies. The normalizer keeps urban
local bodies when type/category fields identify them as municipal, urban, nagar,
town panchayat, notified area, or cantonment bodies, and skips rural panchayat
types.

### Census 2011

Use Census 2011 for Census/statutory town names.

- Population Finder: https://censusindia.gov.in/census.website/en/data/population-finder

Prefer the download for:

```text
Basic Population Figures of India, States, Districts, Sub-District and Town (Without Ward), 2011
```

If you use a ward-level file, the normalizer deduplicates town rows, but the
without-ward file is cleaner.

## Normalize Source Files

Save downloaded LGD/Census files as CSV or JSON, then run:

```powershell
python scripts/prepare_location_sources.py `
  --state "Uttar Pradesh" `
  --lgd-districts data/source/lgd_districts.csv `
  --lgd-local-bodies data/source/lgd_local_bodies.csv `
  --census-towns data/source/census_towns_2011.csv `
  --output data/prepared_locations_uttar_pradesh.csv
```

Preview counts only:

```powershell
python scripts/prepare_location_sources.py `
  --state "Uttar Pradesh" `
  --census-towns data/source/census_towns_2011.csv `
  --dry-run
```

Append unique rows into the main location CSV:

```powershell
python scripts/prepare_location_sources.py `
  --state "Uttar Pradesh" `
  --census-towns data/source/census_towns_2011.csv `
  --output data/prepared_locations_uttar_pradesh.csv `
  --append-to data/locations.csv
```

Then import and generate search tasks:

```powershell
python scripts/import_locations.py data/locations.csv --source official_location_sources
python scripts/generate_search_tasks.py --dry-run
python scripts/generate_search_tasks.py
```

## Output Format

The normalizer writes:

```text
location_type,name,state_name,district_name,sub_district_name,state_lgd_code,district_lgd_code,sub_district_lgd_code,village_lgd_code,source
```

Mapped location types:

- LGD districts -> `district`
- LGD sub-districts -> `sub_district`
- LGD urban local bodies -> `urban_local_body`
- Census towns -> `town`

Villages are intentionally not part of the default expansion path. Add them only
when you intentionally want village-scale discovery tasks.
