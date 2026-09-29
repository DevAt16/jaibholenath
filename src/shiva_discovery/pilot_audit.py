"""Compare a discovery export against a frozen baseline without changing either."""
from __future__ import annotations

from collections import Counter
from .classification import classify_candidate_name


def audit_candidates(baseline_rows, pilot_rows):
    baseline_ids = {row['google_place_id'] for row in baseline_rows}
    if not baseline_ids or '' in baseline_ids:
        raise ValueError('Baseline must contain nonempty Google Place IDs.')
    transitions = Counter()
    changed = []
    pilot_ids = set()
    overlap = 0
    for row in pilot_rows:
        place_id = row['google_place_id']
        if not place_id or place_id in pilot_ids:
            raise ValueError('Pilot export has a blank or repeated Google Place ID.')
        pilot_ids.add(place_id)
        overlap += place_id in baseline_ids
        old = row['confidence']
        if old not in {'high', 'medium', 'low'}:
            raise ValueError('Pilot export has an unknown confidence value.')
        classification = classify_candidate_name(row['discovered_name'])
        transitions[(old, classification.confidence)] += 1
        if old != classification.confidence:
            changed.append({
                'google_place_id': place_id,
                'name': row['discovered_name'],
                'previous_confidence': old,
                'revised_confidence': classification.confidence,
                'revised_reason': classification.classification_reason,
            })
    return {
        'baseline_unique_place_ids': len(baseline_ids),
        'pilot_unique_place_ids': len(pilot_ids),
        'pilot_already_in_baseline': overlap,
        'pilot_new_to_baseline': len(pilot_ids) - overlap,
        'confidence_transitions': [
            {'from': old, 'to': new, 'count': count}
            for (old, new), count in sorted(transitions.items())
        ],
        'changed_candidates': changed,
    }
