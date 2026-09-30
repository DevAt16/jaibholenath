from shiva_discovery.places_client import place_to_candidate
import io
import json
import urllib.error
import pytest
from shiva_discovery import places_client
from shiva_discovery.places_client import GooglePlacesClient, GooglePlacesError
from shiva_discovery.request_budget import BudgetBlocked


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


def test_every_page_reserves_before_network_and_preserves_query(monkeypatch):
    events = []
    requests = []
    def send(request, **kwargs):
        events.append('http')
        requests.append(json.loads(request.data))
        page = {'places': [{'id': str(len(requests))}]}
        if len(requests) == 1:
            page['nextPageToken'] = 'next'
        return io.BytesIO(json.dumps(page).encode())
    monkeypatch.setattr(places_client.urllib.request, 'urlopen', send)
    client = GooglePlacesClient('test-only', before_request=lambda: events.append('reserve'))
    assert len(client.search_text('Shiv Mandir in Agra', max_pages=3)) == 2
    assert events == ['reserve', 'http', 'reserve', 'http']
    assert requests[1].pop('pageToken') == 'next'
    assert requests[0] == requests[1]


def test_missing_guard_changed_sku_and_exhausted_allowance_never_send(monkeypatch):
    monkeypatch.setattr(places_client.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('Must not send'))
    with pytest.raises(BudgetBlocked):
        GooglePlacesClient('test').search_text('Shiva')
    def exhausted():
        raise BudgetBlocked('Exhausted')
    with pytest.raises(BudgetBlocked):
        GooglePlacesClient('test', before_request=exhausted).search_text('Shiva')
    monkeypatch.setattr(places_client, 'FIELD_MASK', places_client.FIELD_MASK + ',places.rating')
    with pytest.raises(BudgetBlocked):
        GooglePlacesClient('test', before_request=lambda: pytest.fail('Unexpected SKU')).search_text('Shiva')


def test_failed_http_attempt_keeps_reservation_and_hides_response_body(monkeypatch):
    reservations = []
    def send(*args, **kwargs):
        raise urllib.error.HTTPError('https://example.test', 429, 'Limited', {}, io.BytesIO(b'sensitive response'))
    monkeypatch.setattr(places_client.urllib.request, 'urlopen', send)
    with pytest.raises(GooglePlacesError, match='429') as failure:
        GooglePlacesClient('test', before_request=lambda: reservations.append(1)).search_text('Shiva')
    assert reservations == [1]
    assert 'sensitive' not in str(failure.value)
