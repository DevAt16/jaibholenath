# Functional Flow

This document explains how the Phase 1 commands work together for Shiva Temple
Discovery. Phase 1 is a discovery pipeline, not a final temple census and not
the public website.

## High-Level Flow

```text
1. Configure environment
2. Apply database migrations
3. Import location records
4. Generate search tasks
5. Run limited Google Places discovery
6. Store deduplicated temple candidates
7. Classify Shiva confidence
8. Export CSV reports
9. Analyze reports and candidates in React UI
```

## Data Flow

```text
data/locations.csv
        |
        v
india_locations
        |
        v
temple_search_tasks
        |
        v
Google Places Text Search API
        |
        v
temple_candidates
        |
        v
reports/*.csv
        |
        v
React analysis UI
```

## 1. Environment Setup

The scripts read credentials from environment variables. A local `.env` file is
auto-loaded by the script bootstrap, but secrets should not be committed.

Required for database access:

```text
DATABASE_URL=postgresql://postgres:change-me@localhost:5432/shiva_temple_discovery
```

Required only for Google discovery:

```text
GOOGLE_PLACES_API_KEY=your-google-places-api-key
```

Alternative PostgreSQL variables are also supported:

```text
PGHOST
PGPORT
PGDATABASE
PGUSER
PGPASSWORD
```

## 2. Initialize the Database

Command:

```powershell
python scripts/init_db.py
```

What it does:

- Connects to PostgreSQL using `DATABASE_URL` or `PG*` variables.
- Creates `schema_migrations` if needed.
- Applies SQL files from `migrations/` in filename order.
- Skips migrations already recorded in `schema_migrations`.

Tables created:

- `india_locations`
- `location_aliases`
- `temple_search_tasks`
- `temple_candidates`

Current migrations:

- `001_phase1_schema.sql`
- `002_add_google_maps_uri.sql`

Run this whenever a new migration is added.

## 3. Import Locations

Command:

```powershell
python scripts/import_locations.py data/locations.csv --source manual_pilot
```

Optional parameters:

```powershell
--location-type district
--limit 100
--source lgd
```

What it reads:

- One or more CSV files.

What it writes:

- `india_locations`

What it does:

- Reads flexible CSV column names.
- Normalizes names into `normalized_name`.
- Infers or uses `location_type`.
- Stores hierarchy fields such as state, district, and sub-district.
- Upserts existing locations where possible.

Important columns:

```text
location_type
name
state_name
district_name
sub_district_name
state_lgd_code
district_lgd_code
sub_district_lgd_code
village_lgd_code
source
```

Recommended Phase 1 location types:

```text
state
district
town
urban_local_body
```

Villages are supported but should not be imported into discovery runs casually
because they can create very large task counts.

## 4. Generate Search Tasks

Preview command:

```powershell
python scripts/generate_search_tasks.py --limit 176 --dry-run
```

Insert command:

```powershell
python scripts/generate_search_tasks.py --limit 176
```

Optional parameters:

```powershell
--include-cities
--include-villages
--limit 100
--dry-run
```

What it reads:

- `india_locations`

What it writes:

- `temple_search_tasks`

Default behavior:

- Uses only these location types:

```text
district
town
urban_local_body
```

- Does not include villages unless `--include-villages` is provided.
- Does not include cities unless `--include-cities` is provided.
- Creates one task per location per Phase 1 keyword.

Phase 1 keywords:

```text
Shiva temple
Shiv Mandir
Mahadev temple
Mahadev Mandir
Shankar Mandir
Someshwar temple
Vishwanath temple
Lingeshwar temple
Rudreshwar temple
```

Example generated query:

```text
Shiva temple in Pune district, Maharashtra, India
```

Task statuses:

```text
pending
running
done
failed
skipped
```

Deduplication:

- A unique database index prevents duplicate tasks for the same
  `(location_id, keyword)` pair.

## 5. Run Google Places Discovery

Small pilot command:

```powershell
python scripts/run_discovery.py --limit 5 --page-size 20 --max-pages 1
```

Larger but still controlled command:

```powershell
python scripts/run_discovery.py --limit 25 --page-size 20 --max-pages 1
```

Optional parameters:

```powershell
--limit 10
--page-size 20
--max-pages 1
--allow-large-limit
```

Safety behavior:

- `--limit` defaults to `10`.
- Limits above `100` require `--allow-large-limit`.
- `--page-size` cannot exceed `20`.
- `--max-pages` cannot exceed `3`.

What it reads:

- Pending rows from `temple_search_tasks`.
- `GOOGLE_PLACES_API_KEY` from the environment.

What it calls:

```text
POST https://places.googleapis.com/v1/places:searchText
```

Google Places request settings:

```text
includedType: hindu_temple
strictTypeFiltering: true
regionCode: IN
languageCode: en
pageSize: 20
```

Requested field mask:

```text
places.id
places.displayName
places.formattedAddress
places.location
places.types
places.primaryType
places.googleMapsUri
nextPageToken
```

What it writes:

- `temple_candidates`
- Updates `temple_search_tasks`

Task update behavior:

- Marks selected tasks as `running`.
- Increments `attempts`.
- On success, marks task `done`.
- Stores raw `result_count` on the task.
- On error, marks task `failed` and stores `last_error`.

