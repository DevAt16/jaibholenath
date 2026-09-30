"""Persist each received page before attempting another budgeted request."""
from .dedupe import deduplicate_places
from .places_client import GooglePlacesError, place_to_candidate
from .request_budget import BudgetBlocked
from .repositories import complete_task, record_candidate_discovery_event, upsert_candidate


def process_task(conn, client, task, *, page_size, max_pages):
    raw_count = 0
    seen = set()
    try:
        for page in client.iter_text_pages(task['search_query'], page_size=page_size, max_pages=max_pages):
            with conn.transaction():
                for place in deduplicate_places(page).unique_places:
                    candidate = place_to_candidate(place, source_query=task['search_query'],
                        source_location_id=int(task['location_id']), state=task.get('state_name'),
                        district=task.get('district_name'))
                    place_id = candidate['google_place_id']
                    if not place_id or place_id in seen:
                        continue
                    seen.add(place_id)
                    candidate_id = upsert_candidate(conn, candidate)
                    record_candidate_discovery_event(conn, candidate_id=candidate_id,
                        candidate=candidate, task=task, result_position=len(seen))
                raw_count += len(page)
                complete_task(conn, task_id=task['id'], status='running', result_count=raw_count)
    except BudgetBlocked as error:
        with conn.transaction():
            complete_task(conn, task_id=task['id'], status='pending', result_count=raw_count,
                          last_error=str(error))
        return 'paused', raw_count, len(seen)
    except (GooglePlacesError, ValueError, OSError) as error:
        with conn.transaction():
            complete_task(conn, task_id=task['id'], status='failed', result_count=raw_count,
                          last_error=str(error)[:2000])
        return 'failed', raw_count, len(seen)
    with conn.transaction():
        complete_task(conn, task_id=task['id'], status='done', result_count=raw_count)
    return 'done', raw_count, len(seen)
