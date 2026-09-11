"""Small WSGI API for the public portal counter; never exposes discovery tables."""

import hashlib
import json
import logging
import os
from uuid import UUID


class MySQLVisitStore:
    def total(self, session_hash=None):
        from .db import connect

        # A separate runtime account keeps the public API out of discovery data.
        dsn = os.environ.get("VISITS_DATABASE_URL")
        if not dsn:
            raise RuntimeError("Visit database is not configured")
        with connect(dsn, prefix="VISITS_MYSQL") as conn:
            with conn.transaction():
                with conn.cursor() as cursor:
                    # Serialize registrations before checking the token. The session
                    # insert and total update commit together, including on retries.
                    cursor.execute("SELECT total FROM portal_visit_totals WHERE singleton = 1 FOR UPDATE")
                    row = cursor.fetchone()
                    if row is None:
                        raise RuntimeError("Visit counter migration has not been applied")
                    total = int(row[0])
                    if session_hash:
                        cursor.execute("SELECT session_hash FROM portal_visit_sessions WHERE session_hash = %s", (session_hash,))
                        if cursor.fetchone() is None:
                            cursor.execute("INSERT INTO portal_visit_sessions (session_hash) VALUES (%s)", (session_hash,))
                            cursor.execute("UPDATE portal_visit_totals SET total = total + 1 WHERE singleton = 1")
                            total += 1
                    return total


def create_app(store=None, allowed_origin=None):
    store = store if store is not None else MySQLVisitStore()
    allowed_origin = allowed_origin or os.environ.get("VISITS_ALLOWED_ORIGIN", "").rstrip("/")

    def application(environ, start_response):
        origin = environ.get("HTTP_ORIGIN", "")
        method = environ.get("REQUEST_METHOD", "GET")
        headers = [("Content-Type", "application/json; charset=utf-8"),
                   ("Cache-Control", "no-store"), ("Vary", "Origin"),
                   ("X-Content-Type-Options", "nosniff")]
        if origin and origin == allowed_origin:
            headers.append(("Access-Control-Allow-Origin", allowed_origin))

        def respond(status, payload):
            body = json.dumps(payload).encode("utf-8")
            start_response(status, headers + [("Content-Length", str(len(body)))])
            return [body]

        if environ.get("PATH_INFO") != "/api/visits":
            return respond("404 Not Found", {"error": "Not found"})
        if not allowed_origin:
            return respond("503 Service Unavailable", {"error": "Counter unavailable"})
        if origin and origin != allowed_origin:
            return respond("403 Forbidden", {"error": "Origin not allowed"})
        if method == "OPTIONS":
            if origin != allowed_origin:
                return respond("403 Forbidden", {"error": "Origin required"})
            headers.extend([("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                            ("Access-Control-Allow-Headers", "Content-Type")])
            return respond("200 OK", {})
        if method not in {"GET", "POST"}:
            headers.append(("Allow", "GET, POST, OPTIONS"))
            return respond("405 Method Not Allowed", {"error": "Method not allowed"})
        session_hash = None
        if method == "POST":
            if origin != allowed_origin:
                return respond("403 Forbidden", {"error": "Origin required"})
            if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/json":
                return respond("415 Unsupported Media Type", {"error": "JSON required"})
            try:
                length = int(environ.get("CONTENT_LENGTH") or "0")
            except ValueError:
                return respond("400 Bad Request", {"error": "Invalid content length"})
            if length <= 0 or length > 1024:
                return respond("413 Content Too Large", {"error": "Invalid request size"})
            try:
                payload = json.loads(environ["wsgi.input"].read(length))
                if not isinstance(payload, dict) or set(payload) != {"session_id"}:
                    raise ValueError("Invalid payload")
                token = UUID(payload["session_id"])
                if token.version != 4:
                    raise ValueError("Random session ID required")
                session_hash = hashlib.sha256(str(token).encode("ascii")).hexdigest()
            except (ValueError, TypeError, AttributeError, UnicodeDecodeError):
                return respond("400 Bad Request", {"error": "Invalid session ID"})
        try:
            total = store.total(session_hash)
        except Exception as error:
            logging.error("Portal counter unavailable (%s)", type(error).__name__)
            return respond("503 Service Unavailable", {"error": "Counter unavailable"})
        return respond("200 OK", {"total": total})

    return application


application = create_app()
