from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator

from .request_budget import BudgetBlocked


TEXT_SEARCH_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.types",
        "places.primaryType",
        "places.googleMapsUri",
        "nextPageToken",
    ]
)
# Deliberately independent of FIELD_MASK: future field changes must be reviewed
# against the budgeted SKU, rather than silently upgrading billing categories.
PRO_FIELDS = frozenset({'places.id', 'places.displayName', 'places.formattedAddress',
                       'places.location', 'places.types', 'places.primaryType',
                       'places.googleMapsUri', 'nextPageToken'})


class GooglePlacesError(RuntimeError):
    pass


@dataclass(frozen=True)
class GooglePlacesClient:
    api_key: str
    timeout_seconds: int = 30
    before_request: Callable[[], None] | None = None

    @classmethod
    def from_env(cls, *, before_request=None) -> "GooglePlacesClient":
        api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if not api_key:
            raise GooglePlacesError("GOOGLE_PLACES_API_KEY is not set.")
        return cls(api_key=api_key, before_request=before_request)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.before_request is None:
            raise BudgetBlocked('Google requests require a persistent request-budget guard.')
        if frozenset(FIELD_MASK.split(',')) != PRO_FIELDS:
            raise BudgetBlocked('Field mask changed; review its billing SKU before running discovery.')
        request = urllib.request.Request(
            TEXT_SEARCH_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            method="POST",
        )
        # Reserve and commit before every HTTP attempt, including pagination.
        # Network failures and uncertain outcomes never refund a reservation.
        self.before_request()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise GooglePlacesError(
                f"Google Places request failed with HTTP {exc.code}."
            ) from exc
        except urllib.error.URLError as exc:
            raise GooglePlacesError(f"Google Places request failed: {exc}") from exc

    def iter_text_pages(
        self,
        text_query: str,
        *,
        page_size: int = 20,
        max_pages: int = 1,
    ) -> Iterator[list[dict[str, Any]]]:
        if not text_query.strip():
            raise ValueError("text_query is required.")
        if page_size < 1 or page_size > 20:
            raise ValueError("page_size must be between 1 and 20.")
        if max_pages < 1 or max_pages > 3:
            raise ValueError("max_pages must be between 1 and 3.")

        payload: dict[str, Any] = {
            "textQuery": text_query,
            "includedType": "hindu_temple",
            "strictTypeFiltering": True,
            "regionCode": "IN",
            "languageCode": "en",
            "pageSize": page_size,
        }

        page_token: str | None = None
        for _ in range(max_pages):
            if page_token:
                payload["pageToken"] = page_token
            response = self._post(payload)
            yield response.get("places", [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def search_text(self, text_query: str, *, page_size: int = 20,
                    max_pages: int = 1) -> list[dict[str, Any]]:
        return [place for page in self.iter_text_pages(text_query, page_size=page_size,
                                                      max_pages=max_pages) for place in page]


def place_to_candidate(
    place: dict[str, Any],
    *,
    source_query: str,
    source_location_id: int,
    state: str | None,
    district: str | None,
) -> dict[str, Any]:
    display_name = place.get("displayName") or {}
    location = place.get("location") or {}
    return {
        "google_place_id": place.get("id"),
        "google_maps_uri": place.get("googleMapsUri"),
        "discovered_name": display_name.get("text") or "",
        "discovered_address": place.get("formattedAddress"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "state": state,
        "district": district,
        "source_query": source_query,
        "source_location_id": source_location_id,
    }
