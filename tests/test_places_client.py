from shiva_discovery.places_client import place_to_candidate


def test_place_to_candidate_maps_google_maps_uri():
    candidate = place_to_candidate(
        {
            "id": "places/abc123",
            "googleMapsUri": "https://maps.google.com/?cid=abc123",
            "displayName": {"text": "Kashi Vishwanath Temple"},
            "formattedAddress": "Varanasi, Uttar Pradesh, India",
            "location": {"latitude": 25.3109, "longitude": 83.0107},
        },
        source_query="Shiva temple in Varanasi district, Uttar Pradesh, India",
        source_location_id=42,
        state="Uttar Pradesh",
        district="Varanasi",
    )

    assert candidate["google_place_id"] == "places/abc123"
    assert candidate["google_maps_uri"] == "https://maps.google.com/?cid=abc123"
    assert candidate["discovered_name"] == "Kashi Vishwanath Temple"
    assert candidate["latitude"] == 25.3109
    assert candidate["longitude"] == 83.0107
