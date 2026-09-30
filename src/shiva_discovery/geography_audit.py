"""Offline geographic triage for Places discovery results.

Query attribution and an inferred locality anchor are review clues, never proof
of a temple's real-world district or state.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import asin, cos, radians, sin, sqrt
import re
from statistics import median

from .keywords import PHASE1_KEYWORDS
from .normalization import normalize_name
from .queries import build_search_query


STATE_ALIASES = {
    'राजस्थान': 'rajasthan', 'उत्तर प्रदेश': 'uttar pradesh',
    'मध्य प्रदेश': 'madhya pradesh', 'हरियाणा': 'haryana',
    'उत्तराखंड': 'uttarakhand', 'बिहार': 'bihar', 'दिल्ली': 'delhi',
}


def _mentions(text: str, name: str) -> bool:
    return bool(name and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.IGNORECASE))


def _coordinates(row):
    try:
        latitude, longitude = float(row['latitude']), float(row['longitude'])
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return latitude, longitude
    except (KeyError, TypeError, ValueError):
        pass
    return None


def _distance_km(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    half = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 12742 * asin(min(1, sqrt(half)))


def _location_key(location):
    return tuple(location.get(field, '') for field in
                 ('name', 'sub_district_name', 'district_name', 'state_name'))


def _address_state(address, known_states):
    for part in reversed(address.split(',')):
        without_postcode = re.sub(r'\s+\d{6}(?:\s+India)?$', '', part.strip(), flags=re.IGNORECASE).strip()
        if without_postcode.casefold() == 'india':
            continue
        candidate = STATE_ALIASES.get(without_postcode, normalize_name(without_postcode))
        if candidate in known_states:
            return candidate
        # Only the last address component (or the one before India) can be a state.
        break
    return None


def audit_geography(candidates, locations, known_states):
    candidates = list(candidates)
    query_locations = {}
    for location in locations:
        for keyword in PHASE1_KEYWORDS:
            query = build_search_query(keyword, location)
            if query in query_locations:
                raise ValueError('Location plan contains duplicate search queries.')
            query_locations[query] = location
    known_states = {normalize_name(name) for name in known_states}
    grouped = defaultdict(list)
    seen_ids = set()
    for row in candidates:
        place_id = row.get('google_place_id')
        if not place_id or place_id in seen_ids:
            raise ValueError('Candidate export has a blank or repeated Place ID.')
        seen_ids.add(place_id)
        location = query_locations.get(row.get('source_query'))
        if location is None:
            raise ValueError('A candidate query is absent from the selected location plan.')
        grouped[_location_key(location)].append((row, location))
    anchors = {}
    anchor_counts = {}
    for location_key, pairs in grouped.items():
        locality = location_key[0]
        matching = [_coordinates(row) for row, _ in pairs if _mentions(row.get('discovered_address', ''), locality)]
        matching = [point for point in matching if point is not None]
        anchor_counts[location_key] = len(matching)
        if len(matching) >= 3:
            anchors[location_key] = (median(point[0] for point in matching), median(point[1] for point in matching))
    records = []
    flags_total = Counter()
    priority_total = Counter()
    for row in candidates:
        location = query_locations[row['source_query']]
        locality = location['name']
        location_key = _location_key(location)
        address = row.get('discovered_address', '')
        point = _coordinates(row)
        state_hint = _address_state(address, known_states)
        expected_state = normalize_name(location['state_name'])
        flags = []
        if state_hint and state_hint != expected_state:
            flags.append('address_names_other_state')
        if normalize_name(row.get('state', '')) != expected_state or normalize_name(row.get('district', '')) != normalize_name(location.get('district_name', '')):
            flags.append('stored_query_attribution_differs_from_plan')
        if not point:
            flags.append('coordinates_missing_or_invalid')
        distance = _distance_km(anchors[location_key], point) if point and location_key in anchors else None
        if distance is not None and distance > 50:
            flags.append('over_50km_from_inferred_locality_anchor')
        elif distance is not None and distance > 25:
            flags.append('over_25km_from_inferred_locality_anchor')
        if not _mentions(address, locality):
            flags.append('address_does_not_name_query_locality')
        priority = ('high' if any(flag in flags for flag in
                    ('address_names_other_state', 'stored_query_attribution_differs_from_plan',
                     'over_50km_from_inferred_locality_anchor'))
                    else 'medium' if flags else 'routine')
        flags_total.update(flags)
        priority_total[priority] += 1
        records.append({
            'google_place_id': row['google_place_id'], 'discovered_name': row.get('discovered_name', ''),
            'google_maps_uri': row.get('google_maps_uri', ''), 'returned_address': address,
            'query_locality': locality, 'query_district': location.get('district_name', ''),
            'query_state': location['state_name'], 'address_state_hint': state_hint or '',
            'distance_from_inferred_locality_km': round(distance, 1) if distance is not None else '',
            'review_priority': priority, 'flags': '|'.join(flags),
        })
    records.sort(key=lambda row: (
        {'high': 0, 'medium': 1, 'routine': 2}[row['review_priority']],
        -float(row['distance_from_inferred_locality_km'] or 0),
        row['discovered_name'].casefold(), row['google_place_id'],
    ))
    return {
        'candidate_count': len(records), 'query_locality_anchors': {
            ', '.join(part for part in location_key if part): {'address_match_count': anchor_counts[location_key],
                       'inferred_latitude': point[0], 'inferred_longitude': point[1]}
            for location_key, point in sorted(anchors.items())},
        'priority_counts': dict(priority_total), 'flag_counts': dict(flags_total),
        'methodology': ('Locality anchors are medians of returned coordinates whose addresses name the query locality. '
                        'Distance thresholds and address state text are triage signals, not administrative boundaries or verified temple locations.'),
        'records': records,
    }
