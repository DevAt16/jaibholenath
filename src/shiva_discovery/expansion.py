"""Bounded daily discovery and atomic, local analysis snapshots.

One database is one expansion campaign. The India calendar day is the retry
key; the existing request ledger still uses Google's Pacific billing month.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

from .discovery_runner import process_task
from .geography_audit import audit_geography
from .keywords import PHASE1_KEYWORDS
from .places_client import GooglePlacesClient
from .reporting import candidate_export_sql, cursor_rows_as_dicts
from .repositories import fetch_and_mark_pending_tasks
from .request_budget import BudgetBlocked, RequestBudget

MAX_CANDIDATES = 250_000
MAX_FILE_BYTES = 250 * 1024 * 1024
INDIA = ZoneInfo('Asia/Kolkata')
CANDIDATE_FIELDS = ('google_place_id', 'google_maps_uri', 'discovered_name',
    'discovered_address', 'latitude', 'longitude', 'state', 'district',
    'source_query', 'confidence', 'confidence_score', 'classification_reason',
    'first_seen_at', 'last_seen_at')


def read_csv(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Input CSV exceeds the size limit.')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('CSV headers are missing or duplicated.')
        rows = []
        for row in reader:
            if None in row or None in row.values():
                raise ValueError('Malformed CSV row.')
            rows.append(row)
            if len(rows) > MAX_CANDIDATES:
                raise ValueError('Input CSV exceeds the candidate limit.')
    return rows


def _date(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def normalize_candidate(row):
    result = {key: str(row.get(key) or '').strip() for key in CANDIDATE_FIELDS}
    if not result['google_place_id'] or not result['discovered_name']:
        raise ValueError('Candidates must have a Place ID and name.')
    if result['confidence'] not in ('high', 'medium', 'low'):
        raise ValueError('Invalid candidate confidence.')
    score = float(result['confidence_score'])
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('Invalid candidate confidence score.')
    result['confidence_score'] = score
    # Missing pins stay blank; they must not silently become (0, 0).
    for key, limit in [('latitude', 90), ('longitude', 180)]:
        value = row.get(key)
        if value is None or value == '':
            result[key] = ''
        else:
            number = float(value)
            if not math.isfinite(number) or abs(number) > limit:
                raise ValueError('Invalid candidate coordinates.')
            result[key] = number
    first, last = (_date(row.get(key)) for key in ('first_seen_at', 'last_seen_at'))
    if first and last and first > last:
        raise ValueError('Candidate observation dates are reversed.')
    result['first_seen_at'] = first.isoformat() if first else ''
    result['last_seen_at'] = last.isoformat() if last else ''
    result['state'] = result['state'] or 'Unknown'
    result['district'] = result['district'] or 'Unknown'
    return result


def merge_candidates(baseline, live):
    groups = []
    for rows in (baseline, live):
        group = {}
        for row in rows:
            candidate = normalize_candidate(row)
            place_id = candidate['google_place_id']
            if place_id in group:
                raise ValueError('A source contains duplicate Place IDs.')
            group[place_id] = candidate
        groups.append(group)
    old, recent = groups
    merged = dict(old)
    for place_id, candidate in recent.items():
        previous = merged.get(place_id)
        if previous:
            # The newest observation supplies fields. Equal timestamps prefer
            # the live record. Keep the earliest first and latest last dates.
            minimum = datetime.min.replace(tzinfo=timezone.utc)
            winner = candidate if (_date(candidate['last_seen_at']) or minimum) >= (
                _date(previous['last_seen_at']) or minimum) else previous
            candidate = dict(winner)
            for key, choose in [('first_seen_at', min), ('last_seen_at', max)]:
                dates = [value for row in (previous, recent[place_id]) if (value := _date(row[key]))]
                candidate[key] = choose(dates).isoformat() if dates else ''
        merged[place_id] = candidate
    if len(merged) > MAX_CANDIDATES:
        raise ValueError('Combined snapshot exceeds the candidate limit; increase it deliberately.')
    return sorted(merged.values(), key=lambda row: row['google_place_id']), {
        'baseline_candidates': len(old), 'database_candidates': len(recent),
        'overlapping_place_ids': len(old.keys() & recent.keys()),
        'added_since_baseline': len(recent.keys() - old.keys()),
        'combined_candidates': len(merged),
    }


def summarize(candidates, input_count):
    def counts(rows):
        confidence = Counter(row['confidence'] for row in rows)
        return dict(unique_google_place_ids=len(rows), high_confidence_shiva=confidence['high'],
            medium_confidence_shiva_candidates=confidence['medium'], low_confidence_possible_temples=confidence['low'])
    states, districts = defaultdict(list), defaultdict(list)
    for row in candidates:
        states[row['state']].append(row)
        districts[(row['state'], row['district'])].append(row)
    return {
        'national': dict(country='India', source='Google Places API; merged candidate snapshots',
            total_discovered_candidates=input_count, duplicates_removed=input_count - len(candidates),
            status='snapshot_input_rows_not_search_occurrences_or_verified_temple_totals', **counts(candidates)),
        'states': [dict(state=state, **counts(rows)) for state, rows in sorted(states.items())],
        'districts': [dict(state=state, district=district, **counts(rows))
                      for (state, district), rows in sorted(districts.items())],
        'candidates': candidates,
    }


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError('Unsupported value in snapshot.')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, default=_json_default, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).encode('utf-8')
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError('Snapshot exceeds the size limit.')
    fd, temporary = tempfile.mkstemp(prefix='.writing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def expansion_lock(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT CONCAT('shiva_expansion_', LEFT(SHA2(DATABASE(), 256), 40))")
        name = cursor.fetchone()[0]
        cursor.execute('SELECT GET_LOCK(%s, 0)', (name,))
        if cursor.fetchone()[0] != 1:
            raise BudgetBlocked('Another expansion batch is running.')
    try:
        yield
    finally:
        with conn.cursor() as cursor:
            cursor.execute('SELECT RELEASE_LOCK(%s)', (name,))


def run_daily_discovery(conn, account, *, state='Uttar Pradesh', location_type='urban_local_body',
                        limit=10, max_requests=30, max_pages=3, clock=None, client_factory=None):
    """Caller holds expansion_lock. Repeated or interrupted days never spend twice."""
    if not 1 <= limit <= 100 or not 1 <= max_pages <= 3 or not max_pages <= max_requests <= 300:
        raise ValueError('Use 1–100 tasks, 1–3 pages, and max-pages–300 requests.')
    clock = clock or (lambda: datetime.now(timezone.utc))
    day = clock().astimezone(INDIA).date()
    with conn.cursor() as cursor:
        cursor.execute('SELECT status, result_json FROM discovery_expansion_batches WHERE run_date=%s', (day,))
        previous = cursor.fetchone()
    if previous:
        return dict(status='already_ran' if previous[0] == 'completed' else 'needs_review',
                    run_date=str(day), previous_status=previous[0], requests=0)
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM discovery_expansion_batches WHERE status='running'")
        if cursor.fetchone()[0]:
            raise BudgetBlocked('An interrupted expansion batch needs review before discovery can resume.')
    budget = RequestBudget(conn, account, max_requests=max_requests, clock=clock)
    if budget.status()['run_remaining'] < 1:
        raise BudgetBlocked('Monthly request allowance exhausted.')
    factory = client_factory or GooglePlacesClient.from_env
    factory(before_request=budget.reserve)  # Validate credentials before a durable claim.
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO discovery_expansion_batches (run_date, budget_run_id, status) VALUES (%s,%s,'running')",
                       (day, budget.run_id))
    result = dict(status='completed', run_date=str(day), requests=0, completed=0, failed=0,
                  raw_results=0, tasks=[])
    try:
        for _ in range(limit):
            # Reserve enough headroom to finish a three-page query. Unused
            # room rolls into the next day; avoid repeatedly restarting pages.
            if budget.status()['run_remaining'] < max_pages:
                result['stop_reason'] = 'request_limit'
                break
            task = None
            # Cover locations with the broad term first, then work through
            # the configured variants after that queue is exhausted.
            for keyword in PHASE1_KEYWORDS:
                tasks = fetch_and_mark_pending_tasks(conn, limit=1, state=state,
                    location_type=location_type, keyword=keyword)
                if tasks:
                    task = tasks[0]
                    break
            if not task:
                result['stop_reason'] = 'queue_empty'
                break
            client = factory(before_request=lambda: budget.reserve(task['id']))
            outcome, raw, unique = process_task(conn, client, task, page_size=20, max_pages=max_pages)
            result['tasks'].append(dict(task_id=task['id'], outcome=outcome, results=raw, unique_in_task=unique))
            result['raw_results'] += raw
            if outcome == 'done':
                result['completed'] += 1
            else:
                result['status'] = 'failed' if outcome == 'failed' else 'paused'
                result['failed'] += outcome == 'failed'
                break  # Stop on the first failure; no automated failure retries.
    except BudgetBlocked:
        result['status'] = 'paused'
        result['stop_reason'] = 'budget_blocked'
    except Exception:
        result['status'] = 'failed'
        raise
    finally:
        result['requests'] = budget.requests
        with conn.cursor() as cursor:
            cursor.execute('UPDATE discovery_expansion_batches SET status=%s, finished_at=UTC_TIMESTAMP(6), result_json=%s WHERE run_date=%s',
                           (result['status'], json.dumps(result), day))
    return result


def export_snapshot(conn, baseline, output_dir, known_states):
    """Caller holds expansion_lock. Publish only a complete validated snapshot."""
    with conn.cursor() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    with conn.transaction(), conn.cursor() as cursor:
        cursor.execute(candidate_export_sql(), (MAX_CANDIDATES + 1,))
        live = cursor_rows_as_dicts(cursor)
        if len(live) > MAX_CANDIDATES:
            raise ValueError('Database export exceeds the candidate limit.')
        cursor.execute('SELECT name, sub_district_name, district_name, state_name, location_type FROM india_locations WHERE id IN (SELECT source_location_id FROM temple_candidates)')
        locations = cursor_rows_as_dicts(cursor)
    live = [normalize_candidate(row) for row in live]
    audit = audit_geography(live, locations, known_states) if live else {'candidate_count': 0, 'records': [], 'priority_counts': {}}
    merged, metrics = merge_candidates(baseline, live)
    reports = summarize(merged, len(baseline) + len(live))
    data = dict(schema_version=1, reports=reports, geography=audit)
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True, default=_json_default).encode('utf-8')
    snapshot_id = hashlib.sha256(encoded).hexdigest()
    output_dir = Path(output_dir)
    path = output_dir / 'snapshots' / f'{snapshot_id}.json'
    # Immutable content file first, then the tiny manifest. The UI fetches all
    # reports from this one file, so counts and rows cannot cross generations.
    if not path.exists():
        atomic_json(path, data)
    current = output_dir / 'latest.json'
    old = json.loads(current.read_text()) if current.exists() else None
    if old and old.get('snapshot_id') == snapshot_id:
        return old
    manifest = dict(schema_version=1, snapshot_id=snapshot_id,
        generated_at=datetime.now(timezone.utc).isoformat(), **metrics,
        geography_high_priority=audit['priority_counts'].get('high', 0))
    atomic_json(current, manifest)
    return manifest
