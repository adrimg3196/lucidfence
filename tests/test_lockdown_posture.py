"""Lockdown Mode como postura de readback (Apple DDM OS 27, WWDC 2026).

Regla de honestidad central: `lockdown_mode_off` es True SOLO cuando la UEM
reporta Lockdown Mode explícitamente OFF (`False`). Un valor `None`/ausente
(desconocido — el caso común hoy) NUNCA penaliza. Sin red, sin fixtures.
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

# Política de ejemplo del PR: fuera de geocerca + Lockdown Mode OFF.
_POLICY = Policy(
    id="lockdown-off-outside",
    name="Fuera de geocerca sin Lockdown Mode",
    description="Lockdown Mode desactivado",
    when=[{"field": "lockdown_mode", "op": "eq", "value": False}],
    actions=[{"action": "notify", "params": {}}],
)


def _matches(device: dict) -> bool:
    """¿Casa la política `lockdown_mode == false` contra este device dict?"""
    engine = RiskEngine()
    risk = engine.evaluate(device, device.get("fence_state", "unknown"), {})
    fired = engine.match_policies([_POLICY], risk, device, device.get("fence_state", "unknown"))
    return any(f["policy_id"] == "lockdown-off-outside" for f in fired)


def test_lockdown_off_signals_and_policy_matches():
    """(a) lockdown_mode=False -> lockdown_mode_off=True, la política casa y
    el motor añade la razón textual."""
    device = {"device_id": "d-off", "lockdown_mode": False, "fence_state": "outside"}
    posture = sig_device_posture(device, {})
    assert posture["lockdown_mode_off"] is True

    assert _matches(device) is True

    risk = RiskEngine().evaluate(device, "outside", {})
    assert "Lockdown Mode desactivado" in risk["reasons"]


def test_lockdown_unknown_never_penalizes_and_policy_skips():
    """(b) lockdown_mode=None -> lockdown_mode_off=False, la política NO casa
    (desconocido != OFF) y no aparece la razón."""
    device = {"device_id": "d-unk", "lockdown_mode": None, "fence_state": "outside"}
    posture = sig_device_posture(device, {})
    assert posture["lockdown_mode_off"] is False

    assert _matches(device) is False

    risk = RiskEngine().evaluate(device, "outside", {})
    assert "Lockdown Mode desactivado" not in risk["reasons"]

    # Ausencia total de la clave se comporta igual que None (desconocido).
    absent = {"device_id": "d-absent", "fence_state": "outside"}
    assert sig_device_posture(absent, {})["lockdown_mode_off"] is False
    assert _matches(absent) is False


def test_lockdown_on_is_not_off():
    """Lockdown Mode ON (True) tampoco es OFF: sin señal, sin penalización."""
    device = {"device_id": "d-on", "lockdown_mode": True, "fence_state": "outside"}
    assert sig_device_posture(device, {})["lockdown_mode_off"] is False
    assert _matches(device) is False


def test_lockdown_mode_roundtrips_report_to_device_dict():
    """(c) lockdown_mode viaja LocationReport -> device dict del engine.

    Reproduce las dos rutas reales de engine.run_once:
      * risk_device = dict(rep.__dict__)         (motor de riesgo)
      * DeviceState(lockdown_mode=rep.lockdown_mode).to_dict()  (políticas)
    y confirma que None se propaga como None (nunca fabricado)."""
    for value in (False, True, None):
        rep = LocationReport(
            device_id="d-rt", name="RT", platform="ios",
            lat=0.0, lng=0.0, lockdown_mode=value,
        )
        # Ruta del motor de riesgo: rep.__dict__ es el device dict.
        risk_device = dict(rep.__dict__)
        assert risk_device["lockdown_mode"] is value

        # Ruta de políticas: DeviceState -> to_dict().
        ds = DeviceState(
            device_id=rep.device_id, name=rep.name, platform=rep.platform,
            lockdown_mode=rep.lockdown_mode,
        )
        assert ds.to_dict()["lockdown_mode"] is value

    # Por defecto (sin reportar) es None: desconocido, no fabricado.
    assert LocationReport(device_id="x", name="x", platform="ios",
                          lat=0.0, lng=0.0).lockdown_mode is None
