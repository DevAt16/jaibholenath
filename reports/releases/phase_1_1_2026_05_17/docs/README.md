# Shiva Temple Discovery

Phase 1 is a backend-only discovery system for likely Shiva temple candidates in India. It imports Indian location records, generates bounded Google Places Text Search tasks, stores deduplicated candidates by Google Place ID, classifies Shiva confidence from discovered names, and exports discovery count reports.

This phase does not build the final website and does not claim exact real-world temple counts. Counts are discovery counts from Google Places API and are meant for later verification.

## Phase 1 Scope

- Maintain a PostgreSQL master location table for Indian states, districts, sub-districts, cities, towns, villages, and urban local bodies.
- Generate search tasks from district, town, and urban local body locations by default.
- Optionally include city or village tasks with explicit flags.
- Call Google Places Text Search with safe limits.
- Deduplicate temple candidates by `google_place_id`.
- Classify candidates as `high`, `medium`, or `low` Shiva confidence.
- Export national, state-wise, and district-wise CSV reports.

## Requirements

- Python 3.10+
- PostgreSQL
- Google Places API key with Places API enabled

Install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Environment

Copy `.env.example` to `.env` or export equivalent environment variables in your shell. The scripts auto-load a local `.env` file when present. Secrets must stay in environment variables and must not be committed.

Required for database scripts:

```text
DATABASE_URL=postgresql://postgres:change-me@localhost:5432/shiva_temple_discovery
```

Required only for discovery:

```text
GOOGLE_PLACES_API_KEY=your-google-places-api-key
```

The scripts also support `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` if `DATABASE_URL` is not set.

## Database Setup

Create the database, then apply migrations:

```powershell
createdb shiva_temple_discovery
python scripts/init_db.py
```

Schema migration:

- `migrations/001_phase1_schema.sql`
- `migrations/002_add_google_maps_uri.sql`
- `migrations/003_candidate_discovery_events.sql`

## Import Locations

Sample CSV:

- `data/sample_locations.csv`

Import a CSV with flexible column mapping:

```powershell
python scripts/import_locations.py data/sample_locations.csv --source sample
```

If the CSV does not contain a location type column, force one:

```powershell
python scripts/import_locations.py districts.csv --location-type district --source lgd
```

Supported location types:

- `state`
- `district`
- `sub_district`
- `city`
- `town`
- `village`
- `urban_local_body`

Normalize official LGD/Census files into the project format before importing:

```powershell
python scripts/prepare_location_sources.py --state "Uttar Pradesh" --census-towns data/source/census_towns_2011.csv --output data/prepared_locations_uttar_pradesh.csv
python scripts/import_locations.py data/prepared_locations_uttar_pradesh.csv --source official_location_sources
```

For source guidance and append-safe examples, see `docs/LOCATION_SOURCES.md`.

For the district-only Phase 1.1 baseline plan, see
`docs/PHASE_1_1_DISTRICT_BASELINE.md`.

## Generate Search Tasks

Default task generation uses districts, towns, and urban local bodies only:

```powershell
python scripts/generate_search_tasks.py --limit 100
```

Generate Phase 1.1 district-only baseline tasks:

```powershell
python scripts/generate_search_tasks.py --district-only --dry-run
python scripts/generate_search_tasks.py --district-only
```

Preview without inserting:

```powershell
python scripts/generate_search_tasks.py --limit 20 --dry-run
```

Include cities:

```powershell
python scripts/generate_search_tasks.py --include-cities --limit 100
```

Include villages only when intentionally expanding scope:

```powershell
python scripts/generate_search_tasks.py --include-villages --limit 100
```

Phase 1 keywords:

- Shiva temple
- Shiv Mandir
- Mahadev temple
- Mahadev Mandir
- Shankar Mandir
- Someshwar temple
- Vishwanath temple
- Lingeshwar temple
- Rudreshwar temple

## Run Discovery

Discovery is bounded by `--limit`, which defaults to 10 tasks. The script refuses limits above 100 unless `--allow-large-limit` is provided.

