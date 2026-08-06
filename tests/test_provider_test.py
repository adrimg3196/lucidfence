"""Tests for MDMAdapter.test_connection() used by the wizard's "Probar" button.

Offline: monkeypatches requests.get to simulate live/401/unreachable without
network. Proves the wizard gets an actionable verdict, not a 500.

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_provider_test.py
"""
import os
import sys
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lucidfence.core.adapters.base import MDMAdapter
from lucidfence.core.adapters.simulation import SimulationAdapter

passed = 0
fails = []


def check(cond, msg):
    global passed
    if cond:
        passed += 1
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  FAIL", msg)


class _Resp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text


def test_format_only_when_no_endpoint():
    a = SimulationAdapter()
    a.api_key = "short"
    r = a.test_connection()
    check(r["ok"] is False and r["error_type"] == "format", "short key -> format error")
    a.api_key = "longenoughkey123"
    r2 = a.test_connection()
    check(r2["ok"] is True and r2["verified"] == "format_only", "valid-format key -> format_only ok")


def test_live_and_auth_and_unreachable():
    captured = {}

    class Probe(MDMAdapter):
        name = "probe"
        _api_base = "https://example.test/v1"
        _test_path = "/ping"

        def _headers(self):
            return {"Authorization": "Bearer x"}

        def execute(self, device, action, params, dry_run=False):
            return {"ok": True}

    import requests

    def fake_get(url, headers=None, timeout=30):
        captured["url"] = url
        return _Resp(200, "{}")

    with patch.object(requests, "get", fake_get):
        a = Probe()
        r = a.test_connection()
        check(r["ok"] is True and r["verified"] == "live", "200 -> live ok")
        check(captured["url"] == "https://example.test/v1/ping", "GET hits declared endpoint")

        def fake_401(url, headers=None, timeout=30):
            return _Resp(401, "no")
        with patch.object(requests, "get", fake_401):
            r = a.test_connection()
            check(r["ok"] is False and r["error_type"] == "auth", "401 -> auth error")

        def fake_exc(url, headers=None, timeout=30):
            raise requests.exceptions.ConnectionError("boom")
        with patch.object(requests, "get", fake_exc):
            r = a.test_connection()
            check(r["ok"] is False and r["error_type"] == "unreachable", "conn error -> unreachable")


if __name__ == "__main__":
    test_format_only_when_no_endpoint()
    test_live_and_auth_and_unreachable()
    print(f"\n=== provider-test: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
