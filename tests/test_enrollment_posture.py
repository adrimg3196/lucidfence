"""Enrolment supervision como postura de readback (Apple DDM OS 27, WWDC 2026).

Regla de honestidad central: `unsupervised` es True SOLO cuando la UEM reporta
`supervised` explícitamente False. Un valor None/ausente (desconocido — el caso
común hoy) NUNCA penaliza. Sin red, sin fixtures.
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

_REASON = "dispositivo sin supervisión (enrolamiento personal)"

_POLICY = Policy(
    id="unsupervised-outside",
    name="Fuera de geocerca sin supervisión",
    description="Enrolamiento personal (no supervisado)",
    when=[
        {"field": "fence_state", "op": "eq", "value": "outside"},
        {"field": "supervised", "op": "eq", "value": False},
    ],
    actions=[{"action": "notify", "params": {}}],
)


def _matches(device: dict) -> bool:
    engine = RiskEngine()
    risk = engine.evaluate(device, device.get("fence_state", "unknown"), {})
    fired = engine.match_policies([_POLICY], risk, device, device.get("fence_state", "unknown"))
    return any(f["policy_id"] == "unsupervised-outside" for f in fired)


def test_unsupervised_signals_and_policy_matches():
    device = {"device_id": "d-uns", "supervised": False, "fence_state": "outside"}
    assert sig_device_posture(device, {})["unsupervised"] is True
    assert _matches(device) is True
    assert _REASON in RiskEngine().evaluate(device, "outside", {})["reasons"]


def test_unknown_never_penalizes_and_policy_skips():
    device = {"device_id": "d-unk", "supervised": None, "fence_state": "outside"}
    assert sig_device_posture(device, {})["unsupervised"] is False
    assert _matches(device) is False
    assert _REASON not in RiskEngine().evaluate(device, "outside", {})["reasons"]

    absent = {"device_id": "d-absent", "fence_state": "outside"}
    assert sig_device_posture(absent, {})["unsupervised"] is False
    assert _matches(absent) is False


def test_supervised_true_is_not_a_risk():
    device = {"device_id": "d-sup", "supervised": True, "fence_state": "outside"}
    assert sig_device_posture(device, {})["unsupervised"] is False
    assert _matches(device) is False
    assert _REASON not in RiskEngine().evaluate(device, "outside", {})["reasons"]


def test_supervised_roundtrips_report_to_device_dict():
    for value in (False, True, None):
        rep = LocationReport(
            device_id="d-rt", name="RT", platform="ios",
            lat=0.0, lng=0.0, supervised=value,
        )
        assert dict(rep.__dict__)["supervised"] is value  # ruta motor de riesgo
        ds = DeviceState(
            device_id=rep.device_id, name=rep.name, platform=rep.platform,
            supervised=rep.supervised,
        )
        assert ds.to_dict()["supervised"] is value  # ruta de políticas

    assert LocationReport(device_id="x", name="x", platform="ios",
                          lat=0.0, lng=0.0).supervised is None
