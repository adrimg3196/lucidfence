"""Activation milestones (funnel demo→live) — TDD superpowers.

Quick-win #1 del análisis CEO 2026-07-27: instrumentación LOCAL del funnel de
activación, sin telemetría externa (local-first). build_product debe exponer
un bloque `activation` con hitos derivables del propio estado del engine.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lucidfence.core.product import build_product  # noqa: E402


def _status(**over):
    base = {
        "devices": [], "recent_events": [], "recent_actions": [],
        "fences": [], "stats": {}, "stats_history": [],
        "mode": "demo", "dry_run": True,
    }
    base.update(over)
    return base


def test_activation_block_present_and_shaped():
    p = build_product(_status())
    act = p.get("activation")
    assert isinstance(act, dict)
    for key in ("milestones", "score", "next_step"):
        assert key in act, f"falta {key}"
    ms = act["milestones"]
    for m in ("has_devices", "has_fences", "live_mode", "action_executed",
              "dry_run_off"):
        assert m in ms and isinstance(ms[m], bool)


def test_activation_empty_demo_scores_zero():
    act = build_product(_status())["activation"]
    assert act["score"] == 0
    assert act["next_step"]  # siempre sugiere el siguiente paso


def test_activation_full_live_scores_100():
    st = _status(
        devices=[{"id": "d1", "lat": 40.0, "lng": -3.0}],
        fences=[{"id": "f1"}],
        recent_actions=[{"action": "lock", "device_id": "d1"}],
        mode="live", dry_run=False,
    )
    act = build_product(st)["activation"]
    assert act["score"] == 100
    assert all(act["milestones"].values())


def test_activation_partial_score_monotonic():
    st = _status(devices=[{"id": "d1"}], fences=[{"id": "f1"}])
    act = build_product(st)["activation"]
    assert 0 < act["score"] < 100
