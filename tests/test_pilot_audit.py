import pytest
from shiva_discovery.pilot_audit import audit_candidates


def test_audit_compares_place_ids_and_reclassifies_without_mutating_inputs():
    baseline = [{'google_place_id': 'A'}, {'google_place_id': 'B'}]
    pilot = [
        {'google_place_id': 'A', 'discovered_name': 'शिव मंदिर', 'confidence': 'low'},
        {'google_place_id': 'C', 'discovered_name': 'Shiva house', 'confidence': 'high'},
    ]
    result = audit_candidates(baseline, pilot)
    assert result['pilot_already_in_baseline'] == 1
    assert result['pilot_new_to_baseline'] == 1
    assert [(item['previous_confidence'], item['revised_confidence']) for item in result['changed_candidates']] == [
        ('low', 'high'), ('high', 'low')]
    assert pilot[0]['confidence'] == 'low'


def test_audit_rejects_duplicate_pilot_ids():
    with pytest.raises(ValueError, match='repeated'):
        audit_candidates([{'google_place_id': 'A'}], [
            {'google_place_id': 'B', 'discovered_name': 'Shiv', 'confidence': 'high'},
            {'google_place_id': 'B', 'discovered_name': 'Shiv', 'confidence': 'high'},
        ])
