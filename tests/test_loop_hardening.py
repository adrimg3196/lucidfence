from __future__ import annotations

import json
import tempfile
from pathlib import Path

import loop_improve


def _roadmap(features):
    return {"plan": {"phases": [{"id": "Q3-2026", "features": features}]}}


def test_loop_prioritization_honors_dependencies_impact_and_effort():
    data = _roadmap([
        {"id": "A", "status": "planned", "impact": "p0_must", "effort": "small", "dependencies": ["B"]},
        {"id": "B", "status": "planned", "impact": "p1_should", "effort": "small", "dependencies": []},
        {"id": "C", "status": "planned", "impact": "p2_nice", "effort": "small", "dependencies": []},
    ])
    first = loop_improve._next_feature(data)
    assert first is not None and first["id"] == "B"
    data["plan"]["phases"][0]["features"][1]["status"] = "done"
    second = loop_improve._next_feature(data)
    assert second is not None and second["id"] == "A"


def test_loop_evidence_gate_does_not_equate_green_suite_with_implementation():
    assert loop_improve._feature_evidence_complete({"subtasks": [{"status": "pending"}]}) is False
    assert loop_improve._feature_evidence_complete({"subtasks": [{"status": "done"}]}) is True
    assert loop_improve._feature_evidence_complete({"subtasks": []}) is False


def test_loop_metrics_are_bounded_and_secret_free():
    with tempfile.TemporaryDirectory() as td:
        old = loop_improve._HISTORY
        loop_improve._HISTORY = Path(td) / "history.jsonl"
        try:
            loop_improve._HISTORY.write_text("\n".join([
                json.dumps({"score": 9, "providers": ["local"]}),
                json.dumps({"score": 5, "providers": ["groq"]}),
            ]) + "\n")
            metrics = loop_improve.loop_metrics()
        finally:
            loop_improve._HISTORY = old
    assert metrics["iterations"] == 2
    assert metrics["average_score"] == 7
    assert metrics["below_threshold"] == 1
    assert metrics["providers"] == ["groq", "local"]
