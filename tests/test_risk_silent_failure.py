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


if __name__ == "__main__":
    test_crashed_evaluator_is_not_false_green()
    test_unknown_sorts_last_not_first()
    print("OK: sentinel regression tests pass")
