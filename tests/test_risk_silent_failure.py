"""Regression tests for issue #302 — risk eval failure must not masquerade as safe.

Two invariants covered here (origin: Codex review #301 / CEO-critical task
t_a6429f0f):

1. A crashed evaluator MUST NOT be presented as a healthy device. The old
   `except Exception: r = {risk_score: 0.0, severity: "low"}` masked a failure
   as "safe/low", indistinguishable from a real low-risk device — a violation of
   "lo desconocido jamas se presenta como senal buena". Now we emit an honest
   sentinel: score=None, level="unknown", verified=False, sorted to the bottom.

2. The headline score/severity PROJECTS the persisted verdict (the value the
   engine actually wrote during run_once and that fired actions), so the GET
   path no longer silently diverges from the actioning verdict after a shift
   change or config edit.
"""
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from lucidfence.core.product import _risk_from_engine, build_product  # noqa: E402


class _BoomRisk:
    """Risk evaluator that raises on every call — simulates a crash."""
    def evaluate(self, device, fence_state, ctx):
        raise RuntimeError("simulated evaluator crash")
    def match_policies(self, policies, risk, device, fence_state):
        return []


class _FakeEng:
    def __init__(self, risk, devices, policies=None):
        self.risk = risk
        self.policies = policies or []
        self._devices = devices
    def _ctx_hour(self):
        return 12
    def _ctx_shift_zones(self):
        return {}
    def _ctx_zone_risk(self):
        return {}


def test_evaluator_crash_is_unknown_not_low():
    """A crashed evaluator AND no persisted verdict yields score=None / level='unknown', never 0/'low'."""
    eng = _FakeEng(_BoomRisk(), [])
    devices = [{"device_id": "d1", "name": "Dev1", "platform": "android",
                "fence_state": "inside", "compliant": True,
                "risk_score": None, "risk_severity": None}]
    rows = _risk_from_engine(eng, devices)
    assert len(rows) == 1
    r = rows[0]
    assert r["score"] is None, f"score must be None on crash, got {r['score']}"
    assert r["level"] == "unknown", f"level must be 'unknown', got {r['level']}"
    assert r["verified"] is False, "crash must not be flagged verified"
    assert r["error"] == "risk_evaluation_failed"
    # An 'unknown' device must NOT be counted as high-risk.
    assert r["score"] is None or r["score"] < 70


def test_unknown_sorts_below_real_low():
    """'unknown' (crashed) must sort BELOW a real low-risk device, never masquerade as healthy."""
    eng = _FakeEng(_BoomRisk(), [])
    devices = [
        # real, explicitly healthy device (low risk, persisted)
        {"device_id": "ok", "name": "OK", "platform": "android",
         "fence_state": "inside", "compliant": True,
         "risk_score": 5.0, "risk_severity": "low"},
        # crashed evaluator
        {"device_id": "boom", "name": "Boom", "platform": "android",
         "fence_state": "inside", "compliant": True,
         "risk_score": None, "risk_severity": None},
    ]
    rows = _risk_from_engine(eng, devices)
    assert [r["device_id"] for r in rows] == ["ok", "boom"], \
        "unknown must sort to the bottom, below a real low-risk device"


def test_headline_projects_persisted_verdict_not_fresh_ctx():
    """GET headline uses persisted verdict, not a fresh recompute (defect 2)."""
    class _StubRisk:
        # Fresh recompute would return a DIFFERENT (higher) score. If the code
        # used the fresh recompute, headline would be 95/'critical'. The
        # persisted verdict is medium/40, so headline must stay 40/'medium'.
        def evaluate(self, device, fence_state, ctx):
            return {"risk_score": 95.0, "severity": "critical",
                    "reasons": ["fresh recompute says critical"],
                    "signals": {}}
        def match_policies(self, policies, risk, device, fence_state):
            return []

    eng = _FakeEng(_StubRisk(), [])
    devices = [{"device_id": "d1", "name": "Dev1", "platform": "android",
                "fence_state": "inside", "compliant": True,
                "risk_score": 40.0, "risk_severity": "medium"}]
    rows = _risk_from_engine(eng, devices)
    r = rows[0]
    assert r["score"] == 40.0, f"headline must project persisted 40.0, got {r['score']}"
    assert r["level"] == "medium", f"headline level must be 'medium', got {r['level']}"
    # But the explicable reasons still come from the fresh recompute (moat).
    assert any("fresh recompute" in f["label"] for f in r["factors"]), \
        "reasons should still be explicable from the recompute"


def test_build_product_risk_summary_handles_null_score():
    """build_product summary/insights must not crash and must not count null as high-risk."""
    eng = _FakeEng(_BoomRisk(), [])
    status = {
        "devices": [{"device_id": "boom", "name": "Boom", "platform": "android",
                     "fence_state": "inside", "compliant": True,
                     "risk_score": None, "risk_severity": None}],
        "interval_seconds": 900,
        "stats_history": [],
        "trails": {},
    }
    prod = build_product(status, eng)
    # No crash, summary consistent
    summary = prod["summary"]
    assert summary["high_risk_devices"] == 0, \
        "null score must NOT be counted as high-risk"
    top = prod["report"]["metrics"]["max_risk_score"]
    assert top == 0, f"max_risk_score must coerce null to 0, got {top}"
