from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .normalization import normalize_header, normalize_name


STANDARD_LOCATION_FIELDNAMES = [
    "location_type",
    "name",
    "state_name",
    "district_name",
    "sub_district_name",
    "state_lgd_code",
    "district_lgd_code",
    "sub_district_lgd_code",
    "village_lgd_code",
    "source",
]

STATE_NAME_ALIASES = (
    "state_name",
    "state",
    "state_ut",
    "state_ut_name",
    "state_name_english",
    "statenameenglish",
    "state_name_in_english",
    "statename",
)

DISTRICT_NAME_ALIASES = (
    "district_name",
    "district",
    "district_name_english",
    "districtnameenglish",
    "district_name_in_english",
    "districtname",
)

SUB_DISTRICT_NAME_ALIASES = (
    "sub_district_name",
    "subdistrict_name",
    "subdistrict_name_english",
    "sub_district",
    "subdistrict",
    "sub_district_name_english",
    "subdistrictnameenglish",
    "tehsil_name",
    "taluka_name",
)

STATE_CODE_ALIASES = (
    "state_lgd_code",
    "state_code",
    "statecode",
    "lgd_state_code",
    "state_lgdcode",
)

DISTRICT_CODE_ALIASES = (
    "district_lgd_code",
    "district_code",
    "districtcode",
    "lgd_district_code",
    "district_lgdcode",
)

SUB_DISTRICT_CODE_ALIASES = (
    "sub_district_lgd_code",
    "subdistrict_lgd_code",
    "sub_district_code",
    "subdistrict_code",
    "subdistrictcode",
    "lgd_subdistrict_code",
    "tehsil_code",
    "taluka_code",
)

LOCAL_BODY_NAME_ALIASES = (
    "local_body_name_english",
    "localbodynameenglish",
    "local_body_name",
    "localbodyname",
    "ulb_name",
    "urban_local_body_name",
    "municipality_name",
    "name",
)

LOCAL_BODY_TYPE_ALIASES = (
    "local_body_type",
    "localbodytype",
    "local_body_type_name",
    "localbodytypename",
    "local_body_category",
    "localbodycategory",
    "category",
    "type",
)

ENTITY_CODE_ALIASES = (
    "entity_code",
    "entitycode",
)

ENTITY_NAME_ALIASES = (
    "entity_name",
    "entityname",
)

ENTITY_TYPE_ALIASES = (
    "entity_type",
    "entitytype",
)

TOWN_NAME_ALIASES = (
    "town_name",
    "town",
    "town_village",
    "town_or_village",
    "village_town",
    "village_town_name",
    "village_town_urban_rural",
    "area_name",
    "areaname",
    "name",
)

URBAN_RURAL_ALIASES = (
    "urban_rural",
    "urbanrural",
    "rural_urban",
    "urbrur",
    "area_type",
)

WARD_ALIASES = (
    "ward",
    "ward_name",
    "wardname",
    "ward_no",
)

URBAN_LOCAL_BODY_TERMS = (
    "urban",
    "municipal",
    "municipality",
    "municipal corporation",
    "municipal council",
    "nagar",
    "town panchayat",
    "notified area",
    "cantonment",
)

RURAL_LOCAL_BODY_TERMS = (
    "gram panchayat",
    "village panchayat",
    "district panchayat",
    "zila parishad",
    "zilla parishad",
    "janpad panchayat",
    "block panchayat",
    "intermediate panchayat",
    "rural",
)


@dataclass(frozen=True)
class SourceStats:
    read_rows: int = 0
    emitted_rows: int = 0
    skipped_rows: int = 0
    duplicate_rows: int = 0


def _normalized_mapping(row: Mapping[str, object]) -> dict[str, str]:
    return {
        normalize_header(key): ("" if value is None else str(value).strip())
        for key, value in row.items()
    }


def _first(row: Mapping[str, str], aliases: Sequence[str]) -> str:
    for alias in aliases:
        value = row.get(normalize_header(alias), "").strip()
        if value:
            return value
    return ""


