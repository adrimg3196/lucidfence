"""Issue #88: adapters populate management_mode/ownership; gate no longer dark.

Before #88 those fields existed nowhere in the model, so the declarative
gate (core.declarative) fell through to imperative for every device. These
tests assert:

  1. Jamf (the DDM-capable adapter) derives management_mode/ownership from the
     REAL UEM response (managed / supervised booleans), not from guesses.
  2. NormalizedDevice carries the fields and the orchestrator validates them.
  3. The declarative gate now returns "declarative" (not imperative) when an
     adapter supports a declarative channel AND the device reports an eligible
     management_mode — i.e. the gate is no longer permanently imperative.
"""
from lucidfence.core.adapters.jamf import JamfAdapter
from lucidfence.core.declarative import declarative_path_for, MANAGEMENT_MODES
from lucidfence.core.multiuem import (
    MultiUEMOrchestrator,
    NormalizedDevice,
    ProviderBinding,
    ProviderCapabilities,
)


# --- 1. Jamf derives management_mode/ownership from the real UEM response ---

def test_jamf_fetch_devices_skips_mock_to_avoid_fabricated_signals():
    # En mock no fabricamos flota ni señales declarativas falsas.
    assert JamfAdapter(live=False).fetch_devices() == []


def test_jamf_derives_fully_managed_when_supervised():
    raw = {"id": "42", "general": {
        "name": "iPhone 15", "platform": "iOS", "managed": True,
        "supervised": True, "serialNumber": "SERIAL1",
        "managementId": "mid-1", "model": "iPhone15,2",
        "osVersion": "17.4", "username": "alice",
    }}
    dev = JamfAdapter(live=False)._normalize_fetch_device(raw)
    assert isinstance(dev, NormalizedDevice)
    assert dev.management_mode == "fully_managed"
    assert dev.ownership == "company"
    assert dev.platform == "ios"
    assert dev.serial_number == "SERIAL1"
    assert dev.inventory.get("jamf_management_id") == "mid-1"


def test_jamf_derives_mdm_when_managed_not_supervised():
    raw = {"id": "43", "general": {
        "name": "iPad", "platform": "iPadOS", "managed": True,
        "supervised": False,
    }}
    dev = JamfAdapter(live=False)._normalize_fetch_device(raw)
    assert dev.management_mode == "mdm"
    assert dev.ownership == "company"


def test_jamf_reports_none_management_mode_when_unmanaged():
    raw = {"id": "44", "general": {
        "name": "BYOD phone", "platform": "iOS", "managed": False,
    }}
    dev = JamfAdapter(live=False)._normalize_fetch_device(raw)
    # No inferimos: unmanaged => señal declarativa vacía.
    assert dev.management_mode is None
    assert dev.ownership is None


# --- 2. NormalizedDevice carries fields + orchestrator validates them ---

def test_normalized_device_carries_management_mode_and_ownership():
    dev = NormalizedDevice(
        "jamf:1", "jamf", "1", "One", "ios",
        management_mode="fully_managed", ownership="company",
    )
    assert dev.management_mode == "fully_managed"
    assert dev.ownership == "company"
    # Defaults stay None for adapters that don't report.
    bare = NormalizedDevice("intune:2", "intune", "2", "Two", "android")
    assert bare.management_mode is None
    assert bare.ownership is None


def test_orchestrator_accepts_valid_management_mode_in_records():
    dev = NormalizedDevice(
        "jamf:1", "jamf", "1", "One", "ios",
        management_mode="fully_managed", ownership="company",
    )
    orch = MultiUEMOrchestrator([ProviderBinding(
        name="jamf",
        capabilities=ProviderCapabilities(inventory=True),
        fetch_devices=lambda: [dev],
    )])
    result = orch.sync()
    assert result.status == "ok"
    assert result.devices[0].management_mode == "fully_managed"
    assert result.devices[0].ownership == "company"


def test_orchestrator_rejects_malformed_management_mode():
    # A non-printable / oversized value must be rejected, not persisted.
    dev = NormalizedDevice(
        "jamf:1", "jamf", "1", "One", "ios",
        management_mode="\x00hack",
    )
    orch = MultiUEMOrchestrator([ProviderBinding(
        name="jamf",
        capabilities=ProviderCapabilities(inventory=True),
        fetch_devices=lambda: [dev],
    )])
    result = orch.sync()
    assert result.status == "error"


# --- 3. The declarative gate is no longer permanently imperative ---

def test_gate_is_declarative_when_adapter_reports_eligible_mode():
    # Jamf supports DDM; a supervised device must route declaratively.
    device = {"management_mode": "fully_managed", "ownership": "company"}
    assert declarative_path_for(device, supports_ddm=True) == "declarative"


def test_gate_falls_to_imperative_only_with_positive_byod_evidence():
    # BYOD is never eligible for whole-device DDM push -> imperative.
    device = {"management_mode": "fully_managed", "ownership": "employee_owned"}
    assert declarative_path_for(device, supports_ddm=True) == "imperative"


def test_gate_returns_unknown_when_adapter_does_not_report_mode():
    # The OLD behaviour: missing field -> dropped to imperative everywhere.
    # Now it returns "unknown" so the caller decides; never silently imperative.
    assert declarative_path_for({"management_mode": None}, supports_ddm=True) == "unknown"
    # And a non-declarative adapter keeps the device in "unknown".
    assert declarative_path_for({"management_mode": "fully_managed"}, supports_ddm=False) == "unknown"


def test_gate_prefers_declarative_over_imperative_for_ddm_device():
    # Regression guard: given a DDM-capable adapter + eligible device, the gate
    # must NOT return imperative (the bug #88 fixed).
    device = {"management_mode": "mdm", "ownership": "company"}
    decision = declarative_path_for(device, supports_ddm=True)
    assert decision == "declarative"
    assert decision != "imperative"


def test_amapi_policy_gate_honours_android_ownership_vocabulary():
    # AMAPI/Intune vocabulary lives in the same enum; the gate already routes
    # it once an adapter sets supports_amapi_policy (left to #90).
    device = {"management_mode": "device_owner", "ownership": "company"}
    assert declarative_path_for(device, supports_amapi_policy=True) == "declarative"
    device_po = {"management_mode": "profile_owner", "ownership": "company"}
    assert declarative_path_for(device_po, supports_amapi_policy=True) == "declarative"
    assert "device_owner" in MANAGEMENT_MODES
    assert "profile_owner" in MANAGEMENT_MODES


def test_end_to_end_jamf_fetch_routes_declaratively_through_gate():
    raw = {"id": "55", "general": {
        "name": "Mac", "platform": "macOS", "managed": True, "supervised": True,
    }}
    dev = JamfAdapter(live=False)._normalize_fetch_device(raw)
    # The whole point of #88: the device Jamf reports now drives the decision.
    assert declarative_path_for(dev, supports_ddm=True) == "declarative"
