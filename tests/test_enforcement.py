"""Rollout de enforcement para pilotos reales: observe -> enforce -> wipe.

Un admin evaluando el producto con su tenant real necesita garantías duras:
en observe NADA sale al UEM; en enforce solo salen las acciones listadas en
`enforcement.live_actions`; y `wipe` (la única irreversible) exige además
`allow_wipe: true`, opcionalmente acotado por `wipe_allowlist`. Un falso
positivo de GPS jamás debe poder borrar un dispositivo por defecto.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.adapters import VALID_ACTIONS  # noqa: E402
from lucidfence.core.adapters.fleet import FleetAdapter  # noqa: E402
from lucidfence.core.adapters.intune import IntuneAdapter  # noqa: E402
from lucidfence.core.adapters.jamf import JamfAdapter  # noqa: E402
from lucidfence.core.state_store import DeviceState  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


class _RecordingAdapter:
    """Captura (action, dry_run) de cada execute sin tocar red."""
    name = "recording"

    def __init__(self):
        self.calls = []

    def execute(self, device, action, params, dry_run=False):
        self.calls.append((action, dry_run))
        return {"ok": True, "adapter": self.name, "action": action,
                "device_id": getattr(device, "device_id", ""), "dry_run": dry_run}


def _dev(device_id="dev-a"):
    return DeviceState(device_id=device_id, name="Test", platform="ios")


def _engine(enforcement=None, **kw):
    extra = {"enforcement": enforcement} if enforcement is not None else None
    eng = make_temp_engine(cooldown_seconds=0, extra_config=extra, **kw)
    rec = _RecordingAdapter()
    eng.adapter = rec
    eng.orchestrator = None
    return eng, rec


def test_default_is_observe():
    eng, _ = _engine()
    assert eng.dry_run is True
    st = eng.enforcement_status()
    assert st["mode"] == "observe"
    assert st["allow_wipe"] is False


def test_mode_observe_wins_over_legacy_dry_run_false():
    eng, _ = _engine(enforcement={"mode": "observe"})
    eng2 = make_temp_engine(cooldown_seconds=0,
                            extra_config={"dry_run": False,
                                          "enforcement": {"mode": "observe"}})
    assert eng.dry_run is True
    assert eng2.dry_run is True


def test_observe_never_calls_live_even_for_wipe():
    eng, rec = _engine()  # default: observe
    res = eng.run_command(_dev(), "wipe", {})
    assert res.get("dry_run") is True
    assert not res.get("blocked")
    assert rec.calls == [("wipe", True)]


def test_enforce_live_actions_gates_per_action():
    eng, rec = _engine(enforcement={"mode": "enforce", "live_actions": ["message"]})
    assert eng.dry_run is False
    eng.run_command(_dev(), "message", {"text": "hola"})
    eng.run_command(_dev(), "lock", {})
    # message sale en vivo; lock (no listado) queda dry-run.
    assert ("message", False) in rec.calls
    assert ("lock", True) in rec.calls


def test_wipe_blocked_in_enforce_without_allow_wipe():
    eng, rec = _engine(enforcement={"mode": "enforce", "live_actions": ["wipe"]})
    res = eng.run_command(_dev(), "wipe", {})
    assert res["ok"] is False
    assert res["blocked"] is True
    assert res["error_type"] == "wipe_not_allowed"
    # El adapter jamás llega a ver el wipe bloqueado.
    assert rec.calls == []


def test_wipe_allowlist_scopes_the_blast_radius():
    enf = {"mode": "enforce", "live_actions": ["wipe"],
           "allow_wipe": True, "wipe_allowlist": ["dev-allowed"]}
    eng, rec = _engine(enforcement=enf)
    blocked = eng.run_command(_dev("dev-other"), "wipe", {})
    assert blocked["ok"] is False and blocked["error_type"] == "wipe_not_allowed"
    allowed = eng.run_command(_dev("dev-allowed"), "wipe", {})
    assert allowed["ok"] is True
    assert rec.calls == [("wipe", False)]


def test_enforcement_status_in_engine_status():
    eng, _ = _engine(enforcement={"mode": "enforce", "live_actions": ["lock"],
                                  "allow_wipe": True})
    st = eng.status()["enforcement"]
    assert st["mode"] == "enforce"
    assert st["live_actions"] == ["lock"]
    assert st["allow_wipe"] is True
    # Sin live_actions la política legacy es "todas".
    eng2, _ = _engine(enforcement={"mode": "enforce"})
    assert eng2.status()["enforcement"]["live_actions"] == "all"


# ---- set_compliance: la remediación de menor riesgo ------------------------

def test_set_compliance_is_a_valid_action():
    assert "set_compliance" in VALID_ACTIONS


def test_set_compliance_reaches_adapter_via_run_command():
    eng, rec = _engine(enforcement={"mode": "enforce",
                                    "live_actions": ["set_compliance"]})
    res = eng.run_command(_dev(), "set_compliance", {"compliant": False})
    assert res["ok"] is True
    assert rec.calls == [("set_compliance", False)]


def test_intune_mock_accepts_set_compliance():
    res = IntuneAdapter().execute({"device_id": "d1"}, "set_compliance",
                                  {"compliant": False}, dry_run=False)
    assert res["ok"] is True
    assert res.get("mock") is True


def test_jamf_degrades_set_compliance_with_guidance():
    res = JamfAdapter().execute({"device_id": "d1"}, "set_compliance", {})
    assert res["ok"] is False
    assert res["error_type"] == "unsupported_action"
    assert "compliance partner" in res["error"]


def test_fleet_degrades_set_compliance_with_guidance():
    res = FleetAdapter().execute({"device_id": "d1"}, "set_compliance", {})
    assert res["ok"] is False
    assert res["error_type"] == "unsupported_action"
    assert "Entra" in res["error"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