Candidate storage behavior:

- Uses `google_place_id` as the unique external reference.
- Inserts new candidates.
- Updates existing candidates if the same Place ID is rediscovered.
- Stores `google_maps_uri` when Google returns it.
- Updates `last_seen_at` on rediscovery.

Important: Google Places is a discovery source only. The output is not an
official temple census.

## 6. Candidate Classification

Classification normally happens automatically during discovery when a candidate
is inserted or updated.

Manual name check:

```powershell
python scripts/classify_candidate.py "Kashi Vishwanath Temple" "Someshwar Mandir"
```

Reclassify stored candidates:

```powershell
python scripts/classify_candidate.py --update-db --limit 1000
```

What it reads:

- Candidate names or `temple_candidates`

What it writes:

- `confidence`
- `confidence_score`
- `classification_reason`

Classification levels:

```text
high
medium
low
```

High-confidence examples:

```text
shiva
shiv
mahadev
vishwanath
somnath
kedarnath
lingeshwar
linga
lingam
```

Medium-confidence examples:

```text
shankar
ishwar
eshwar
nath
rudra
someshwar
bholenath
```

Low confidence is not a keyword list. It is the fallback when the discovered
name does not match configured high or medium Shiva terms.

## 7. Export Reports

Count reports:

```powershell
python scripts/report_counts.py --output-dir reports
```

Reports plus candidate review CSV:

```powershell
python scripts/report_counts.py --output-dir reports --include-candidates --candidate-limit 5000
```

What it reads:

- `temple_search_tasks`
- `temple_candidates`

What it writes:

```text
reports/national_summary.csv
reports/state_counts.csv
reports/district_counts.csv
reports/candidate_review.csv
```

`candidate_review.csv` is only written when `--include-candidates` is used.

National summary includes:

```text
total_discovered_candidates
unique_google_place_ids
high_confidence_shiva
medium_confidence_shiva_candidates
low_confidence_possible_temples
duplicates_removed
status
```

State and district reports include:

```text
unique_google_place_ids
high_confidence_shiva
medium_confidence_shiva_candidates
low_confidence_possible_temples
```

Candidate review includes:

```text
google_place_id
google_maps_uri
discovered_name
discovered_address
latitude
longitude
state
district
source_query
confidence
confidence_score
classification_reason
first_seen_at
last_seen_at
```

These reports are discovery counts, not exact real-world Shiva temple counts.

## 8. React Analysis UI

Start UI:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173/
```

What it reads:

- Bundled sample report CSVs by default.
- User-selected CSV files from `reports/`.

Recommended files to load:

```text
reports/national_summary.csv
reports/state_counts.csv
reports/district_counts.csv
reports/candidate_review.csv
```

What it does:

- Opens on the Discovery Search page by default.
- Searches currently loaded candidate report data in the browser.
- Provides an `Insights` button for the analysis dashboard.
- Shows national metrics.
- Shows high, medium, and low confidence breakdown.
- Shows state-wise and district-wise counts.
- Shows candidate review rows.
- Filters candidates by search text, confidence, state, and row count.
- Opens Google Maps links when `google_maps_uri` is present.

What it does not do:

- It does not connect directly to PostgreSQL.
- It does not call Google APIs.
- It does not update candidates.
- It is not the final public website.

## Recommended Pilot Run

For the current `data/locations.csv`:

```powershell
python scripts/init_db.py
python scripts/import_locations.py data/locations.csv --source manual_pilot
python scripts/generate_search_tasks.py --limit 176 --dry-run
python scripts/generate_search_tasks.py --limit 176
python scripts/run_discovery.py --limit 5 --page-size 20 --max-pages 1
python scripts/report_counts.py --output-dir reports --include-candidates --candidate-limit 5000
```

Then:

```powershell
cd frontend
npm run dev
```

Load the generated CSV files from `reports/`.

## Safe Scaling Guidance

Start with small discovery runs:

```powershell
python scripts/run_discovery.py --limit 5
python scripts/run_discovery.py --limit 25
python scripts/run_discovery.py --limit 100
```

Avoid these until you intentionally want wider coverage:

```powershell
--include-villages
--allow-large-limit
--max-pages 3
```

Google API quota and billing are controlled in Google Cloud Console. The local
script limits reduce accidental large runs, but they do not replace Google Cloud
quota or budget alerts.

## Troubleshooting

No pending tasks:

```text
No pending search tasks found.
```

Likely cause:

- Tasks were not generated.
- Existing tasks were already run.
- Pending tasks are already marked `done` or `failed`.

Google API key missing:

```text
GOOGLE_PLACES_API_KEY is not set.
```

Fix:

- Add `GOOGLE_PLACES_API_KEY` to `.env`.

Candidate Maps links missing:

- Existing candidates may have been discovered before `google_maps_uri` was
  added.
- Rediscovering the same Place ID can update the field when Google returns it.

Counts look small:

- Reports are discovery counts from completed searches.
- Run more pending tasks with a controlled `--limit`.

Counts should not be described as:

```text
exact real-world temple counts
official census counts
all Shiva temples in India
```
