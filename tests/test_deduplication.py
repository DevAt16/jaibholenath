from shiva_discovery.dedupe import deduplicate_places


def test_deduplicate_places_keeps_first_place_id_and_counts_duplicates():
    result = deduplicate_places(
        [
            {"id": "place-1", "displayName": {"text": "First"}},
            {"id": "place-1", "displayName": {"text": "Duplicate"}},
            {"displayName": {"text": "Missing ID"}},
            {"id": "place-2", "displayName": {"text": "Second"}},
        ]
    )

    assert [place["id"] for place in result.unique_places] == ["place-1", "place-2"]
    assert result.duplicate_count == 2