def _clean_code(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        numeric = float(value)
    except ValueError:
        return value
    if numeric.is_integer():
        return str(int(numeric))
    return value


def _matches_state(state_name: str, state_filter: str | None) -> bool:
    if not state_filter:
        return True
    return normalize_name(state_name) == normalize_name(state_filter)


def _standard_row(
    *,
    location_type: str,
    name: str,
    state_name: str,
    district_name: str = "",
    sub_district_name: str = "",
    state_lgd_code: str = "",
    district_lgd_code: str = "",
    sub_district_lgd_code: str = "",
    village_lgd_code: str = "",
    source: str,
) -> dict[str, str]:
    return {
        "location_type": location_type,
        "name": name.strip(),
        "state_name": state_name.strip(),
        "district_name": district_name.strip(),
        "sub_district_name": sub_district_name.strip(),
        "state_lgd_code": _clean_code(state_lgd_code),
        "district_lgd_code": _clean_code(district_lgd_code),
        "sub_district_lgd_code": _clean_code(sub_district_lgd_code),
        "village_lgd_code": _clean_code(village_lgd_code),
        "source": source,
    }


def location_row_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("location_type", "")).strip(),
        normalize_name(row.get("name")),
        normalize_name(row.get("state_name")),
        normalize_name(row.get("district_name")),
        normalize_name(row.get("sub_district_name")),
    )


