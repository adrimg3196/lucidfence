"""Tests del simulador what-if de políticas (P0.1) — el plan antes del apply."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.fences import Fence
from lucidfence.core.policy_replay import load_trail_points, replay_policy

# Trail sintético: dev-a sale de la geocerca dos veces; dev-b siempre dentro.
TRAIL = [
    {"device_id": "dev-a", "lat": 40.42, "lng": -3.70, "fence_state": "inside", "ts": "2026-08-10T09:00:00Z"},
    {"device_id": "dev-a", "lat": 40.90, "lng": -3.70, "fence_state": "outside", "ts": "2026-08-10T10:00:00Z"},
    {"device_id": "dev-b", "lat": 40.42, "lng": -3.71, "fence_state": "inside", "ts": "2026-08-10T10:05:00Z"},
    {"device_id": "dev-a", "lat": 40.42, "lng": -3.70, "fence_state": "inside", "ts": "2026-08-10T11:00:00Z"},
    {"device_id": "dev-a", "lat": 41.00, "lng": -3.70, "fence_state": "outside", "ts": "2026-08-10T23:30:00Z"},
]

OUTSIDE_LOCK_POLICY = {
    "id": "pol-lock-outside",
    "name": "Lock al salir de geocerca",
    "when": [{"field": "fence_state", "op": "eq", "value": "outside"}],
    "actions": [{"action": "lock", "params": {}}],
    "severity": "high",
}


def test_replay_counts_fires_and_never_executes() -> None:
    result = replay_policy(OUTSIDE_LOCK_POLICY, TRAIL)
    assert result["dry_run"] is True
    assert result["points_evaluated"] == 5
    assert result["fires_total"] == 2 and result["devices_affected"] == 1
    assert result["fires_by_device"] == {"dev-a": 2}
    assert result["actions_that_would_run"] == {"lock": 2}
    assert result["destructive_actions"] == ["lock"]
    assert result["period"] == {"from": "2026-08-10T09:00:00Z", "to": "2026-08-10T23:30:00Z"}
    # Cada disparo de ejemplo lleva su explicación (evidence gate).
    for fire in result["sample_fires"]:
        assert fire["device_id"] == "dev-a" and fire["reasons"]


def test_replay_spatial_only_policy_is_exact() -> None:
    result = replay_policy(OUTSIDE_LOCK_POLICY, TRAIL)
    assert result["approximation"]["exact"] is True


def test_replay_flags_non_spatial_conditions_as_approximation() -> None:
    policy = {
        "id": "p", "name": "compuesta",
        "when": [
            {"field": "fence_state", "op": "eq", "value": "outside"},
            {"field": "signal:device_health.compliant", "op": "eq", "value": False},
        ],
        "actions": [{"action": "notify", "params": {}}],
    }
    result = replay_policy(policy, TRAIL, device_states={"dev-a": {"compliant": False}})
    assert result["approximation"]["exact"] is False
    assert "signal:device_health.compliant" in result["approximation"]["non_spatial_conditions"]
    # dev-a no conforme y fuera → dispara en sus 2 salidas.
    assert result["fires_total"] == 2


def test_replay_time_of_day_uses_trail_timestamp() -> None:
    # Solo dispara fuera de horario: de las 2 salidas de dev-a, únicamente la
    # de las 23:30 cuenta — la hora sale del timestamp del trail, no de ahora.
    policy = {
        "id": "p-night", "name": "salida nocturna",
        "when": [
            {"field": "fence_state", "op": "eq", "value": "outside"},
            {"field": "signal:time_of_day.off_hours", "op": "eq", "value": True},
        ],
        "actions": [{"action": "notify", "params": {}}],
    }
    result = replay_policy(policy, TRAIL)
    assert result["fires_total"] == 1
    assert result["sample_fires"][0]["ts"] == "2026-08-10T23:30:00Z"


def test_replay_recompute_fences_what_if() -> None:
    # Geocerca hipotética gigante que cubre todos los puntos: al recalcular,
    # nada queda "outside" y la policy no dispara ni una vez.
    big_fence = Fence.from_raw({"id": "todo-madrid", "name": "Todo", "type": "circle",
                                "center": {"lat": 40.6, "lng": -3.70}, "radius_m": 200_000})
    result = replay_policy(OUTSIDE_LOCK_POLICY, TRAIL, fences=[big_fence])
    assert result["fence_state_source"] == "recomputed"
    assert result["fires_total"] == 0


def test_replay_disabled_candidate_still_evaluates() -> None:
    policy = dict(OUTSIDE_LOCK_POLICY, enabled=False)
    assert replay_policy(policy, TRAIL)["fires_total"] == 2


def test_load_trail_points_skips_corrupt_lines_and_limits() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for p in TRAIL:
            f.write(json.dumps(p) + "\n")
        f.write("{corrupto\n")
        f.write(json.dumps({"device_id": "dev-c", "lat": None, "lng": 1, "ts": "x"}) + "\n")
        path = f.name
    try:
        points = load_trail_points(path)
        assert len(points) == 5  # corrupta y sin lat fuera
        assert load_trail_points(path, limit=2) == points[-2:]
        assert load_trail_points("/no/existe.jsonl") == []
    finally:
        os.unlink(path)
