"""Regression tests for the honest risk sentinel (#302-1).

`_risk_from_engine` must NOT mask an evaluation failure as a low-risk (score 0,
level "low") device — that is a false-green that hides outages/bugs behind a
green dashboard. A crash in `eng.risk.evaluate` must yield an explicit sentinel
row: score=None, level="unknown", populated reasons, verified=False, and it must
sort last (never compete with real signal).
"""

from lucidfence.core.product import _risk_from_engine


class _FakeEngine:
    """Minimal eng stub matching the attributes _risk_from_engine touches.

    `_risk_from_engine` reads `eng.risk.evaluate(...)` and `eng.policies`;
    `eng.risk` is exposed as a property returning self (which provides the
    evaluate/match_policies methods), mirroring the real Engine layout.
    """

    def __init__(self, evaluate_raises=None):
        self._evaluate_raises = evaluate_raises
        self.policies = []

    def _ctx_hour(self):
        return 12

    def _ctx_shift_zones(self):
        return {}

    def _ctx_zone_risk(self):
        return {}

    @property
    def risk(self):
        return self

    def evaluate(self, device, fence_state, ctx):
        if self._evaluate_raises is not None:
            # Raise only for the device id named in the exception's args list,
            # so a mixed fleet can have one real score and one sentinel.
            raise_target = getattr(self._evaluate_raises, "_raise_for", None)
            if raise_target is None or raise_target == device.get("device_id"):
                raise self._evaluate_raises
        return {"risk_score": 82.0, "severity": "high",
                "reasons": ["fuera de perímetro"], "signals": {"z": 1}}

    def match_policies(self, policies, r, device, fence_state):
        return []


def _make_eng(raises=None):
    eng = _FakeEngine(evaluate_raises=raises)
    # _risk_from_engine reads eng.risk.evaluate and eng.policies directly.
    return eng


def test_evaluate_failure_yields_unknown_sentinel_not_false_green():
    eng = _make_eng(raises=RuntimeError("engine exploded"))
    devices = [{"device_id": "d1", "name": "laptop", "platform": "macos",
                "fence_state": "unknown"}]
    rows = _risk_from_engine(eng, devices)
    assert len(rows) == 1
    r = rows[0]
    # Core invariant: score is None and level is "unknown" — NEVER 0/"low".
    assert r["score"] is None, f"sentinel score must be None, got {r['score']!r}"
    assert r["level"] == "unknown", f"sentinel level must be unknown, got {r['level']!r}"
    # Honest reasons live in `factors` (UI renders them), not a silent empty list.
    factor_labels = [f.get("label") for f in r.get("factors", [])]
    assert factor_labels, "sentinel must carry the failure reason as a factor"
    assert "engine exploded" in factor_labels[0]
    # Must not be reported as a verified (green) signal.
    assert r["verified"] is False


def test_evaluate_failure_sorts_last_and_does_not_crash_consumers():
    boom = ValueError("boom")
    boom._raise_for = "bad"  # only the "bad" device fails evaluation
    eng = _make_eng(raises=boom)
    devices = [
        {"device_id": "ok", "name": "good", "platform": "ios",
         "fence_state": "inside"},
        {"device_id": "bad", "name": "broken", "platform": "android",
         "fence_state": "outside"},
    ]
    rows = _risk_from_engine(eng, devices)
    # Both rows present; the failing one (unknown) must sort AFTER the real one.
    assert [x["device_id"] for x in rows] == ["ok", "bad"]
    assert rows[0]["score"] == 82.0
    assert rows[1]["score"] is None
    assert rows[1]["level"] == "unknown"


def test_successful_evaluation_still_produces_numeric_score():
    eng = _make_eng()
    devices = [{"device_id": "ok", "name": "good", "platform": "ios",
                "fence_state": "inside"}]
    rows = _risk_from_engine(eng, devices)
    assert rows[0]["score"] == 82.0
    assert rows[0]["level"] == "high"
    # A real score with reasons => verified True (green badge allowed).
    assert rows[0]["verified"] is True
