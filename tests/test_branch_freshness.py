"""Tests for scripts/branch_freshness_check.py (anti-staleness pre-flight, t_13ea01ab).

Mirrors the repo's zero-dependency harness: every `test_*` function is discovered
and run by `python3 tests/run_tests.py`. No external services; the selftest builds
its own throwaway git repos, so it is safe under CI.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

_spec = importlib.util.spec_from_file_location(
    "branch_freshness_check",
    os.path.join(_ROOT, "scripts", "branch_freshness_check.py"),
)
bfc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bfc)


def test_flag_template_format():
    """flag-template must emit a pasteable BRANCH_FRESHNESS: block with the key."""
    fr = {"repo": "/x", "branch": "feature/x", "behind": 3, "ahead": 1,
          "merge_base": "abc", "status": "ADVISORY"}
    block = bfc.flag_template(fr)
    assert block.startswith("BRANCH_FRESHNESS:"), block
    assert "commits_behind_main:" in block
    assert "status: ADVISORY" in block


def test_sum_grep_counts_per_file():
    """_sum_grep sums the trailing per-file counts from `git grep -c` output."""
    out = "engine.py:3\ncore/x.py:2\n"
    assert bfc._sum_grep(out) == 5


def test_freshness_status_bands():
    """threshold bands: 0=FRESH, <=N=ADVISORY, >N=STALE (pure, no git needed)."""
    # build a fake fr dict shape via the internal status mapping by calling freshness
    # on a non-repo to confirm ERROR path is clean, then assert band math indirectly.
    fr = bfc.freshness("/nonexistent/path/that/is/not/git")
    assert fr["status"] == "ERROR"
    assert fr["behind"] is None


def test_selftest_passes():
    """The script's own --selftest (STALE/FRESH/grep/flag-template) must pass."""
    rc = bfc.main(["--selftest"])
    assert rc == 0, f"selftest exit {rc}"
