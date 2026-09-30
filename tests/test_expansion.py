from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from shiva_discovery.expansion import atomic_json, merge_candidates, read_csv, summarize


def candidate(place_id='a', **values):
    return dict(google_place_id=place_id, discovered_name='Shiva temple', state='Uttar Pradesh',
        district='Agra', confidence='high', confidence_score='0.95', latitude=27.1, longitude=78.1,
        first_seen_at='2026-05-01 00:00:00', last_seen_at='2026-05-02T00:00:00+00:00', **values)


def test_merge_keeps_unique_ids_and_full_observation_window_without_mutating_inputs():
    baseline = [candidate()]
    live = [dict(candidate(), discovered_name='Mahadev temple', first_seen_at='2026-09-28T00:00:00Z',
                 last_seen_at='2026-09-29T05:30:00+05:30'), candidate('b')]
    rows, metrics = merge_candidates(baseline, live)
    assert len(rows) == 2
    assert rows[0]['discovered_name'] == 'Mahadev temple'
    assert rows[0]['first_seen_at'] == '2026-05-01T00:00:00+00:00'
    assert rows[0]['last_seen_at'] == '2026-09-29T00:00:00+00:00'
    assert baseline[0]['discovered_name'] == 'Shiva temple'
    assert metrics['added_since_baseline'] == metrics['overlapping_place_ids'] == 1
    reports = summarize(rows, 3)
    assert reports['national']['unique_google_place_ids'] == 2
    assert reports['national']['duplicates_removed'] == 1
    assert reports['states'][0]['unique_google_place_ids'] == 2


def test_older_database_copy_cannot_replace_newer_baseline_fields():
    rows, _ = merge_candidates([dict(candidate(), last_seen_at='2026-09-29T00:00:00Z')],
                               [dict(candidate(), discovered_name='Old name')])
    assert rows[0]['discovered_name'] == 'Shiva temple'


@pytest.mark.parametrize('changes', [dict(google_place_id=''), dict(confidence_score='nan'),
    dict(latitude='inf'), dict(confidence='verified'), dict(last_seen_at='2025-01-01'),
    dict(first_seen_at='not-a-date')])
def test_invalid_source_is_rejected(changes):
    with pytest.raises(ValueError):
        merge_candidates([dict(candidate(), **changes)], [])


def test_duplicate_within_source_is_rejected_not_silently_merged():
    with pytest.raises(ValueError, match='duplicate'):
        merge_candidates([candidate(), candidate()], [])


def test_zero_coordinates_are_preserved_and_missing_are_not_invented():
    rows, _ = merge_candidates([dict(candidate(), latitude=0, longitude=0),
                               dict(candidate('b'), latitude=None, longitude=None)], [])
    assert rows[0]['latitude'] == rows[0]['longitude'] == 0
    assert rows[1]['latitude'] == rows[1]['longitude'] == ''


def test_atomic_write_failure_keeps_previous_manifest(tmp_path):
    path = tmp_path / 'latest.json'
    atomic_json(path, {'snapshot_id': 'old'})
    with patch('shiva_discovery.expansion.os.replace', side_effect=OSError('disk failed')):
        with pytest.raises(OSError):
            atomic_json(path, {'snapshot_id': 'new'})
    assert json.loads(path.read_text()) == {'snapshot_id': 'old'}
    assert list(tmp_path.iterdir()) == [path]


def test_malformed_csv_is_rejected(tmp_path):
    path = tmp_path / 'source.csv'
    path.write_text('id,name\na,Temple,unexpected\n')
    with pytest.raises(ValueError):
        read_csv(path)
