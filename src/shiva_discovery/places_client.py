from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request
from typing import Any


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


class GooglePlacesError(RuntimeError):
    pass


@dataclass(frozen=True)
class GooglePlacesClient:
    api_key: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "GooglePlacesClient":
        api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if not api_key:
            raise GooglePlacesError("GOOGLE_PLACES_API_KEY is not set.")
        return cls(api_key=api_key)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GooglePlacesError(
                f"Google Places request failed with HTTP {exc.code}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise GooglePlacesError(f"Google Places request failed: {exc}") from exc

    def search_text(
        self,
        text_query: str,
        *,
        page_size: int = 20,
        max_pages: int = 1,
    ) -> list[dict[str, Any]]:
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

        places: list[dict[str, Any]] = []
        page_token: str | None = None
        for _ in range(max_pages):
            if page_token:
                payload["pageToken"] = page_token
            response = self._post(payload)
            places.extend(response.get("places", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return places


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
