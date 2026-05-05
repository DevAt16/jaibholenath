from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .classification import classify_candidate_name
from .csv_import import LocationRecord
from .normalization import normalize_name


LOCATION_COLUMNS = (
    "name",
    "normalized_name",
    "location_type",
    "parent_id",
    "state_name",
    "district_name",
    "sub_district_name",
    "state_lgd_code",
    "district_lgd_code",
    "sub_district_lgd_code",
    "village_lgd_code",
    "source",
    "full_path",
    "search_priority",
    "is_active",
)


def _fetch_one_id(cursor, sql: str, params: tuple[object, ...]) -> int | None:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row[0]) if row else None


def find_parent_location_id(conn, record: LocationRecord) -> int | None:
    if record.parent_id:
        return record.parent_id

    with conn.cursor() as cursor:
        if record.location_type == "district":
            if record.state_lgd_code:
                return _fetch_one_id(
                    cursor,
                    """
                    SELECT id FROM india_locations
                    WHERE location_type = 'state' AND state_lgd_code = %s
                    ORDER BY id LIMIT 1;
                    """,
                    (record.state_lgd_code,),
                )
            if record.state_name:
                return _fetch_one_id(
                    cursor,
                    """
                    SELECT id FROM india_locations
                    WHERE location_type = 'state' AND normalized_name = %s
                    ORDER BY id LIMIT 1;
                    """,
                    (normalize_name(record.state_name),),
                )

        if record.location_type == "sub_district":
            if record.district_lgd_code:
                return _fetch_one_id(
                    cursor,
                    """
                    SELECT id FROM india_locations
                    WHERE location_type = 'district' AND district_lgd_code = %s
                    ORDER BY id LIMIT 1;
                    """,
                    (record.district_lgd_code,),
                )

        if record.location_type in {"city", "town", "urban_local_body", "village"}:
            if record.sub_district_lgd_code:
                parent_id = _fetch_one_id(
                    cursor,
                    """
                    SELECT id FROM india_locations
                    WHERE location_type = 'sub_district' AND sub_district_lgd_code = %s
                    ORDER BY id LIMIT 1;
                    """,
                    (record.sub_district_lgd_code,),
                )
                if parent_id:
                    return parent_id
            if record.district_lgd_code:
                return _fetch_one_id(
                    cursor,
                    """
                    SELECT id FROM india_locations
                    WHERE location_type = 'district' AND district_lgd_code = %s
                    ORDER BY id LIMIT 1;
                    """,
                    (record.district_lgd_code,),
                )

    return None


def find_existing_location_id(conn, record: LocationRecord) -> int | None:
    with conn.cursor() as cursor:
        code_lookup: tuple[str, str] | None = None
        if record.location_type == "state" and record.state_lgd_code:
            code_lookup = ("state_lgd_code", record.state_lgd_code)
        elif record.location_type == "district" and record.district_lgd_code:
            code_lookup = ("district_lgd_code", record.district_lgd_code)
        elif record.location_type == "sub_district" and record.sub_district_lgd_code:
            code_lookup = ("sub_district_lgd_code", record.sub_district_lgd_code)
        elif record.location_type == "village" and record.village_lgd_code:
            code_lookup = ("village_lgd_code", record.village_lgd_code)

        if code_lookup:
            column, value = code_lookup
            return _fetch_one_id(
                cursor,
                f"""
                SELECT id FROM india_locations
                WHERE location_type = %s AND {column} = %s
                ORDER BY id LIMIT 1;
                """,
                (record.location_type, value),
            )

        return _fetch_one_id(
            cursor,
            """
            SELECT id FROM india_locations
            WHERE location_type = %s
              AND normalized_name = %s
              AND COALESCE(state_name, '') = COALESCE(%s, '')
              AND COALESCE(district_name, '') = COALESCE(%s, '')
            ORDER BY id LIMIT 1;
            """,
            (
                record.location_type,
                record.normalized_name,
                record.state_name,
                record.district_name,
            ),
        )


def upsert_location(conn, record: LocationRecord) -> int:
    parent_id = find_parent_location_id(conn, record)
    values = {
        "name": record.name,
        "normalized_name": record.normalized_name,
        "location_type": record.location_type,
        "parent_id": parent_id,
        "state_name": record.state_name,
        "district_name": record.district_name,
        "sub_district_name": record.sub_district_name,
        "state_lgd_code": record.state_lgd_code,
        "district_lgd_code": record.district_lgd_code,
        "sub_district_lgd_code": record.sub_district_lgd_code,
        "village_lgd_code": record.village_lgd_code,
        "source": record.source,
        "full_path": record.full_path,
        "search_priority": record.search_priority,
        "is_active": record.is_active,
    }
    existing_id = find_existing_location_id(conn, record)

    with conn.cursor() as cursor:
        if existing_id:
            assignments = ", ".join(f"{column} = %s" for column in LOCATION_COLUMNS)
            cursor.execute(
                f"""
                UPDATE india_locations
                SET {assignments}, updated_at = NOW()
                WHERE id = %s
                RETURNING id;
                """,
                tuple(values[column] for column in LOCATION_COLUMNS) + (existing_id,),
            )
            return int(cursor.fetchone()[0])

        placeholders = ", ".join(["%s"] * len(LOCATION_COLUMNS))
        cursor.execute(
            f"""
            INSERT INTO india_locations ({", ".join(LOCATION_COLUMNS)})
            VALUES ({placeholders})
            RETURNING id;
            """,
            tuple(values[column] for column in LOCATION_COLUMNS),
        )
        return int(cursor.fetchone()[0])


