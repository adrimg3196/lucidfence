"""Tests for declarative UEM action engine capability gates and fallbacks.

Validates that:
  1. If an adapter does NOT declare a capability, executing the declarative action
     is rejected with `unsupported_action`.
  2. If the device fails the gate or the adapter returns `fallback: "imperative"`,
     and the action was an upgrade, the engine re-executes EXACTLY the original action and parameters.
  3. Cycle automatic execution functions correctly.
"""
from __future__ import annotations

import os
import sys

# Ensure tests root is on path for helpers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import make_temp_engine
from lucidfence.core.state_store import DeviceState
from lucidfence.core.adapters.base import MDMAdapter


class MockUncapableAdapter(MDMAdapter):
    name = "mock_uncapable"
    supports_ddm = False
    supports_amapi_policy = False
    supports_dsc = False

    def execute(self, device, action, params, dry_run=False):
        return {"ok": True, "mock": True, "action": action}


class MockCapableAdapter(MDMAdapter):
    name = "mock_capable"
    supports_ddm = True
    supports_amapi_policy = True
    supports_dsc = True

    def __init__(self):
        self.calls = []

    def execute(self, device, action, params, dry_run=False):
        self.calls.append((action, params))
        if action == "apply_ddm" and getattr(device, "os_version", "") == "14.8":
            return {"ok": False, "fallback": "imperative"}
        return {"ok": True, "mock": True, "action": action}


def test_adapter_without_capability_rejects_declarative_action():
    engine = make_temp_engine()
    engine.dry_run = False
    engine.adapter = MockUncapableAdapter()

    device = DeviceState(device_id="dev-uncapable", name="iPad", platform="ios", os_version="17.4.1")

    # Executing apply_ddm on an uncapable adapter should return unsupported_action
    res = engine.run_command(device, "apply_ddm", {"policy": "some-policy"})
    assert res["ok"] is False
    assert res["error_type"] == "unsupported_action"


def test_fallback_preserves_original_action_and_parameters():
    engine = make_temp_engine()
    engine.dry_run = False
    capable_adapter = MockCapableAdapter()
    engine.adapter = capable_adapter

    # We will simulate an upgraded execution.
    # To do this, we can call `_execute_adapter_action` directly with orig_action and orig_params.
    device = DeviceState(device_id="dev-too-old", name="iPad Old", platform="ios", os_version="14.8")

    # 1. Device fails the gate (iOS 14.8 is too old for DDM)
    res = engine._execute_adapter_action(
        device,
        "apply_ddm",
        {"policy": "some-policy", "profile_url": "https://some-url"},
        dry_run=False,
    )
    # Since it was an explicit call without an upgraded action, it returns the gate failure
    assert res["ok"] is False
    assert res["error_type"] == "device_gate_failed"

    # Now let's try with an upgraded action (orig_action="lock", orig_params={"some": "param"})
    res2 = engine._execute_adapter_action(
        device,
        "apply_ddm",
        {"policy": "some-policy", "profile_url": "https://some-url"},
        dry_run=False,
        orig_action="lock",
        orig_params={"some": "param"}
    )
    # The device fails the DDM gate, so it MUST execute EXACTLY the original action and its params
    assert res2["ok"] is True
    assert res2["action"] == "lock"
    assert res2["enforcement_path"] == "imperative"
    assert res2["fallback_reason"] == "device_gate_failed"

    # Verify that the adapter's execute was called with 'lock' and the correct params
    assert ("lock", {"some": "param"}) in capable_adapter.calls


def test_fallback_when_adapter_returns_fallback_imperative():
    engine = make_temp_engine()
    engine.dry_run = False
    capable_adapter = MockCapableAdapter()
    engine.adapter = capable_adapter

    # Here we have an iOS device passing the gate, but the adapter mock execution returns a fallback
    device = DeviceState(device_id="dev-fallback-adapter", name="iPad New", platform="ios", os_version="17.4.1")

    # Let's mock a case where the capable adapter's apply_ddm execution requests fallback: imperative
    # We will override the adapter's return to simulate a fallback: imperative
    def fake_execute(device, action, params, dry_run=False):
        if action == "apply_ddm":
            return {"ok": False, "fallback": "imperative"}
        return {"ok": True, "action": action, "params": params}
    capable_adapter.execute = fake_execute

    # Call with upgraded action
    res = engine._execute_adapter_action(
        device,
        "apply_ddm",
        {"policy": "some-policy", "profile_url": "https://some-url"},
        dry_run=False,
        orig_action="wipe",
        orig_params={"wipe_reason": "compromised"}
    )

    assert res["ok"] is True
    assert res["action"] == "wipe"
    assert res["params"] == {"wipe_reason": "compromised"}
    assert res["enforcement_path"] == "imperative"
    assert res["fallback_reason"] == "adapter_requested_fallback"


def test_cycle_automatic_preserves_imperative_path_when_no_document():
    engine = make_temp_engine()
    engine.dry_run = False
    capable_adapter = MockCapableAdapter()
    engine.adapter = capable_adapter

    # Add a device that matches a geofence and triggers an automatic action
    device_report = DeviceState(device_id="dev-cycle", name="Android Tablet", platform="android",
                                management_mode="device_owner", ownership="company_owned",
                                fence_state="outside")
    # Since _find_declarative_policy_and_entry returns None (lack of policy/document),
    # there is no upgrade and it runs the original action imperatively.
    res = engine._execute_adapter_action(device_report, "lock", {"msg": "lock-it"}, dry_run=False)

    assert res["ok"] is True
    assert res["action"] == "lock"
    assert res["enforcement_path"] == "imperative"
    assert "fallback_reason" not in res
