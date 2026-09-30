"""Private n8n control surface for the unchanged, bounded discovery CLI."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [sys.executable, str(ROOT / "scripts/run_expansion_batch.py"),
           "--limit", "10", "--max-requests", "30", "--max-pages", "3",
           "--state", "Uttar Pradesh", "--location-type", "urban_local_body"]
SUCCESS = {"completed", "already_ran", "export_only", "dry_run"}
STATUSES = SUCCESS | {"blocked", "failed", "paused", "needs_review", "running"}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def parse_result(completed):
    """Only the CLI's JSON contract is retained; raw child logs never escape."""
    output = completed.stdout if completed.returncode == 0 else completed.stderr
    try:
        result = json.loads(output)
        if not isinstance(result, dict) or result.get("status") not in STATUSES:
            raise ValueError
        keys = ("status", "reason", "error_type", "requests", "completed",
                "failed", "run_date", "previous_status", "raw_results", "snapshot", "remaining_requests",
                "max_requests", "matching_pending_tasks")
        result = {key: result[key] for key in keys if key in result}
        if completed.returncode != 0 and result["status"] in SUCCESS:
            raise ValueError
        return result
    except (ValueError, TypeError):
        return {"status": "failed", "error_type": "InvalidWorkerResult",
                "reason": "Inspect the discovery journal before another live invocation."}


class Controller:
    def __init__(self, state, token, live=False, runner=subprocess.run):
        if len(token) < 32:
            raise ValueError("Configure a control token of at least 32 characters.")
        self.state = Path(state)
        self.token = token
        self.live = live
        self.runner = runner
        self.lock = threading.Lock()
        self.state.mkdir(parents=True, exist_ok=True)

    def authorized(self, supplied):
        return hmac.compare_digest(self.token.encode(), (supplied or "").encode())

    def last(self):
        try:
            return json.loads((self.state / "latest.json").read_text())
        except (OSError, ValueError):
            return {"status": "not_run"}

    def daily_health(self):
        try:
            result = json.loads((self.state / "last-daily.json").read_text())
            recent = datetime.fromisoformat(result["finished_at"]) > datetime.now(timezone.utc) - timedelta(hours=36)
            healthy = result["result"]["status"] in {"completed", "already_ran"} and recent
            return (200 if healthy else 503), result
        except (OSError, ValueError, KeyError, TypeError):
            return 503, {"status": "no_daily_result"}

    def invoke(self, mode):
        if mode not in {"run", "preflight", "export"}:
            return 404, {"status": "unknown_operation"}
        if mode == "run" and not self.live:
            return 409, {"status": "live_disabled"}
        if not self.lock.acquire(blocking=False):
            return 409, {"status": "busy"}
        record = {"invocation_id": str(uuid.uuid4()), "mode": mode,
                  "started_at": now(), "result": {"status": "running"}}
        try:
            write_json(self.state / "latest.json", record)
            args = COMMAND + ({"preflight": ["--dry-run"], "export": ["--export-only"]}.get(mode, []))
            try:
                completed = self.runner(args, cwd=ROOT, capture_output=True, text=True, timeout=3600)
                result = parse_result(completed)
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                result = {"status": "needs_review", "reason": "Worker timed out. Inspect the interrupted journal; do not reset it or retry Google tasks."}
                exit_code = 1
            except Exception as error:
                result = {"status": "failed", "error_type": type(error).__name__,
                          "reason": "Inspect the discovery journal before another live invocation."}
                exit_code = 1
            record.update(finished_at=now(), exit_code=exit_code, result=result)
            write_json(self.state / "history" / (record["invocation_id"] + ".json"), record)
            write_json(self.state / "latest.json", record)
            if mode == "run":
                write_json(self.state / "last-daily.json", record)
            return (200 if exit_code == 0 and result["status"] in SUCCESS else 503), record
        finally:
            self.lock.release()


def handler(controller):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, value):
            payload = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A disconnected caller does not restart discovery.

        def do_GET(self):
            if self.path == "/health":
                return self.respond(200, {"status": "healthy", "live_enabled": controller.live})
            if self.path == "/health/daily":
                code, record = controller.daily_health()
                # Monitoring endpoints don't disclose research records.
                return self.respond(code, {"status": record.get("result", record).get("status"), "finished_at": record.get("finished_at")})
            if not controller.authorized(self.headers.get("X-JBN-Token")):
                return self.respond(401, {"status": "unauthorized"})
            if self.path == "/status":
                return self.respond(200, controller.last())
            self.respond(404, {"status": "not_found"})

        def do_POST(self):
            if not controller.authorized(self.headers.get("X-JBN-Token")):
                return self.respond(401, {"status": "unauthorized"})
            # Fixed commands only. No caller-controlled limits, locations or billing.
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 1024 or self.headers.get("Transfer-Encoding"):
                    raise ValueError
                body = self.rfile.read(length)
                if body.strip() and json.loads(body) != {}:
                    raise ValueError
            except (ValueError, TypeError):
                return self.respond(400, {"status": "invalid_body"})
            self.respond(*controller.invoke(self.path.removeprefix("/")))

        def log_message(self, *_args):
            pass  # Headers and child output never enter access logs.
    return Handler


def main():
    token = Path(os.environ.get("JBN_TOKEN_FILE", "/run/secrets/control_token")).read_text().strip()
    controller = Controller(os.environ.get("JBN_STATE_DIR", "/app/state"), token,
                            live=os.environ.get("JBN_LIVE_ENABLED", "false").lower() == "true")
    server = ThreadingHTTPServer(("0.0.0.0", 8787), handler(controller))
    server.daemon_threads = False
    server.serve_forever()


if __name__ == "__main__":
    main()
