"""Tests for the Multi-UEM wiring exposed via the engine and adapters.

These are offline (no live UEM calls): they prove the orchestrator is now
wired into the engine and that remediation actions route to the right adapter
by device provider_refs, and that DeviceState carries provider_refs.

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_multiuem_api.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lucidfence.core.adapters import build_bindings, ADAPTER_REGISTRY
from lucidfence.core.multiuem import MultiUEMOrchestrator
from lucidfence.core.state_store import DeviceState
from lucidfence.core.engine import Engine

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


def test_build_bindings():
    bindings = build_bindings([
        {"name": "simulation", "org_id": "o1"},
        {"name": "applivery", "org_id": "o2", "api_key": "k"},
        {"name": "not_a_real_provider", "org_id": "o3"},
    ])
    names = {b.name for b in bindings}
    check("simulation" in names, "build_bindings includes simulation")
    check("applivery" in names, "build_bindings includes applivery")
    check("not_a_real_provider" not in names, "build_bindings skips unknown providers")
    check(len(bindings) == 2, "build_bindings drops unknown providers only")


def test_engine_routes_by_provider_refs():
    calls = []

    class FakeAdapter:
        name = "fakeuem"

        def __init__(self, *args, **kwargs):
            pass

        def execute(self, device, action, params, dry_run=False):
            calls.append((action, getattr(device, "device_id", None)))
            return {"ok": True, "adapter": "fakeuem", "action": action}

        def fetch_devices(self):
            return []

    ADAPTER_REGISTRY["fakeuem"] = FakeAdapter
    try:
        cfg = {"autostart": False, "providers": [
            {"name": "simulation", "org_id": "o1"},
            {"name": "fakeuem", "org_id": "o2"},
        ]}
        eng = Engine(cfg)
        try:
            check(eng.orchestrator is not None, "engine wires orchestrator from providers")

            class Dev:
                device_id = "dev-9"
                provider_refs = {"fakeuem": "remote-9"}

            eng._execute_action(Dev(), "lock", {})
            check(len(calls) == 1 and calls[0][0] == "lock",
                  "action routed to fakeuem via provider_refs")
        finally:
            try:
                eng.stop()
            except Exception:
                pass
    finally:
        ADAPTER_REGISTRY.pop("fakeuem", None)


def test_device_state_carries_provider_refs():
    ds = DeviceState(device_id="d1", name="n", platform="android",
                     provider_refs={"applivery": "a1", "jamf": "j1"})
    check(ds.provider_refs == {"applivery": "a1", "jamf": "j1"},
          "DeviceState persists provider_refs")
    d = ds.to_dict()
    check(d.get("provider_refs") == {"applivery": "a1", "jamf": "j1"},
          "provider_refs survives to_dict() round-trip")


if __name__ == "__main__":
    test_build_bindings()
    test_engine_routes_by_provider_refs()
    test_device_state_carries_provider_refs()
    print(f"\n=== multiuem-api: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
