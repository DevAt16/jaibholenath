from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Iterable

from .keywords import SEARCH_PRIORITY_BY_TYPE
from .normalization import normalize_header, normalize_name


LOCATION_TYPES = {
    "state",
    "district",
    "sub_district",
    "city",
    "town",
    "village",
    "urban_local_body",
}

LOCATION_TYPE_ALIASES = {
    "state": "state",
    "states": "state",
    "district": "district",
    "districts": "district",
    "subdistrict": "sub_district",
    "sub district": "sub_district",
    "sub_district": "sub_district",
    "tehsil": "sub_district",
    "taluka": "sub_district",
    "city": "city",
    "cities": "city",
    "town": "town",
    "towns": "town",
    "village": "village",
    "villages": "village",
    "ulb": "urban_local_body",
    "urban local body": "urban_local_body",
    "urban_local_body": "urban_local_body",
    "municipality": "urban_local_body",
    "municipal corporation": "urban_local_body",
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "location_name", "place_name"),
    "location_type": ("location_type", "type", "place_type", "category"),
    "parent_id": ("parent_id", "parent_location_id"),
    "state_name": ("state_name", "state", "state_ut", "state_ut_name", "statename"),
    "district_name": ("district_name", "district", "districtname"),
    "sub_district_name": (
        "sub_district_name",
        "subdistrict_name",
        "sub_district",
        "subdistrict",
        "tehsil_name",
        "taluka_name",
        "block_name",
    ),
    "state_lgd_code": (
        "state_lgd_code",
        "state_code",
        "lgd_state_code",
        "statecode",
    ),
    "district_lgd_code": (
        "district_lgd_code",
        "district_code",
        "lgd_district_code",
        "districtcode",
    ),
    "sub_district_lgd_code": (
        "sub_district_lgd_code",
        "subdistrict_lgd_code",
        "sub_district_code",
        "subdistrict_code",
        "tehsil_code",
        "taluka_code",
    ),
    "village_lgd_code": (
        "village_lgd_code",
        "village_code",
        "lgd_village_code",
        "villagecode",
    ),
    "source": ("source", "data_source"),
    "full_path": ("full_path", "path"),
    "search_priority": ("search_priority", "priority"),
    "is_active": ("is_active", "active"),
}

TYPE_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "state": ("state_name", "state", "state_ut_name", "name"),
    "district": ("district_name", "district", "name"),
    "sub_district": (
        "sub_district_name",
        "subdistrict_name",
        "tehsil_name",
        "taluka_name",
        "name",
    ),
    "city": ("city_name", "city", "town_city", "name"),
    "town": ("town_name", "town", "town_city", "name"),
    "village": ("village_name", "village", "name"),
    "urban_local_body": ("ulb_name", "urban_local_body_name", "municipality_name", "name"),
}

INFER_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    location_type: tuple(alias for alias in aliases if alias != "name")
    for location_type, aliases in TYPE_NAME_ALIASES.items()
}


@dataclass(frozen=True)
class LocationRecord:
    name: str
    normalized_name: str
    location_type: str
    parent_id: int | None
    state_name: str | None
    district_name: str | None
    sub_district_name: str | None
    state_lgd_code: str | None
    district_lgd_code: str | None
    sub_district_lgd_code: str | None
    village_lgd_code: str | None
    source: str
    full_path: str
    search_priority: int
    is_active: bool


def _normalized_row(raw_row: dict[str, str]) -> dict[str, str]:
    return {
        normalize_header(key): (value.strip() if isinstance(value, str) else "")
        for key, value in raw_row.items()
    }


def _first(row: dict[str, str], aliases: Iterable[str]) -> str:
    for alias in aliases:
        value = row.get(normalize_header(alias), "").strip()
        if value:
            return value
    return ""


def _field(row: dict[str, str], name: str) -> str:
    return _first(row, FIELD_ALIASES[name])


def canonical_location_type(value: str | None) -> str:
    normalized = normalize_name(value).replace("_", " ")
    canonical = LOCATION_TYPE_ALIASES.get(normalized)
    if canonical:
        return canonical
    normalized_with_underscore = normalized.replace(" ", "_")
    if normalized_with_underscore in LOCATION_TYPES:
        return normalized_with_underscore
    raise ValueError(f"Unsupported location type: {value!r}")


def infer_location_type(row: dict[str, str], forced_location_type: str | None = None) -> str:
    if forced_location_type:
        return canonical_location_type(forced_location_type)

    raw_type = _field(row, "location_type")
    if raw_type:
        return canonical_location_type(raw_type)

    for location_type in (
        "village",
        "urban_local_body",
        "city",
        "town",
        "sub_district",
        "district",
        "state",
    ):
        if _first(row, INFER_TYPE_ALIASES[location_type]):
            return location_type

    raise ValueError("Could not infer location_type. Pass --location-type for this CSV.")


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_bool(value: str, default: bool = True) -> bool:
    if not value:
        return default
    return normalize_name(value) not in {"0", "false", "no", "n", "inactive"}


def _join_unique(parts: Iterable[str | None]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for part in parts:
        if not part:
            continue
        key = normalize_name(part)
        if key and key not in seen:
            seen.add(key)
            output.append(part)
    return " > ".join(output)


def map_csv_row(
    raw_row: dict[str, str],
    *,
    source: str = "csv",
    forced_location_type: str | None = None,
) -> LocationRecord:
    row = _normalized_row(raw_row)
    location_type = infer_location_type(row, forced_location_type)
    name = _first(row, TYPE_NAME_ALIASES[location_type]) or _field(row, "name")
    if not name:
        raise ValueError("Location row is missing a name.")

    state_name = _field(row, "state_name") or None
    district_name = _field(row, "district_name") or None
    sub_district_name = _field(row, "sub_district_name") or None

    if location_type == "state" and not state_name:
        state_name = name
    if location_type == "district" and not district_name:
        district_name = name
    if location_type == "sub_district" and not sub_district_name:
        sub_district_name = name

    explicit_source = _field(row, "source")
    full_path = _field(row, "full_path") or _join_unique(
        [state_name, district_name, sub_district_name, name]
    )
    search_priority = _parse_int(_field(row, "search_priority"))

    return LocationRecord(
        name=name,
        normalized_name=normalize_name(name),
        location_type=location_type,
        parent_id=_parse_int(_field(row, "parent_id")),
        state_name=state_name,
        district_name=district_name,
        sub_district_name=sub_district_name,
        state_lgd_code=_field(row, "state_lgd_code") or None,
        district_lgd_code=_field(row, "district_lgd_code") or None,
        sub_district_lgd_code=_field(row, "sub_district_lgd_code") or None,
        village_lgd_code=_field(row, "village_lgd_code") or None,
        source=explicit_source or source,
        full_path=full_path,
        search_priority=search_priority
        if search_priority is not None
        else SEARCH_PRIORITY_BY_TYPE.get(location_type, 100),
        is_active=_parse_bool(_field(row, "is_active"), default=True),
    )


def read_location_csv(
    path: Path,
    *,
    source: str = "csv",
    forced_location_type: str | None = None,
    limit: int | None = None,
) -> list[LocationRecord]:
    records: list[LocationRecord] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            if limit is not None and len(records) >= limit:
                break
            try:
                records.append(
                    map_csv_row(
                        row,
                        source=source,
                        forced_location_type=forced_location_type,
                    )
                )
            except ValueError as exc:
                raise ValueError(f"{path}:{index}: {exc}") from exc
    return records
