"""Issue #89: the engine (and multi-UEM orchestrator) must consult the
adapter's declarative-capability flags (supports_ddm / supports_dsc /
supports_amapi_policy) at action time and route eligible actions through the
declarative channel (DDM declaration / DSC config / AMAPI policy) instead of
the blind imperative execute path.

These tests assert acceptance #1 and #2 of #89:

  * With supports_ddm=True and an eligible device (management_mode set by #88),
    a destructive action (lock/wipe) is routed to the declarative builder
    (JamfAdapter._apply_ddm -> build_declarations), tagged
    enforcement="declarative", and the imperative command method is NEVER
    invoked.
  * Without the flag (or ineligible device) the action falls through to the
    imperative adapter.execute as before.
  * The MultiUEMOrchestrator applies the same gate.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.adapters.jamf import JamfAdapter
from lucidfence.core.adapters.windows_conformidad import WindowsConformidadAdapter
from lucidfence.core.declarative import declarative_path_for
from lucidfence.core.state_store import DeviceState
from lucidfence.core.multiuem import (
    MultiUEMOrchestrator,
    NormalizedDevice,
    ProviderBinding,
    ProviderCapabilities,
)
from helpers import make_temp_engine


POLICY = {"id": "pol-1", "name": "geofence"}
PROFILE_URL = "https://mdm.example.com/profile.mobileconfig"


# --- helpers ---------------------------------------------------------------

class _ImperativeSpy:
    """Wraps an adapter and records whether the blind imperative execute ran.

    The declarative builder (e.g. _apply_ddm) is a different method on the same
    adapter, so we spy on the public ``execute`` entry and assert that the
    imperative command path is not taken for an eligible declarative action.
    """

    def __init__(self, adapter):
        self._adapter = adapter
        self.imperative_calls = []

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def execute(self, device, action, params, dry_run=False):
        # The declarative builder is reached via ``execute`` too (Jamf routes
        # action=="apply_ddm" to _apply_ddm). We only flag the BLIND imperative
        # commands (lock/wipe) as "imperative_calls" — those are the ones the
        # declarative gate must suppress.
        if action in ("lock", "wipe", "reboot", "clear_passcode"):
            self.imperative_calls.append((action, params))
        return self._adapter.execute(device, action, params, dry_run=dry_run)


def _eligible_ddm_device():
    return DeviceState(
        device_id="dev-1", name="iPad HQ", platform="ios",
        os_version="17.4.1", management_mode="fully_managed",
        ownership="company", fence_state="outside",
    )


def _ineligible_ddm_device():
    # No management_mode reported -> gate returns "unknown" -> imperative.
    return DeviceState(
        device_id="dev-2", name="BYOD iPhone", platform="ios",
        os_version="17.4.1", management_mode=None,
        ownership=None, fence_state="outside",
    )


# --- acceptance #2: DDM declarative routing (engine) -----------------------

def test_engine_routes_ddm_declaratively_and_skips_imperative():
    engine = make_temp_engine()
    spy = _ImperativeSpy(JamfAdapter(live=False))
    engine.adapter = spy
    engine.dry_run = False
    device = _eligible_ddm_device()

    res = engine.run_command(device, "lock", {"policy": POLICY, "profile_url": PROFILE_URL})

    # Routed to the declarative channel.
    assert res.get("enforcement") == "declarative", res
    assert res.get("declarative_subaction") == "apply_ddm", res
    assert res.get("original_action") == "lock", res
    # The blind imperative lock command was NOT executed.
    assert spy.imperative_calls == [], f"imperative ran: {spy.imperative_calls}"
    # The declaration was actually built (DDM payload present).
    assert "declarations" in res, res
    assert res["declarations"]["configurations"], res


def test_engine_falls_back_to_imperative_when_not_eligible():
    engine = make_temp_engine()
    spy = _ImperativeSpy(JamfAdapter(live=False))
    engine.adapter = spy
    engine.dry_run = False
    device = _ineligible_ddm_device()

    res = engine.run_command(device, "lock", {})

    # No declarative routing happened.
    assert res.get("enforcement") != "declarative", res
    # The imperative command DID run (the legacy behaviour is preserved).
    assert spy.imperative_calls == [("lock", {})], spy.imperative_calls


def test_engine_routes_wipe_declaratively_for_ddm_device():
    engine = make_temp_engine()
    spy = _ImperativeSpy(JamfAdapter(live=False))
    engine.adapter = spy
    engine.dry_run = False
    engine.allow_wipe = True
    device = _eligible_ddm_device()

    res = engine.run_command(device, "wipe", {"policy": POLICY, "profile_url": PROFILE_URL})

    assert res.get("enforcement") == "declarative", res
    assert res.get("declarative_subaction") == "apply_ddm", res
    assert spy.imperative_calls == [], spy.imperative_calls


# --- acceptance #1: the flags drive the route (not just hardcoded) ---------

def test_gate_honours_supports_ddm_flag_absence():
    # Adapter with supports_ddm=False -> no declarative routing even for an
    # eligible-looking device (the flag is the gate, per #89).
    from lucidfence.core.adapters.fleet import FleetAdapter
    engine = make_temp_engine()
    spy = _ImperativeSpy(FleetAdapter())
    engine.adapter = spy
    engine.dry_run = False
    device = _eligible_ddm_device()  # would be eligible IF supports_ddm were set

    res = engine.run_command(device, "lock", {})
    assert res.get("enforcement") != "declarative", res
    # FleetAdapter has no lock command; it returns a structured error rather
    # than raising — the point is the declarative path was never selected.
    assert spy.imperative_calls == [("lock", {})], spy.imperative_calls


# --- acceptance #2: multi-UEM orchestrator applies the same gate -----------

def test_orchestrator_routes_ddm_declaratively():
    adapter = JamfAdapter(live=False)
    spy = _ImperativeSpy(adapter)
    binding = ProviderBinding(
        name="jamf",
        capabilities=ProviderCapabilities(actions=frozenset({"lock", "wipe"})),
        fetch_devices=lambda: [],
        execute_action=spy.execute,
    )
    orch = MultiUEMOrchestrator([binding])
    device = NormalizedDevice(
        "jamf:1", "jamf", "1", "iPad HQ", "ios",
        management_mode="fully_managed", ownership="company",
    )

    res = orch.execute(
        {"provider": "jamf", "provider_device_id": "1", "provider_refs": {"jamf": "1"},
         "management_mode": "fully_managed", "ownership": "company",
         "platform": "ios", "os_version": "17.4.1"},
        "lock", {"policy": POLICY, "profile_url": PROFILE_URL}, dry_run=False,
    )
    assert res.get("enforcement") == "declarative", res
    assert res.get("declarative_subaction") == "apply_ddm", res
    # The blind imperative lock command was never issued.
    assert spy.imperative_calls == [], spy.imperative_calls
    # The DDM declaration was built.
    assert "declarations" in res, res


# --- acceptance #3: capability matrix reflects the flags -------------------

def test_provider_catalog_reflects_declarative_flags():
    from lucidfence.saas.providers import PROVIDER_CATALOG
    # jamf exposes DDM; windows_conformidad exposes DSC; AMAPI pending #90.
    assert PROVIDER_CATALOG["jamf"]["declarative"]["supports_ddm"] is True
    assert PROVIDER_CATALOG["windows_conformidad"]["declarative"]["supports_dsc"] is True
    assert PROVIDER_CATALOG["jamf"]["declarative"]["supports_amapi_policy"] is False
    assert PROVIDER_CATALOG["windows_conformidad"]["declarative"]["supports_amapi_policy"] is False
    # The catalog values mirror the adapter flags (single source of truth).
    assert JamfAdapter.supports_ddm is True
    assert WindowsConformidadAdapter.supports_dsc is True


def test_declarative_gate_matches_adapter_flags():
    # The gate and the adapter flags agree on eligibility for a DDM device.
    dev = {"management_mode": "fully_managed", "ownership": "company"}
    assert declarative_path_for(dev, supports_ddm=JamfAdapter.supports_ddm) == "declarative"
    dev_dsc = {"management_mode": "fully_managed", "ownership": "company"}
    assert declarative_path_for(dev_dsc, supports_dsc=WindowsConformidadAdapter.supports_dsc) == "declarative"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n=== {passed} passed, {failed} failed ===")
    sys.exit(1 if failed else 0)
