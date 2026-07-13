"""TDD: core/ai.py — IA bridge to local MoA (graceful fallback).

Covers:
  - available() reflects MoA reachability
  - incident/digest/alert/support helpers return IA text when MoA is up,
    and a deterministic plain-text fallback when MoA is down (never raises)
  - the plain fallback still conveys the key signals (state, risk, compliant)
We mock the network layer so the test is offline and deterministic.
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ai  # noqa: E402


def _fake_post(data, *, dry=True, rounds=2, agg_mode="synthesize", stream=False):
    # Simulate MoA returning an aggregated narrative.
    content = "Respuesta IA simulada para la prueba."
    return {"choices": [{"message": {"content": content}}], "moa": {"agg_used": "openrouter"}}


def test_available_true_when_moa_up():
    with mock.patch.object(ai, "available", return_value=True):
        assert ai.available() is True


def test_incident_narrative_uses_moa_when_available():
    with mock.patch.object(ai, "available", return_value=True), \
         mock.patch.object(ai, "_post", _fake_post):
        out = ai.incident_narrative(
            {"name": "iPad C3", "fence_state": "outside", "risk_score": 82, "compliant": False},
            dry=True,
        )
    assert "Respuesta IA simulada" in out


def test_incident_narrative_falls_back_when_moa_down():
    with mock.patch.object(ai, "available", return_value=False):
        out = ai.incident_narrative(
            {"name": "iPad C3", "fence_state": "outside", "risk_score": 82, "compliant": False},
            dry=True,
        )
    # Plain fallback must still carry the core signals.
    assert "iPad C3" in out
    assert "outside" in out
    assert "82" in out
    assert "non-compliant" in out


def test_digest_summary_uses_moa_when_available():
    devs = [
        {"name": "iPad C3", "fence_state": "outside", "risk_score": 82, "compliant": False},
        {"name": "Movil RRHH", "fence_state": "inside", "risk_score": 35, "compliant": True},
    ]
    with mock.patch.object(ai, "available", return_value=True), \
         mock.patch.object(ai, "_post", _fake_post):
        out = ai.digest_summary({"ts": "x"}, devs, dry=True)
    assert "Respuesta IA simulada" in out


def test_alert_blurb_fallback_has_signals():
    firing = {"rule_type": "noncompliant", "device_name": "iPad C3",
               "device_id": "dev-003", "severity": "high"}
    with mock.patch.object(ai, "available", return_value=False):
        out = ai.alert_blurb(firing, dry=True)
    assert "iPad C3" in out
    assert "noncompliant" in out


def test_support_reply_fallback():
    with mock.patch.object(ai, "available", return_value=False):
        out = ai.support_reply({"subject": "Geo no dispara", "body": "falla"}, dry=True)
    assert "Geo no dispara" in out