def fetch_locations_for_tasks(
    conn,
    *,
    location_types: Iterable[str],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    types = tuple(location_types)
    placeholders = ", ".join(["%s"] * len(types))
    sql = f"""
        SELECT id, name, location_type, state_name, district_name, sub_district_name
        FROM india_locations
        WHERE is_active = TRUE AND location_type IN ({placeholders})
        ORDER BY search_priority, state_name, district_name, name, id
    """
    params: tuple[object, ...] = types
    if limit is not None:
        sql += " LIMIT %s"
        params = params + (limit,)

    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_search_task(
    conn,
    *,
    location_id: int,
    keyword: str,
    search_query: str,
    search_level: str,
) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO temple_search_tasks (location_id, keyword, search_query, search_level)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (location_id, keyword) DO NOTHING
            RETURNING id;
            """,
            (location_id, keyword, search_query, search_level),
        )
        return cursor.fetchone() is not None


def fetch_and_mark_pending_tasks(conn, *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH picked AS (
                SELECT id
                FROM temple_search_tasks
                WHERE status = 'pending'
                ORDER BY created_at, id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            ),
            updated AS (
                UPDATE temple_search_tasks AS task
                SET status = 'running',
                    attempts = task.attempts + 1,
                    updated_at = NOW()
                FROM picked
                WHERE task.id = picked.id
                RETURNING
                    task.id,
                    task.location_id,
                    task.keyword,
                    task.search_query,
                    task.search_level,
                    task.attempts
            )
            SELECT
                updated.*,
                loc.name AS location_name,
                loc.location_type,
                loc.state_name,
                loc.district_name
            FROM updated
            LEFT JOIN india_locations AS loc ON loc.id = updated.location_id
            ORDER BY updated.id;
            """,
            (limit,),
        )
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def complete_task(
    conn,
    *,
    task_id: int,
    status: str,
    result_count: int,
    last_error: str | None = None,
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE temple_search_tasks
            SET status = %s,
                result_count = %s,
                last_error = %s,
                updated_at = NOW()
            WHERE id = %s;
            """,
            (status, result_count, last_error, task_id),
        )


def upsert_candidate(conn, candidate: Mapping[str, Any]) -> int:
    classification = classify_candidate_name(str(candidate.get("discovered_name") or ""))
    params = {
        "google_place_id": candidate["google_place_id"],
        "discovered_name": candidate.get("discovered_name"),
        "discovered_address": candidate.get("discovered_address"),
        "latitude": candidate.get("latitude"),
        "longitude": candidate.get("longitude"),
        "state": candidate.get("state"),
        "district": candidate.get("district"),
        "source_query": candidate.get("source_query"),
        "source_location_id": candidate.get("source_location_id"),
        "confidence": classification.confidence,
        "confidence_score": classification.confidence_score,
        "classification_reason": classification.classification_reason,
    }

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO temple_candidates (
                google_place_id,
                discovered_name,
                discovered_address,
                latitude,
                longitude,
                state,
                district,
                source_query,
                source_location_id,
                confidence,
                confidence_score,
                classification_reason
            )
            VALUES (
                %(google_place_id)s,
                %(discovered_name)s,
                %(discovered_address)s,
                %(latitude)s,
                %(longitude)s,
                %(state)s,
                %(district)s,
                %(source_query)s,
                %(source_location_id)s,
                %(confidence)s,
                %(confidence_score)s,
                %(classification_reason)s
            )
            ON CONFLICT (google_place_id) DO UPDATE
            SET discovered_name = EXCLUDED.discovered_name,
                discovered_address = EXCLUDED.discovered_address,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                state = COALESCE(EXCLUDED.state, temple_candidates.state),
                district = COALESCE(EXCLUDED.district, temple_candidates.district),
                source_query = EXCLUDED.source_query,
                source_location_id = EXCLUDED.source_location_id,
                confidence = EXCLUDED.confidence,
                confidence_score = EXCLUDED.confidence_score,
                classification_reason = EXCLUDED.classification_reason,
                last_seen_at = NOW()
            RETURNING id;
            """,
            params,
        )
        return int(cursor.fetchone()[0])


def update_candidate_classification(conn, candidate_id: int, discovered_name: str) -> None:
    classification = classify_candidate_name(discovered_name)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE temple_candidates
            SET confidence = %s,
                confidence_score = %s,
                classification_reason = %s,
                last_seen_at = NOW()
            WHERE id = %s;
            """,
            (
                classification.confidence,
                classification.confidence_score,
                classification.classification_reason,
                candidate_id,
            ),
        )
