"""Salud de hardware como postura de readback (Apple DDM OS 27, WWDC 2026).

Regla de honestidad central: `hardware_degraded` es True SOLO cuando algún
componente reporta degradación explícita (False, o un string reconocido:
"degraded"/"failed"/"error"). None/ausente/dict vacío/valores raros
(desconocido — el caso común hoy) NUNCA penalizan. Sin red, sin fixtures.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.location_source import LocationReport  # noqa: E402
from lucidfence.core.state_store import DeviceState  # noqa: E402
from lucidfence.core.policies import (  # noqa: E402
    Policy,
    RiskEngine,
    sig_device_posture,
)

_REASON_PREFIX = "salud de hardware degradada"

_POLICY = Policy(
    id="hw-degraded-outside",
    name="Fuera de geocerca con hardware degradado",
    description="Salud de hardware degradada (DDM OS 27)",
    when=[
        {"field": "fence_state", "op": "eq", "value": "outside"},
        {"field": "hardware_degraded", "op": "eq", "value": True},
    ],
    actions=[{"action": "notify", "params": {}}],
)


def _matches(device: dict) -> bool:
    engine = RiskEngine()
    risk = engine.evaluate(device, device.get("fence_state", "unknown"), {})
    fired = engine.match_policies([_POLICY], risk, device, device.get("fence_state", "unknown"))
    return any(f["policy_id"] == "hw-degraded-outside" for f in fired)


def _has_reason(device: dict) -> bool:
    reasons = RiskEngine().evaluate(device, "outside", {})["reasons"]
    return any(r.startswith(_REASON_PREFIX) for r in reasons)


def test_component_false_signals_and_policy_matches():
    device = {"device_id": "d-hw", "fence_state": "outside",
              "hardware_health": {"baseband": False, "camera": True}}
    posture = sig_device_posture(device, {})
    assert posture["hardware_degraded"] is True
    assert posture["hardware_degraded_components"] == ["baseband"]
    assert _has_reason(device) is True
    assert _matches(device) is True
    # La razón textual nombra el componente degradado.
    reasons = RiskEngine().evaluate(device, "outside", {})["reasons"]
    assert any("baseband" in r for r in reasons if r.startswith(_REASON_PREFIX))


def test_unknown_never_penalizes_and_policy_skips():
    for hh in (None, {}, {"nfc": "weird-status"}, {"uwb": 42}, {"camera": [1, 2]}):
        device = {"device_id": "d-unk", "fence_state": "outside", "hardware_health": hh}
        posture = sig_device_posture(device, {})
        assert posture["hardware_degraded"] is False
        assert posture["hardware_degraded_components"] == []
        assert _has_reason(device) is False
        assert _matches(device) is False

    absent = {"device_id": "d-absent", "fence_state": "outside"}
    assert sig_device_posture(absent, {})["hardware_degraded"] is False
    assert _matches(absent) is False


def test_all_healthy_is_not_a_risk():
    device = {"device_id": "d-ok", "fence_state": "outside",
              "hardware_health": {"baseband": True, "camera": "ok",
                                  "biometrics": "Healthy", "nfc": "NORMAL"}}
    posture = sig_device_posture(device, {})
    assert posture["hardware_degraded"] is False
    assert posture["hardware_degraded_components"] == []
    assert _has_reason(device) is False
    assert _matches(device) is False


def test_degraded_string_penalizes():
    for word in ("degraded", "Failed", "ERROR"):
        device = {"device_id": "d-str", "fence_state": "outside",
                  "hardware_health": {"biometrics": word}}
        posture = sig_device_posture(device, {})
        assert posture["hardware_degraded"] is True
        assert posture["hardware_degraded_components"] == ["biometrics"]
        assert _has_reason(device) is True
        assert _matches(device) is True


def test_degraded_score_matches_posture_weight():
    """Mismo peso (+10) que lockdown_mode_off / unsupervised."""
    base = {"device_id": "d-base", "fence_state": "outside"}
    degraded = {"device_id": "d-deg", "fence_state": "outside",
                "hardware_health": {"uwb": False}}
    rk = RiskEngine()
    delta = rk.evaluate(degraded, "outside", {})["risk_score"] - \
        rk.evaluate(base, "outside", {})["risk_score"]
    assert delta == 10


def test_hardware_health_roundtrips_report_to_device_dict():
    for value in ({"baseband": False}, {"camera": True, "nfc": "ok"}, None):
        rep = LocationReport(
            device_id="d-rt", name="RT", platform="ios",
            lat=0.0, lng=0.0, hardware_health=value,
        )
        assert dict(rep.__dict__)["hardware_health"] == value  # ruta motor de riesgo
        ds = DeviceState(
            device_id=rep.device_id, name=rep.name, platform=rep.platform,
            hardware_health=rep.hardware_health,
        )
        assert ds.to_dict()["hardware_health"] == value  # ruta de políticas

    # Por defecto (sin reportar) es None: desconocido, no fabricado.
    assert LocationReport(device_id="x", name="x", platform="ios",
                          lat=0.0, lng=0.0).hardware_health is None
