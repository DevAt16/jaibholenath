import io
import json
from uuid import uuid4

from shiva_discovery.visits_api import create_app


class MemoryStore:
    def __init__(self):
        self.sessions = set()

    def total(self, session_hash=None):
        if session_hash:
            self.sessions.add(session_hash)
        return len(self.sessions)


def request(app, method="GET", payload=None, **overrides):
    body = json.dumps(payload).encode() if payload is not None else b""
    environ = {"REQUEST_METHOD": method, "PATH_INFO": "/api/visits",
               "HTTP_ORIGIN": "https://portal.example", "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body), **overrides}
    result = {}
    def start_response(status, headers):
        result.update(status=status, headers=dict(headers))
    result["body"] = json.loads(b"".join(app(environ, start_response)))
    return result


def test_session_retries_do_not_increment_and_reads_never_increment():
    store = MemoryStore()
    app = create_app(store, "https://portal.example")
    token = str(uuid4())
    assert request(app)["body"] == {"total": 0}
    assert request(app, "POST", {"session_id": token})["body"] == {"total": 1}
    assert request(app, "POST", {"session_id": token})["body"] == {"total": 1}
    assert request(app, "POST", {"session_id": str(uuid4())})["body"] == {"total": 2}
    assert request(app)["body"] == {"total": 2}
    assert token not in store.sessions
    assert all(len(value) == 64 for value in store.sessions)


def test_origins_methods_and_paths_are_restricted():
    store = MemoryStore()
    app = create_app(store, "https://portal.example")
    for origin in ["", "https://other.example"]:
        assert request(app, "POST", {"session_id": str(uuid4())}, HTTP_ORIGIN=origin)["status"].startswith("403")
    assert request(app, "DELETE")["status"].startswith("405")
    assert request(app, PATH_INFO="/api/candidates")["status"].startswith("404")
    assert not store.sessions


def test_preflight_allows_only_configured_origin_and_responses_are_not_cached():
    app = create_app(MemoryStore(), "https://portal.example")
    response = request(app, "OPTIONS")
    assert response["headers"]["Access-Control-Allow-Origin"] == "https://portal.example"
    assert response["headers"]["Cache-Control"] == "no-store"
    assert request(app, "OPTIONS", HTTP_ORIGIN="https://other.example")["status"].startswith("403")


def test_bad_or_excessive_input_never_records_a_visit():
    store = MemoryStore()
    app = create_app(store, "https://portal.example")
    for payload in [None, [], {}, {"session_id": 1}, {"session_id": "bad"},
                    {"session_id": str(uuid4()), "extra": "not allowed"}]:
        assert request(app, "POST", payload)["status"].startswith(("400", "413"))
    assert request(app, "POST", {}, CONTENT_LENGTH="1025")["status"].startswith("413")
    assert request(app, "POST", {}, CONTENT_LENGTH="bad")["status"].startswith("400")
    assert request(app, "POST", {}, CONTENT_TYPE="text/plain")["status"].startswith("415")
    assert not store.sessions


def test_failure_does_not_fabricate_zero_or_leak_connection_details():
    class FailingStore:
        def total(self, _):
            raise RuntimeError("secret connection information")
    response = request(create_app(FailingStore(), "https://portal.example"))
    assert response["status"].startswith("503")
    assert response["body"] == {"error": "Counter unavailable"}
