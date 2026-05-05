from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DedupeResult:
    unique_places: list[dict[str, Any]]
    duplicate_count: int


def deduplicate_places(places: Iterable[Mapping[str, Any]]) -> DedupeResult:
    """Keep the first occurrence of each Google Place ID."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    duplicate_count = 0

    for place in places:
        place_id = str(place.get("id") or "").strip()
        if not place_id:
            duplicate_count += 1
            continue
        if place_id in seen:
            duplicate_count += 1
            continue
        seen.add(place_id)
        unique.append(dict(place))

    return DedupeResult(unique_places=unique, duplicate_count=duplicate_count)
