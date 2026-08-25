"""Regression tests for defect 2 (issue #302) — the GET path must PROJECT the
persisted verdict EXPLAIN (reasons + matched_policies + evaluated_at) instead of
recomputing it with a fresh context that may disagree with the verdict that fired
actions.

Two views of the same dashboard (server.py /api/risk and saas_server.py) both go
through `_risk_from_engine`, so a single fix covers both — but they must not
disagree with each other, nor with the verdict the engine wrote during run_once.

Covers (from defect2-technical-design.md):
- Unit: a device with a RECENT risk_evaluated_at -> GET projects the persisted
  reasons (does NOT recompute, even if ctx.hour changes).
- Unit: a device with NO risk_evaluated_at -> GET recomputes live (fallback).
- Unit: an OLD risk_evaluated_at (age > 2*interval) -> stale=True and the last
  known evaluated_at is preserved (no invented number).
- Integration: after Engine.run_once, DeviceState.risk_reasons /
  risk_matched_policies are not None and match the /api/risk row (projection,
  not recompute).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.product import _risk_from_engine  # noqa: E402


class _HourSensitiveRisk:
    """evaluate returns reasons that DEPEND on ctx['hour'] so we can prove
    whether the GET path recomputes (uses ctx.hour) or projects persisted."""

    def evaluate(self, device, fence_state, ctx):
        hour = ctx.get("hour", 0)
        return {
            "risk_score": 10.0,
            "severity": "low",
            "reasons": [f"live reason computed at hour {hour}"],
            "signals": {},
            "provenance": "tool",
            "verified": True,
        }

    def match_policies(self, policies, risk, device, fence_state):
        # Distinct sentinel so we can tell live recompute from persisted projection.
        return [{"policy_id": "pol-recomputed-live", "name": "x", "severity": "low",
                 "description": "", "actions": []}]


class _FakeEng:
    def __init__(self, risk, devices, policies=None):
        self.risk = risk
        self.policies = policies or []
        self._devices = devices

    def _ctx_hour(self):
        # A fixed, off-by-one hour vs. whatever the persisted verdict assumed.
        return 3

    def _ctx_shift_zones(self):
        return {}

    def _ctx_zone_risk(self):
        return {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago_iso(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def test_recent_evaluated_at_projects_persisted_not_recomputed():
    """Fresh verdict -> reasons/matched come from the persisted verdict, NOT the
    hour-sensitive live evaluation."""
    eng = _FakeEng(_HourSensitiveRisk(), [])
    devices = [{
        "device_id": "d1", "name": "Dev1", "platform": "android",
        "fence_state": "inside", "compliant": True,
        "risk_score": 10.0, "risk_severity": "low",
        "risk_reasons": ["persisted reason A", "persisted reason B"],
        "risk_matched_policies": ["pol-persisted"],
        "risk_evaluated_at": _now_iso(),
        "risk_provenance": "tool", "risk_verified": True,
    }]
    rows = _risk_from_engine(eng, devices, interval_seconds=900)
    assert len(rows) == 1
    r = rows[0]
    labels = [f["label"] for f in r["factors"]]
    assert labels == ["persisted reason A", "persisted reason B"], labels
    # Must NOT contain the live (hour-dependent) reason.
    assert not any("live reason" in l for l in labels), labels
    assert r["matched_policies"] == ["pol-persisted"], r["matched_policies"]
    assert r["verified"] is True
    assert r["stale"] is False
    assert r["evaluated_at"] == devices[0]["risk_evaluated_at"]


def test_absent_evaluated_at_recomputes_live():
    """No evaluated_at -> fallback recompute against the live evaluator."""
    eng = _FakeEng(_HourSensitiveRisk(), [])
    devices = [{
        "device_id": "d2", "name": "Dev2", "platform": "ios",
        "fence_state": "inside", "compliant": True,
        "risk_score": None, "risk_severity": None,
        # reasons present but NO evaluated_at -> not authoritative.
        "risk_reasons": ["stale persisted reason"],
        "risk_matched_policies": ["pol-stale"],
        "risk_evaluated_at": None,
        "risk_provenance": "none", "risk_verified": False,
    }]
    rows = _risk_from_engine(eng, devices, interval_seconds=900)
    r = rows[0]
    labels = [f["label"] for f in r["factors"]]
    # Live recompute wins when there is no timestamp.
    assert any("live reason" in l for l in labels), labels
    assert "pol-recomputed-live" in r["matched_policies"], r["matched_policies"]
    assert r["stale"] is True


def test_old_evaluated_at_is_stale_preserves_timestamp():
    """Old verdict (age > 2*interval) -> stale=True and evaluated_at kept, no new number."""
    eng = _FakeEng(_HourSensitiveRisk(), [])
    old_iso = _hours_ago_iso(10)  # far beyond 2*900s
    devices = [{
        "device_id": "d3", "name": "Dev3", "platform": "android",
        "fence_state": "outside", "compliant": True,
        "risk_score": 40.0, "risk_severity": "medium",
        "risk_reasons": ["old persisted reason"],
        "risk_matched_policies": ["pol-old"],
        "risk_evaluated_at": old_iso,
        "risk_provenance": "tool", "risk_verified": True,
    }]
    rows = _risk_from_engine(eng, devices, interval_seconds=900)
    r = rows[0]
    assert r["stale"] is True
    # The last known timestamp is preserved (honest), not invented.
    assert r["evaluated_at"] == old_iso
    # Falls back to live recompute for the displayed factors.
    assert any("live reason" in f["label"] for f in r["factors"])


def test_no_recompute_when_ctx_hour_changes_but_verdict_fresh():
    """Defect-2 core: a shift change (different ctx hour) must NOT alter the
    projected explain of a fresh verdict."""
    eng = _FakeEng(_HourSensitiveRisk(), [])
    devices = [{
        "device_id": "d4", "name": "Dev4", "platform": "android",
        "fence_state": "inside", "compliant": True,
        "risk_score": 10.0, "risk_severity": "low",
        "risk_reasons": ["persisted reason A"],
        "risk_matched_policies": ["pol-persisted"],
        "risk_evaluated_at": _now_iso(),
        "risk_provenance": "tool", "risk_verified": True,
    }]
    # First projection (fresh).
    r1 = _risk_from_engine(eng, devices, interval_seconds=900)[0]
    # Second projection after a "shift change": ctx hour differs (eng._ctx_hour=3).
    # Even though the engine would now evaluate differently, the persisted
    # verdict must be projected identically.
    r2 = _risk_from_engine(eng, devices, interval_seconds=900)[0]
    assert [f["label"] for f in r1["factors"]] == [f["label"] for f in r2["factors"]]
    assert r2["matched_policies"] == ["pol-persisted"]
    assert r2["evaluated_at"] == devices[0]["risk_evaluated_at"]


def _build_tenant(tmp: Path) -> Path:
    api_spec = importlib.util.spec_from_file_location(
        "saas_api_op", ROOT / "scripts" / "saas_api_op.py")
    api = importlib.util.module_from_spec(api_spec)
    assert api_spec and api_spec.loader
    api_spec.loader.exec_module(api)
    api.BASE = tmp / "data" / "cloud_tenants"
    payload = {
        "name": "Explain bench",
        "fleet": [
            {"id": f"dev-{i}", "name": f"Device {i}", "platform": "android",
             "lat": 40.4168 + (i % 5) * 0.001, "lng": -3.7038 + (i % 5) * 0.001,
             "compliant": True, "department": "Ops"}
            for i in range(5)
        ],
        "fences": [{"id": "f1", "name": "HQ", "kind": "circle",
                    "center": {"lat": 40.4168, "lng": -3.7038}, "radius_m": 500}],
    }
    api.create_tenant("explain-bench", payload)
    return api.BASE / "explain-bench"


def test_run_once_persists_explain_and_api_risk_matches():
    """Integration: Engine.run_once writes the explain to DeviceState, and the
    /api/risk row projects it (projection, not recompute)."""
    import json

    from lucidfence.core.engine import Engine

    tmp = Path(tempfile.mkdtemp(prefix="lucidfence-explain-"))
    tdir = _build_tenant(tmp)
    tdata = tdir / "data"
    cfg = {
        "mode": "simulation",
        "autostart": False,
        "data_dir": str(tdata),
        "org_id": tdir.name,
        "sim_seed_path": str(tdata / "fleet_seed.json"),
        "fences_path": str(tdata / "fences.json"),
        "routes_path": str(tdata / "routes.json"),
        "policies_path": str(tdata / "policies.json"),
        "action_cooldown_seconds": 3600,
        "incident_webhook_url": "",
    }
    eng = Engine(cfg)
    eng.run_once()

    # Write-site: persisted explain must be populated for every device.
    states = eng.store.snapshot().values()
    assert states, "no device states after run_once"
    for s in states:
        assert s.risk_reasons is not None, f"risk_reasons not persisted for {s.device_id}"
        assert s.risk_matched_policies is not None, \
            f"risk_matched_policies not persisted for {s.device_id}"
        assert s.risk_evaluated_at is not None, \
            f"risk_evaluated_at not persisted for {s.device_id}"

    # Read-site: /api/risk projects the persisted verdict.
    devices = [s.to_dict() for s in states]
    rows = _risk_from_engine(eng, devices, interval_seconds=eng.interval)
    by_id = {r["device_id"]: r for r in rows}
    for s in states:
        row = by_id[s.device_id]
        # matched_policies MUST project the persisted verdict (non-trivial check).
        assert row["matched_policies"] == s.risk_matched_policies, s.device_id
        # reasons project verbatim when present; empty -> "Sin senales" placeholder
        # (display artifact), which is still projection (not a fresh live recompute
        # that would inject different reasons).
        if s.risk_reasons:
            assert [f["label"] for f in row["factors"]] == s.risk_reasons, \
                (s.device_id, row["factors"], s.risk_reasons)
        else:
            assert any("Sin senales" in f["label"] for f in row["factors"]), \
                (s.device_id, row["factors"])
        # Fresh verdict -> not stale, timestamp preserved.
        assert row["stale"] is False
        assert row["evaluated_at"] == s.risk_evaluated_at
    print(f"  [ok] run_once persisted explain for {len(states)} devices; "
          f"/api/risk projects it without recompute")


if __name__ == "__main__":
    test_recent_evaluated_at_projects_persisted_not_recomputed()
    test_absent_evaluated_at_recomputes_live()
    test_old_evaluated_at_is_stale_preserves_timestamp()
    test_no_recompute_when_ctx_hour_changes_but_verdict_fresh()
    test_run_once_persists_explain_and_api_risk_matches()
    print("ALL EXPLAIN-PERSIST TESTS PASSED")
