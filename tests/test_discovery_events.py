import pytest

from shiva_discovery.repositories import build_candidate_discovery_event


def test_build_candidate_discovery_event_preserves_query_attribution():
    task = {
        "id": 101,
        "location_id": 42,
        "location_type": "district",
        "location_name": "Bajali",
        "state_name": "Assam",
        "district_name": "Bajali",
        "keyword": "Shiva temple",
        "search_query": "Shiva temple in Bajali, Assam, India",
        "search_level": "district",
    }
    candidate = {
        "google_place_id": "places/abc",
        "google_maps_uri": "https://maps.google.com/?cid=abc",
        "discovered_name": "Mahadev Mandir",
        "discovered_address": "Bajali, Assam",
        "latitude": 26.5,
        "longitude": 91.0,
        "state": "Assam",
        "district": "Bajali",
        "source_query": "Shiva temple in Bajali, Assam, India",
        "source_location_id": 42,
    }

    event = build_candidate_discovery_event(
        candidate_id=7,
        candidate=candidate,
        task=task,
        result_position=3,
    )

    assert event == {
        "candidate_id": 7,
        "google_place_id": "places/abc",
        "search_task_id": 101,
        "source_location_id": 42,
        "source_location_type": "district",
        "source_location_name": "Bajali",
        "state_name": "Assam",
        "district_name": "Bajali",
        "keyword": "Shiva temple",
        "search_query": "Shiva temple in Bajali, Assam, India",
        "search_level": "district",
        "result_position": 3,
        "discovered_name": "Mahadev Mandir",
        "discovered_address": "Bajali, Assam",
        "latitude": 26.5,
        "longitude": 91.0,
        "google_maps_uri": "https://maps.google.com/?cid=abc",
    }


def test_build_candidate_discovery_event_requires_place_id():
    with pytest.raises(ValueError, match="google_place_id"):
        build_candidate_discovery_event(
            candidate_id=1,
            candidate={"google_place_id": ""},
            task={"id": 10, "search_query": "Shiva temple in Pune, Maharashtra, India"},
            result_position=1,
        )


def test_build_candidate_discovery_event_requires_positive_position():
    with pytest.raises(ValueError, match="result_position"):
        build_candidate_discovery_event(
            candidate_id=1,
            candidate={"google_place_id": "places/abc"},
            task={"id": 10, "search_query": "Shiva temple in Pune, Maharashtra, India"},
            result_position=0,
        )
