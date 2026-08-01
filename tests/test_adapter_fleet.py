"""Tests for the Fleet MDM adapter (multi-UEM goal).

Reuses the frozen SDK contract assertions from test_sdk_contract.py. No real
network calls: the live path is exercised with requests mocked.
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from lucidfence.core.adapters import FleetAdapter, ADAPTER_REGISTRY
from tests.test_sdk_contract import assert_valid_name, assert_response_shape


def test_fleet_registered_and_named():
    assert "fleet" in ADAPTER_REGISTRY
    assert_valid_name(FleetAdapter().name)


def test_fleet_mock_lock_ok():
    a = FleetAdapter()
    r = a.execute({"device_id": "abc-123"}, "lock", {})
    assert_response_shape(r, "fleet")
    assert r["ok"] is True and r["mock"] is True


def test_fleet_unsupported_action_never_raises():
    a = FleetAdapter()
    for act in ("locate", "clear_passcode", "bogus"):
        r = a.execute({"device_id": "x"}, act, {})
        assert r["ok"] is False and r["error_type"] == "unsupported_action"


def test_fleet_dry_run_builds_request():
    a = FleetAdapter(endpoint_template="https://fleet.example.com")
    r = a.execute({"device_id": "d1"}, "reboot", {}, dry_run=True)
    assert r["mode"] == "dry_run"
    assert r["would_send"]["url"].endswith("/api/v1/fleet/device/d1/restart")


def test_fleet_live_path_mocked():
    try:
        from unittest import mock
    except ImportError:
        print("SKIP: test_fleet_live_path_mocked (unittest.mock unavailable)")
        return

    class FakeResp:
        status_code = 202
        text = "ok"
        def json(self): return {"token": "sess"}
        def raise_for_status(self): pass

    a = FleetAdapter(endpoint_template="https://fleet.example.com",
                     api_token="tok")
    with mock.patch("requests.post", return_value=FakeResp()), \
         mock.patch("requests.request", return_value=FakeResp()) as req:
        r = a.execute({"device_id": "d1"}, "lock", {})
    assert r["ok"] is True and r["mode"] == "live"
    called_url = req.call_args[0][1]
    assert called_url.endswith("/api/v1/fleet/device/d1/lock")