def dedupe_location_rows(rows: Iterable[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    seen: set[tuple[str, str, str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    duplicate_count = 0
    for row in rows:
        key = location_row_key(row)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        deduped.append(row)
    return deduped, duplicate_count


def read_source_rows(path: Path) -> list[dict[str, object]]:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key in ("records", "data", "result", "items"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ValueError(f"{path} does not contain a JSON list or records list.")
        return [dict(row) for row in payload if isinstance(row, Mapping)]

    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def normalize_lgd_district_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    state_filter: str | None = None,
) -> tuple[list[dict[str, str]], SourceStats]:
    output: list[dict[str, str]] = []
    read_rows = 0
    skipped_rows = 0
    for raw_row in rows:
        read_rows += 1
        row = _normalized_mapping(raw_row)
        state_name = _first(row, STATE_NAME_ALIASES)
        district_name = _first(row, DISTRICT_NAME_ALIASES)
        if not state_name or not district_name or not _matches_state(state_name, state_filter):
            skipped_rows += 1
            continue
        output.append(
            _standard_row(
                location_type="district",
                name=district_name,
                state_name=state_name,
                district_name=district_name,
                state_lgd_code=_first(row, STATE_CODE_ALIASES),
                district_lgd_code=_first(row, DISTRICT_CODE_ALIASES),
                source="lgd",
            )
        )

    deduped, duplicate_rows = dedupe_location_rows(output)
    return deduped, SourceStats(read_rows, len(deduped), skipped_rows, duplicate_rows)


def normalize_lgd_sub_district_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    state_filter: str | None = None,
) -> tuple[list[dict[str, str]], SourceStats]:
    output: list[dict[str, str]] = []
    read_rows = 0
    skipped_rows = 0
    for raw_row in rows:
        read_rows += 1
        row = _normalized_mapping(raw_row)
        state_name = _first(row, STATE_NAME_ALIASES)
        district_name = _first(row, DISTRICT_NAME_ALIASES)
        sub_district_name = _first(row, SUB_DISTRICT_NAME_ALIASES)
        if (
            not state_name
            or not district_name
            or not sub_district_name
            or not _matches_state(state_name, state_filter)
        ):
            skipped_rows += 1
            continue
        output.append(
            _standard_row(
                location_type="sub_district",
                name=sub_district_name,
                state_name=state_name,
                district_name=district_name,
                sub_district_name=sub_district_name,
                state_lgd_code=_first(row, STATE_CODE_ALIASES),
                district_lgd_code=_first(row, DISTRICT_CODE_ALIASES),
                sub_district_lgd_code=_first(row, SUB_DISTRICT_CODE_ALIASES),
                source="lgd",
            )
        )

    deduped, duplicate_rows = dedupe_location_rows(output)
    return deduped, SourceStats(read_rows, len(deduped), skipped_rows, duplicate_rows)


def build_sub_district_lookup(
    sub_district_rows: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    normalized_rows, _ = normalize_lgd_sub_district_rows(sub_district_rows)
    for row in normalized_rows:
        code = row.get("sub_district_lgd_code", "")
        if code:
            lookup[code] = row
    return lookup


def _is_urban_local_body(row: Mapping[str, str]) -> bool:
    local_body_type = normalize_name(_first(row, LOCAL_BODY_TYPE_ALIASES))
    if not local_body_type:
        return True
    if any(term in local_body_type for term in RURAL_LOCAL_BODY_TERMS):
        return False
    return any(term in local_body_type for term in URBAN_LOCAL_BODY_TERMS)


def normalize_lgd_local_body_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    state_filter: str | None = None,
    sub_district_lookup: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[list[dict[str, str]], SourceStats]:
    grouped: dict[str, dict[str, Any]] = {}
    read_rows = 0
    skipped_rows = 0
    for raw_row in rows:
        read_rows += 1
        row = _normalized_mapping(raw_row)
        state_name = _first(row, STATE_NAME_ALIASES)
        local_body_name = _first(row, LOCAL_BODY_NAME_ALIASES)
        if not state_name or not local_body_name or not _matches_state(state_name, state_filter):
            skipped_rows += 1
            continue
        if not _is_urban_local_body(row):
            skipped_rows += 1
            continue

        local_body_code = _first(row, ("local_body_code", "localbodycode", "ulb_code"))
        group_key = local_body_code or f"{state_name}|{local_body_name}"
        group = grouped.setdefault(
            group_key,
            {
                "state_name": state_name,
                "local_body_name": local_body_name,
                "state_lgd_code": _first(row, STATE_CODE_ALIASES),
                "district_lgd_code": "",
                "district_name": "",
                "sub_district_name": "",
                "sub_district_lgd_code": "",
            },
        )

        district_name = _first(row, DISTRICT_NAME_ALIASES)
        if district_name and not group["district_name"]:
            group["district_name"] = district_name
        district_code = _first(row, DISTRICT_CODE_ALIASES)
        if district_code and not group["district_lgd_code"]:
            group["district_lgd_code"] = district_code

        entity_type = normalize_name(_first(row, ENTITY_TYPE_ALIASES))
        entity_code = _clean_code(_first(row, ENTITY_CODE_ALIASES))
        entity_name = _first(row, ENTITY_NAME_ALIASES)
        if entity_type == "district" and not group["district_name"]:
            group["district_name"] = entity_name
            group["district_lgd_code"] = entity_code
        elif entity_type in {"subdistrict", "sub district", "subistrict"}:
            if not group["sub_district_name"]:
                group["sub_district_name"] = entity_name
            if not group["sub_district_lgd_code"]:
                group["sub_district_lgd_code"] = entity_code
            lookup_row = (sub_district_lookup or {}).get(entity_code)
            if lookup_row:
                if not group["district_name"]:
                    group["district_name"] = lookup_row.get("district_name", "")
                if not group["district_lgd_code"]:
                    group["district_lgd_code"] = lookup_row.get("district_lgd_code", "")
                if not group["sub_district_name"]:
                    group["sub_district_name"] = lookup_row.get("sub_district_name", "")

    output = [
        _standard_row(
            location_type="urban_local_body",
            name=str(group["local_body_name"]),
            state_name=str(group["state_name"]),
            district_name=str(group["district_name"]),
            sub_district_name=str(group["sub_district_name"]),
            state_lgd_code=str(group["state_lgd_code"]),
            district_lgd_code=str(group["district_lgd_code"]),
            sub_district_lgd_code=str(group["sub_district_lgd_code"]),
            source="lgd",
        )
        for group in grouped.values()
    ]

    deduped, duplicate_rows = dedupe_location_rows(output)
    skipped_rows += len(output) - len(deduped)
    return deduped, SourceStats(read_rows, len(deduped), skipped_rows, duplicate_rows)


def normalize_lgd_local_body_coverage_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    state_filter: str | None = None,
) -> tuple[list[dict[str, str]], SourceStats]:
    """Map LGD local body coverage rows directly when district columns exist.

    Most current LGD local body downloads are coverage files and may not include a
    direct district column. Use normalize_lgd_local_body_rows for deduped ULBs.
    This helper is intentionally not exported in the CLI.
    """
    output: list[dict[str, str]] = []
    read_rows = 0
    skipped_rows = 0
    for raw_row in rows:
        read_rows += 1
        row = _normalized_mapping(raw_row)
        state_name = _first(row, STATE_NAME_ALIASES)
        district_name = _first(row, DISTRICT_NAME_ALIASES)
        local_body_name = _first(row, LOCAL_BODY_NAME_ALIASES)
        if not state_name or not district_name or not local_body_name:
            skipped_rows += 1
            continue
        if not _matches_state(state_name, state_filter) or not _is_urban_local_body(row):
            skipped_rows += 1
            continue
        output.append(
            _standard_row(
                location_type="urban_local_body",
                name=local_body_name,
                state_name=state_name,
                district_name=district_name,
                state_lgd_code=_first(row, STATE_CODE_ALIASES),
                district_lgd_code=_first(row, DISTRICT_CODE_ALIASES),
                source="lgd",
            )
        )

    deduped, duplicate_rows = dedupe_location_rows(output)
    return deduped, SourceStats(read_rows, len(deduped), skipped_rows, duplicate_rows)


def _is_rural_census_row(row: Mapping[str, str]) -> bool:
    urban_rural = normalize_name(_first(row, URBAN_RURAL_ALIASES))
    return urban_rural in {"rural", "r", "village"}


def normalize_census_town_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    state_filter: str | None = None,
) -> tuple[list[dict[str, str]], SourceStats]:
    output: list[dict[str, str]] = []
    read_rows = 0
    skipped_rows = 0
    for raw_row in rows:
        read_rows += 1
        row = _normalized_mapping(raw_row)
        state_name = _first(row, STATE_NAME_ALIASES)
        district_name = _first(row, DISTRICT_NAME_ALIASES)
        sub_district_name = _first(row, SUB_DISTRICT_NAME_ALIASES)
        town_name = _first(row, TOWN_NAME_ALIASES)
        ward_name = _first(row, WARD_ALIASES)
        if ward_name and normalize_name(town_name) == normalize_name(ward_name):
            town_name = ""
        if (
            not state_name
            or not district_name
            or not town_name
            or not _matches_state(state_name, state_filter)
            or _is_rural_census_row(row)
        ):
            skipped_rows += 1
            continue
        output.append(
            _standard_row(
                location_type="town",
                name=town_name,
                state_name=state_name,
                district_name=district_name,
                sub_district_name=sub_district_name,
                state_lgd_code=_first(row, STATE_CODE_ALIASES),
                district_lgd_code=_first(row, DISTRICT_CODE_ALIASES),
                sub_district_lgd_code=_first(row, SUB_DISTRICT_CODE_ALIASES),
                source="census_2011",
            )
        )

    deduped, duplicate_rows = dedupe_location_rows(output)
    return deduped, SourceStats(read_rows, len(deduped), skipped_rows, duplicate_rows)


def write_standard_location_csv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_LOCATION_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in STANDARD_LOCATION_FIELDNAMES})


def append_unique_location_rows(path: Path, new_rows: Iterable[dict[str, str]]) -> int:
    existing_rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            existing_rows = list(csv.DictReader(handle))

    seen = {location_row_key(row) for row in existing_rows}
    appended: list[dict[str, str]] = []
    for row in new_rows:
        key = location_row_key(row)
        if key in seen:
            continue
        seen.add(key)
        appended.append(row)

    write_standard_location_csv(path, [*existing_rows, *appended])
    return len(appended)
