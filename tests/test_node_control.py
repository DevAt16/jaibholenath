from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

path = Path(__file__).parents[1] / 'node/control.py'
spec = importlib.util.spec_from_file_location('control', path)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
TOKEN = 'test-control-token-' + 'x' * 40


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def controller(self, live=True, runner=None):
        return control.Controller(self.temp.name, TOKEN, live=live,
            runner=runner or (lambda args, **kw: subprocess.CompletedProcess(args, 0, '{"status":"already_ran","requests":0}', '')))

    def test_fixed_command_and_preflight(self):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, '{"status":"dry_run"}', '')
        controller = self.controller(live=False, runner=run)
        self.assertEqual(controller.invoke('run')[0], 409)
        self.assertEqual(calls, [])
        self.assertEqual(controller.invoke('preflight')[0], 200)
        self.assertIn('--dry-run', calls[0])
        self.assertEqual(calls[0][calls[0].index('--max-requests') + 1], '30')
        self.assertEqual(calls[0][calls[0].index('--limit') + 1], '10')
        self.assertFalse((Path(self.temp.name) / 'last-daily.json').exists())

    def test_budget_block_is_failure_and_recorded(self):
        c = self.controller(runner=lambda args, **kw: subprocess.CompletedProcess(args, 2, '', '{"status":"blocked","reason":"Usage is stale"}'))
        code, result = c.invoke('run')
        self.assertEqual(code, 503)
        self.assertEqual(result['exit_code'], 2)
        self.assertEqual(c.daily_health()[0], 503)
        self.assertEqual(c.last()['result']['status'], 'blocked')

    def test_child_exception_and_raw_output_do_not_leak(self):
        secret = 'sensitive-unexpected-child-output'
        c = self.controller(runner=lambda args, **kw: subprocess.CompletedProcess(args, 1, '', secret))
        self.assertEqual(c.invoke('run')[0], 503)
        self.assertNotIn(secret, (Path(self.temp.name) / 'latest.json').read_text())
        def raise_secret(*args, **kw):
            raise RuntimeError(secret)
        c.runner = raise_secret
        self.assertEqual(c.invoke('run')[0], 503)
        self.assertNotIn(secret, (Path(self.temp.name) / 'latest.json').read_text())

    def test_concurrent_call_does_not_start_second_child(self):
        entered, release = threading.Event(), threading.Event()
        def run(args, **kw):
            entered.set(); release.wait(5)
            return subprocess.CompletedProcess(args, 0, '{"status":"already_ran","requests":0}', '')
        c = self.controller(runner=run)
        with ThreadPoolExecutor(1) as pool:
            first = pool.submit(c.invoke, 'run')
            self.assertTrue(entered.wait(2))
            self.assertEqual(c.invoke('run')[0], 409)
            release.set()
            self.assertEqual(first.result()[0], 200)
        self.assertEqual(len(list((Path(self.temp.name) / 'history').glob('*.json'))), 1)
        self.assertEqual(c.daily_health()[0], 200)

    def test_http_auth_and_no_caller_control(self):
        c = self.controller()
        server = control.ThreadingHTTPServer(('127.0.0.1', 0), control.handler(c))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection(*server.server_address)
            conn.request('POST', '/run', '{}')
            response = conn.getresponse()
            self.assertEqual(response.status, 401); response.read()
            conn.request('POST', '/run', '{"max_requests":300}', {'X-JBN-Token': TOKEN})
            response = conn.getresponse()
            self.assertEqual(response.status, 400); response.read()
            conn.request('POST', '/run', '{}', {'X-JBN-Token': TOKEN})
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['result']['requests'], 0)
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_timeout_requires_review(self):
        def timeout(args, **kw):
            raise subprocess.TimeoutExpired(args, 3600)
        c = self.controller(runner=timeout)
        self.assertEqual(c.invoke('run')[1]['result']['status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
