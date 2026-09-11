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
                WHERE id = %s;
                """,
                tuple(values[column] for column in LOCATION_COLUMNS) + (existing_id,),
            )
            return existing_id

        placeholders = ", ".join(["%s"] * len(LOCATION_COLUMNS))
        cursor.execute(
            f"""
            INSERT INTO india_locations ({", ".join(LOCATION_COLUMNS)})
            VALUES ({placeholders});
            """,
            tuple(values[column] for column in LOCATION_COLUMNS),
        )
        return int(cursor.lastrowid)


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
            ON DUPLICATE KEY UPDATE id = id;
            """,
            (location_id, keyword, search_query, search_level),
        )
        return cursor.rowcount == 1


def fetch_and_mark_pending_tasks(conn, *, limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be positive")
    # The lock and update must remain in the same transaction across workers.
    with conn.transaction():
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM temple_search_tasks
                WHERE status = 'pending' ORDER BY created_at, id
                LIMIT %s FOR UPDATE SKIP LOCKED
            """, (limit,))
            ids = tuple(row[0] for row in cursor.fetchall())
            if not ids:
                return []
            placeholders = ", ".join(["%s"] * len(ids))
            cursor.execute(f"""
                UPDATE temple_search_tasks SET status = 'running',
                attempts = attempts + 1, updated_at = NOW()
                WHERE id IN ({placeholders})
            """, ids)
            cursor.execute(f"""
                SELECT task.id, task.location_id, task.keyword, task.search_query,
                       task.search_level, task.attempts, loc.name AS location_name,
                       loc.location_type, loc.state_name, loc.district_name
                FROM temple_search_tasks AS task
                LEFT JOIN india_locations AS loc ON loc.id = task.location_id
                WHERE task.id IN ({placeholders}) ORDER BY task.id
            """, ids)
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


def build_candidate_discovery_event(
    *,
    candidate_id: int,
    candidate: Mapping[str, Any],
    task: Mapping[str, Any],
    result_position: int | None,
) -> dict[str, Any]:
    google_place_id = str(candidate.get("google_place_id") or "").strip()
    if not google_place_id:
        raise ValueError("candidate google_place_id is required for discovery events.")
    if result_position is not None and result_position < 1:
        raise ValueError("result_position must be at least 1 when provided.")

    return {
        "candidate_id": candidate_id,
        "google_place_id": google_place_id,
        "search_task_id": task.get("id"),
        "source_location_id": candidate.get("source_location_id") or task.get("location_id"),
        "source_location_type": task.get("location_type"),
        "source_location_name": task.get("location_name"),
        "state_name": candidate.get("state") or task.get("state_name"),
        "district_name": candidate.get("district") or task.get("district_name"),
        "keyword": task.get("keyword"),
        "search_query": candidate.get("source_query") or task.get("search_query"),
        "search_level": task.get("search_level"),
        "result_position": result_position,
        "discovered_name": candidate.get("discovered_name") or "",
        "discovered_address": candidate.get("discovered_address"),
        "latitude": candidate.get("latitude"),
        "longitude": candidate.get("longitude"),
        "google_maps_uri": candidate.get("google_maps_uri"),
    }


def record_candidate_discovery_event(
    conn,
    *,
    candidate_id: int,
    candidate: Mapping[str, Any],
    task: Mapping[str, Any],
    result_position: int | None,
) -> int:
    event = build_candidate_discovery_event(
        candidate_id=candidate_id,
        candidate=candidate,
        task=task,
        result_position=result_position,
    )

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO candidate_discovery_events (
                candidate_id,
                google_place_id,
                search_task_id,
                source_location_id,
                source_location_type,
                source_location_name,
                state_name,
                district_name,
                keyword,
                search_query,
                search_level,
                result_position,
                discovered_name,
                discovered_address,
                latitude,
                longitude,
                google_maps_uri
            )
            VALUES (
                %(candidate_id)s,
                %(google_place_id)s,
                %(search_task_id)s,
                %(source_location_id)s,
                %(source_location_type)s,
                %(source_location_name)s,
                %(state_name)s,
                %(district_name)s,
                %(keyword)s,
                %(search_query)s,
                %(search_level)s,
                %(result_position)s,
                %(discovered_name)s,
                %(discovered_address)s,
                %(latitude)s,
                %(longitude)s,
                %(google_maps_uri)s
            )
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id), candidate_id = VALUES(candidate_id),
                source_location_id = VALUES(source_location_id),
                source_location_type = VALUES(source_location_type),
                source_location_name = VALUES(source_location_name),
                state_name = VALUES(state_name),
                district_name = VALUES(district_name),
                keyword = VALUES(keyword),
                search_query = VALUES(search_query),
                search_level = VALUES(search_level),
                result_position = VALUES(result_position),
                discovered_name = VALUES(discovered_name),
                discovered_address = VALUES(discovered_address),
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                google_maps_uri = COALESCE(
                    VALUES(google_maps_uri),
                    candidate_discovery_events.google_maps_uri
                ),
                observed_at = NOW();
            """,
            event,
        )
        return int(cursor.lastrowid)


def upsert_candidate(conn, candidate: Mapping[str, Any]) -> int:
    classification = classify_candidate_name(str(candidate.get("discovered_name") or ""))
    params = {
        "google_place_id": candidate["google_place_id"],
        "google_maps_uri": candidate.get("google_maps_uri"),
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
                google_maps_uri,
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
                %(google_maps_uri)s,
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
            ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id), google_maps_uri = COALESCE(VALUES(google_maps_uri), temple_candidates.google_maps_uri),
                discovered_name = VALUES(discovered_name),
                discovered_address = VALUES(discovered_address),
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                state = COALESCE(VALUES(state), temple_candidates.state),
                district = COALESCE(VALUES(district), temple_candidates.district),
                source_query = VALUES(source_query),
                source_location_id = VALUES(source_location_id),
                confidence = VALUES(confidence),
                confidence_score = VALUES(confidence_score),
                classification_reason = VALUES(classification_reason),
                last_seen_at = NOW();
            """,
            params,
        )
        return int(cursor.lastrowid)


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
