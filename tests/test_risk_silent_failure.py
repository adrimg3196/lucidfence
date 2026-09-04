"""Regression test for #302 Defect 1: a crashed risk evaluator must NEVER
appear as risk_score:0 / severity:low (a false-green identical to a healthy
device). The repo's honesty invariant: lo desconocido jamas se presenta como
senal buena. A crash must surface as an honest sentinel (score=None,
level="unknown") that travels without breaking consumers.

Assignee: empresa-ceo (verification only; fix lives in lucidfence/core/product.py).
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _product_module():
    return _load(ROOT / "lucidfence" / "core" / "product.py")


class _FailingRisk:
    def evaluate(self, device, fence_state, ctx):
        raise RuntimeError("boom: signal provider blew up")

    def match_policies(self, policies, risk, device, fence_state):
        return []


class _FakeEngine:
    policies = []

    def __init__(self):
        self.risk = _FailingRisk()

    def _ctx_hour(self):
        return 12

    def _ctx_shift_zones(self):
        return {}

    def _ctx_zone_risk(self):
        return {}


def test_crashed_evaluator_is_not_false_green():
    """A device whose evaluator raises must be 'unknown', never 0/low."""
    product = _product_module()
    eng = _FakeEngine()
    devices = [{"device_id": "d1", "name": "X", "fence_state": "inside"}]
    rows = product._risk_from_engine(eng, devices)
    assert len(rows) == 1, "must still return one row per device"
    row = rows[0]
    assert row["score"] is None, "crashed evaluator must NOT yield score 0"
    assert row["level"] == "unknown", "crashed evaluator must NOT yield low/healthy"
    assert row["eval_error"] == "RuntimeError", "error type should travel as telemetry"
    factor_labels = [f.get("label", "") for f in (row["factors"] or [])]
    assert any("evaluación fallida" in label for label in factor_labels), \
        "reason must explain the failure, not hide it"


def test_unknown_sorts_last_not_first():
    """Unknown (None) must rank below a real 0-score device in the summary."""
    product = _product_module()

    class _MixedRisk:
        def __init__(self, value):
            self._value = value

        def evaluate(self, device, fence_state, ctx):
            if self._value is None:
                raise ValueError("nope")
            return {"risk_score": self._value, "severity": "low",
                    "reasons": ["x"], "signals": {}, "verified": True,
                    "provenance": "tool"}

        def match_policies(self, policies, risk, device, fence_state):
            return []

    class _E:
        policies = []
        def __init__(self, v): self.risk = _MixedRisk(v)
        def _ctx_hour(self): return 12
        def _ctx_shift_zones(self): return {}
        def _ctx_zone_risk(self): return {}

    devices = [
        {"device_id": "ok0", "name": "A", "fence_state": "inside"},
        {"device_id": "crash", "name": "B", "fence_state": "inside"},
    ]
    rows = product._risk_from_engine(_E(0.0), [devices[0]])
    rows += product._risk_from_engine(_E(None), [devices[1]])
    # reverse=True sort: real 0.0 > -1.0 sentinel, so the crashed one is last.
    assert rows[-1]["device_id"] == "crash"
    assert rows[-1]["score"] is None


def _now_iso(seconds_ago: float = 0.0) -> str:
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def test_headline_projects_persisted_verdict_not_fresh_ctx():
    """GET headline uses the persisted verdict, NOT a fresh recompute (defect 2).

    A persisted verdict (medium/40, evaluated moments ago) must stay 40/'medium'
    even though the live evaluator would compute 80/'high' for a fresh context.
    The GET path projects the actioning verdict so the dashboard never silently
    disagrees with the value that fired automation.
    """
    product = _product_module()

    class _HighRisk:
        def evaluate(self, device, fence_state, ctx):
            return {"risk_score": 80.0, "severity": "high",
                    "reasons": ["live-recompute"], "signals": {},
                    "verified": True, "provenance": "tool"}
        def match_policies(self, policies, risk, device, fence_state):
            return []

    class _E:
        policies = []
        def __init__(self): self.risk = _HighRisk()
        def _ctx_hour(self): return 3   # a DIFFERENT hour -> fresh ctx would differ
        def _ctx_shift_zones(self): return {}
        def _ctx_zone_risk(self): return {}

    # Persisted verdict is medium/40, evaluated 5s ago (well within the window).
    devices = [{
        "device_id": "d1", "name": "X", "fence_state": "inside",
        "risk_score": 40.0, "risk_severity": "medium",
        "risk_reasons": ["persisted-reason"], "risk_matched_policies": ["p1"],
        "risk_evaluated_at": _now_iso(5), "risk_provenance": "tool",
        "risk_verified": True,
    }]
    rows = product._risk_from_engine(_E(), devices, interval_seconds=900)
    row = rows[0]
    # Headline must project the persisted 40/medium, NOT the fresh 80/high.
    assert row["score"] == 40.0, "headline must project persisted verdict, not fresh ctx"
    assert row["level"] == "medium"
    # EXPLAIN must also project the persisted reasons/matched, not live recompute.
    factor_labels = [f.get("label") for f in (row["factors"] or [])]
    assert "persisted-reason" in factor_labels, "explain must project persisted reasons"
    # matched_policies is also projected from the persisted verdict (fresh ctx).
    assert row["matched_policies"] == ["p1"]
    assert row["stale"] is False, "fresh persisted verdict must not be flagged stale"
    assert row["evaluated_at"] == devices[0]["risk_evaluated_at"]


def test_stale_verdict_flags_stale_not_blank():
    """When the persisted verdict is old, GET keeps the projected headline but
    flags stale=True and falls back to a live EXPLAIN (defect 2). It never
    invents a headline from a fresh context nor goes blank."""
    product = _product_module()

    class _LowRisk:
        def evaluate(self, device, fence_state, ctx):
            return {"risk_score": 10.0, "severity": "low",
                    "reasons": ["live"], "signals": {},
                    "verified": True, "provenance": "tool"}
        def match_policies(self, policies, risk, device, fence_state):
            return []

    class _E:
        policies = []
        def __init__(self): self.risk = _LowRisk()
        def _ctx_hour(self): return 12
        def _ctx_shift_zones(self): return {}
        def _ctx_zone_risk(self): return {}

    # Old persisted verdict (beyond 2x interval) -> headline kept, explain live + stale.
    devices = [{
        "device_id": "d1", "name": "X", "fence_state": "inside",
        "risk_score": 40.0, "risk_severity": "medium",
        "risk_reasons": ["stale-reason"], "risk_matched_policies": ["p1"],
        "risk_evaluated_at": _now_iso(3600),  # 1h ago, interval 900*2=1800s window
        "risk_provenance": "tool", "risk_verified": True,
    }]
    rows = product._risk_from_engine(_E(), devices, interval_seconds=900)
    row = rows[0]
    # Headline still projects the persisted verdict (never a fresh-context number).
    assert row["score"] == 40.0, "stale must keep projected headline, not live 10"
    assert row["level"] == "medium"
    assert row["stale"] is True, "stale persisted verdict must be flagged stale"
    factor_labels = [f.get("label") for f in (row["factors"] or [])]
    assert "live" in factor_labels, "stale recompute must use live explain"


if __name__ == "__main__":
    test_crashed_evaluator_is_not_false_green()
    test_unknown_sorts_last_not_first()
    test_headline_projects_persisted_verdict_not_fresh_ctx()
    test_stale_verdict_flags_stale_not_blank()
    print("OK: sentinel + verdict-projection regression tests pass")
