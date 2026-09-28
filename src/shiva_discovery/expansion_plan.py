"""Offline location-to-query planning; no database or Google access."""
from __future__ import annotations
from collections import Counter
from .keywords import PHASE1_KEYWORDS
from .normalization import normalize_name
from .queries import build_search_query


def build_expansion_plan(rows, *, state=None, location_types=('town', 'urban_local_body'),
                         limit=50, max_pages=3, request_budget=0):
    if not 1 <= max_pages <= 3 or not 0 <= request_budget <= 30000 or (limit is not None and limit < 1):
        raise ValueError('Use 1–3 pages, a 0–30000 request assumption, and a positive location limit.')
    if not location_types or set(location_types) - {'town', 'urban_local_body', 'city'}:
        raise ValueError('Expansion planning supports towns, urban local bodies and explicitly selected cities.')
    unique = {}
    ambiguous = {}
    excluded = duplicates = 0
    for raw in rows:
        row = {key: str(value or '').strip() for key, value in raw.items()}
        if row.get('location_type') not in location_types or (state and row.get('state_name') != state):
            excluded += 1
            continue
        if not row.get('name') or not row.get('state_name'):
            raise ValueError('Eligible locations must include name and state_name.')
        # Match the current importer identity, and flag ambiguous parent data.
        key = tuple(normalize_name(row.get(key, '')) for key in ('location_type', 'name', 'state_name', 'district_name'))
        if key in unique:
            if unique[key].get('sub_district_name', '') != row.get('sub_district_name', ''):
                ambiguous.setdefault(key, [unique[key]]).append(row)
            elif key in ambiguous:
                ambiguous[key].append(row)
            else:
                duplicates += 1
        else:
            unique[key] = row
    ordered = sorted((row for key, row in unique.items() if key not in ambiguous),
                     key=lambda row: (not bool(row.get('district_name')), *(row.get(key, '') for key in ('state_name', 'district_name', 'location_type', 'name'))))
    selected = ordered if limit is None else ordered[:limit]
    tasks = [{'location_type': row['location_type'], 'name': row['name'],
              'state': row['state_name'], 'district': row.get('district_name', ''),
              'keyword': keyword, 'query': build_search_query(keyword, row)}
             for row in selected for keyword in PHASE1_KEYWORDS]
    upper = len(tasks) * max_pages
    return {
        'mode': 'offline-dry-run', 'google_requests_sent': 0, 'queue_modified': False,
        'eligible_unique_locations': len(ordered), 'selected_locations': len(selected),
        'unselected_locations': len(ordered) - len(selected), 'duplicate_rows_removed': duplicates,
        'withheld_ambiguous_groups': list(ambiguous.values()),
        'excluded_rows': excluded, 'selected_location_types': dict(Counter(row['location_type'] for row in selected)),
        'locations_without_district': sum(not row.get('district_name') for row in selected),
        'potential_tasks': len(tasks), 'max_pages_per_task': max_pages,
        'first_page_requests': len(tasks), 'maximum_page_requests': upper,
        'assumed_available_requests': request_budget,
        'whole_tasks_fitting_worst_case': min(len(tasks), request_budget // max_pages),
        'worst_case_months_at_assumed_allowance': ((upper + request_budget - 1) // request_budget) if request_budget else None,
        'notes': [
            'Request budget is a planning assumption, not verified billing-account allowance.',
            'Existing database tasks are not inspected; actual new task count may be lower.',
            'Retries/restarts consume extra requests beyond this no-retry estimate.',
            'Result occurrences and unique temple counts cannot be predicted from request counts.',
            'Source district attribution is not verified temple geography.',
        ],
        'tasks': tasks,
    }
