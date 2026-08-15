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
from lucidfence.core.adapters.intune import IntuneAdapter, AuthError as IntuneAuth, TransportError as IntuneTransport
from lucidfence.core.adapters.jamf import JamfAdapter, AuthError as JamfAuth, TransportError as JamfTransport
from lucidfence.core.adapters.chromeos import ChromeOSAdapter

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


def test_oauth_adapters_use_grant():
    # Intune: a successful token fetch IS a live check.
    a = IntuneAdapter(tenant_id="t", client_id="c", client_secret="s")
    with patch.object(a, "_fetch_token", return_value="tok"):
        r = a.test_connection()
    check(r["ok"] is True and r["verified"] == "live", "intune: token ok -> live")
    a2 = IntuneAdapter(tenant_id="t", client_id="c", client_secret="s")
    with patch.object(a2, "_fetch_token", side_effect=IntuneAuth("bad")):
        r = a2.test_connection()
    check(r["ok"] is False and r["error_type"] == "auth", "intune: AuthError -> auth")
    a3 = IntuneAdapter(tenant_id="t", client_id="c", client_secret="s")
    with patch.object(a3, "_fetch_token", side_effect=IntuneTransport("down")):
        r = a3.test_connection()
    check(r["ok"] is False and r["error_type"] == "unreachable", "intune: TransportError -> unreachable")

    # Jamf: same shape, Basic -> bearer grant.
    j = JamfAdapter(base_url="https://x.jamfcloud.com", client_id="c", client_secret="s")
    with patch.object(j, "_fetch_token", return_value="tok"):
        r = j.test_connection()
    check(r["ok"] is True and r["verified"] == "live", "jamf: token ok -> live")
    j2 = JamfAdapter(base_url="https://x.jamfcloud.com", client_id="c", client_secret="s")
    with patch.object(j2, "_fetch_token", side_effect=JamfAuth("bad")):
        r = j2.test_connection()
    check(r["ok"] is False and r["error_type"] == "auth", "jamf: AuthError -> auth")

    # ChromeOS: refresh_token grant -> RuntimeError mapping.
    c = ChromeOSAdapter(client_id="c", client_secret="s", refresh_token="r")
    with patch.object(c, "_fetch_access_token", return_value="tok"):
        r = c.test_connection()
    check(r["ok"] is True and r["verified"] == "live", "chromeos: token ok -> live")
    c2 = ChromeOSAdapter(client_id="c", client_secret="s", refresh_token="r")
    with patch.object(c2, "_fetch_access_token", side_effect=RuntimeError("Google OAuth refresh HTTP 401")):
        r = c2.test_connection()
    check(r["ok"] is False and r["error_type"] == "auth", "chromeos: 401 -> auth")
    c3 = ChromeOSAdapter(client_id="c", client_secret="s", refresh_token="r")
    with patch.object(c3, "_fetch_access_token", side_effect=RuntimeError("unreachable")):
        r = c3.test_connection()
    check(r["ok"] is False and r["error_type"] == "unreachable", "chromeos: unreachable -> unreachable")


if __name__ == "__main__":
    test_format_only_when_no_endpoint()
    test_live_and_auth_and_unreachable()
    test_oauth_adapters_use_grant()
    print(f"\n=== provider-test: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