```powershell
python scripts/run_discovery.py --limit 10
```

Google Places Text Search request settings:

- `includedType: hindu_temple`
- `strictTypeFiltering: true`
- `regionCode: IN`
- `languageCode: en`
- `pageSize: 20`
- field mask for only required fields

The client uses the API key from `GOOGLE_PLACES_API_KEY`.

Each newly discovered place observation is also written to
`candidate_discovery_events`. The `temple_candidates` table remains the deduped
latest candidate view, while `candidate_discovery_events` records which task,
query, keyword, and source location observed the Google Place ID.

Backfill the current candidate view into the event ledger as latest-known
attribution events:

```powershell
python scripts/backfill_discovery_events.py --district-only --dry-run
python scripts/backfill_discovery_events.py --district-only --all
```

## Classify Candidates

Classify names without touching the database:

```powershell
python scripts/classify_candidate.py "Kashi Vishwanath Temple" "Someshwar Mandir"
```

Reclassify stored candidates:

```powershell
python scripts/classify_candidate.py --update-db --limit 1000
```

High-confidence terms include `shiva`, `shiv`, `mahadev`, `vishwanath`, `kedarnath`, `omkareshwar`, `lingeshwar`, `linga`, and related configured terms. Medium-confidence terms include `shankar`, `ishwar`, `nath`, `rudra`, `someshwar`, `bholenath`, and related configured terms.

## Export Reports

```powershell
python scripts/report_counts.py
```

Export candidate rows for UI review:

```powershell
python scripts/report_counts.py --include-candidates --candidate-limit 5000
```

Export a strict Phase 1.1 district-only baseline report set:

```powershell
python scripts/report_counts.py `
  --district-only `
  --output-dir reports/phase_1_1_district_baseline `
  --include-candidates `
  --candidate-limit 100000
```

Generate the Phase 1.1 methodology/work report:

```powershell
python scripts/generate_phase1_1_work_report.py
```

Generate shareable Phase 1.1 social cards:

```powershell
python scripts/generate_phase1_1_social_cards.py
```

Freeze Phase 1.1 as a dated release by copying the final CSVs, PDFs, social
cards, and audit files into:

```text
reports/releases/phase_1_1_2026_05_17/
```

Generated files:

- `reports/national_summary.csv`
- `reports/state_counts.csv`
- `reports/district_counts.csv`
- `reports/candidate_review.csv` when `--include-candidates` is used

Sample report files are included:

- `reports/sample_national_summary.csv`
- `reports/sample_state_counts.csv`
- `reports/sample_district_counts.csv`
- `reports/sample_candidate_review.csv`

Reports include:

- total discovered candidates
- unique Google Place IDs
- high-confidence Shiva temples
- medium-confidence Shiva temple candidates
- low-confidence possible temples
- duplicates removed
- state-wise counts
- district-wise counts

These are discovery counts, not exact real-world counts and not an official temple census.

For scoped reports, candidate rows are still exported from the deduped latest
candidate view. Use `candidate_discovery_events` for multi-query and
multi-location attribution analysis.

## Analysis UI

A React dashboard is available for Phase 1 report analysis only. It is not the
final public website and it is not an admin panel.

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. The dashboard starts with sample report CSVs
on the Discovery Search page. Use the `Insights` button to open the analysis
dashboard, which can load generated files from `reports/`:

- `reports/national_summary.csv`
- `reports/state_counts.csv`
- `reports/district_counts.csv`
- `reports/candidate_review.csv`

Candidate rows include `google_maps_uri` when Google returns it, and the UI
shows it as an external Maps link. `google_place_id` remains the stable external
reference for deduplication.

## Tests

Run the core logic tests:

```powershell
python -m pytest
```

Covered areas:

- name normalization
- query generation
- Shiva confidence classification
- duplicate handling
- count reporting SQL

## Data Policy

Read `docs/DATA_POLICY.md` before publishing or interpreting any report output. Google Places is a discovery source, and final temple knowledge should be verified later from multiple sources.

For the command-by-command pipeline, read `docs/FUNCTIONAL_FLOW.md`.
