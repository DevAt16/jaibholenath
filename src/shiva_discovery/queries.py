from __future__ import annotations

from collections.abc import Mapping

from .keywords import (
    DEFAULT_TASK_LOCATION_TYPES,
    OPTIONAL_CITY_TASK_TYPES,
    OPTIONAL_VILLAGE_TASK_TYPES,
)
from .normalization import normalize_name


def _value(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _unique_parts(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        clean = part.strip()
        if not clean:
            continue
        key = normalize_name(clean)
        if key and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique


def build_location_phrase(location: Mapping[str, object]) -> str:
    location_type = _value(location, "location_type")
    name = _value(location, "name")
    state_name = _value(location, "state_name")
    district_name = _value(location, "district_name")
    sub_district_name = _value(location, "sub_district_name")

    if location_type == "district":
        parts = [f"{name} district", state_name, "India"]
    elif location_type == "state":
        parts = [name, "India"]
    elif location_type == "sub_district":
        parts = [name, district_name, state_name, "India"]
    else:
        parts = [name, sub_district_name, district_name, state_name, "India"]

    return ", ".join(_unique_parts(parts))


def build_search_query(keyword: str, location: Mapping[str, object]) -> str:
    return f"{keyword.strip()} in {build_location_phrase(location)}"


def eligible_location_types(
    *,
    district_only: bool = False,
    include_cities: bool = False,
    include_villages: bool = False,
) -> tuple[str, ...]:
    if district_only:
        return ("district",)

    types = list(DEFAULT_TASK_LOCATION_TYPES)
    if include_cities:
        types.extend(OPTIONAL_CITY_TASK_TYPES)
    if include_villages:
        types.extend(OPTIONAL_VILLAGE_TASK_TYPES)
    return tuple(types)
