"""Unit tests for the release-resilience helper scripts (t_9e6615ad).

Runs under the zero-dependency runner: python3 tests/run_tests.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

SCRIPTS = ROOT / "scripts"


def _load(name: str):
    path = SCRIPTS / name if name.endswith(".py") else SCRIPTS / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cloud_aliveness_classify_fresh_and_stale():
    mod = _load("cloud_state_aliveness")
    from datetime import datetime, timezone

    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)
    # fresco: 30 min de antigüedad, umbral 60
    fresh = {"generated_at": "2026-08-24T11:30:00Z"}
    state, _ = mod.classify(fresh, 60.0, now=now)
    assert state == "fresh", state
    # stale: 90 min
    stale = {"generated_at": "2026-08-24T10:30:00Z"}
    state, detail = mod.classify(stale, 60.0, now=now)
    assert state == "stale", state
    assert "90.0" in detail
    # sin generated_at
    state, detail = mod.classify({}, 60.0, now=now)
    assert state == "stale" and "generated_at" in detail


def test_move_changelog_unreleased_renames_and_keeps_unreleased_on_top():
    mod = _load("move_changelog_unreleased")
    text = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "- fix(ci): relax data-branch ruleset (#270)\n\n"
        "## [1.6.0] - 2026-08-18\n\n"
        "### Added\n\n- feat(enforcement): rollout seguro\n"
    )
    new_text, changed = mod.move(text, "1.7.0", date="2026-08-24")
    assert changed
    # primera sección sigue siendo [Unreleased]
    assert new_text.splitlines()[2].strip() == "## [Unreleased]", new_text.splitlines()[:4]
    assert "## [1.7.0] - 2026-08-24" in new_text
    # el bullet de Unreleased se movió bajo la versión
    assert "- fix(ci): relax data-branch ruleset (#270)" in new_text.split("## [1.7.0]")[1]
    # idempotente si ya existe
    _, changed2 = mod.move(new_text, "1.7.0", date="2026-08-24")
    assert changed2 is False


def test_parse_test_failures_splits_real_vs_quarantined():
    mod = _load("parse_test_failures")
    quarantine = {"test_web_bundle.py", "test_ssf_transmitter.py"}
    out = (
        "  PASS  test_foo.py::t1\n"
        "  FAIL  tests/test_web_bundle.py::t1: InvalidKeyError\n"
        "  FAIL  test_ssf_transmitter.py::t2: InvalidKeyError\n"
        "  FAIL  tests/test_engine.py::t3: AssertionError\n"
    )
    res = mod.classify(out, quarantine)
    assert set(res["quarantined"]) == {"test_ssf_transmitter.py", "test_web_bundle.py"}, res
    assert res["real"] == ["test_engine.py"], res
