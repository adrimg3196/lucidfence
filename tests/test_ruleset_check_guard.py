"""Regression tests for the GitHub ruleset required-check guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ruleset_check_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("ruleset_check_guard", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_matrix_expanded_check_matches_declared_job_name():
    """GitHub appends a matrix suffix already present in the job name."""
    guard = _load_guard()
    workflow = ".github/workflows/ci.yml"
    with (
        patch.object(guard, "list_workflow_files", return_value=[workflow]),
        patch.object(
            guard,
            "_workflow_contexts",
            return_value=("CI", {"python"}, {"Python tests (3.11)"}),
        ),
    ):
        assert (
            guard.find_workflow_for_context(
                "/unused", "Python tests (3.11) (3.11)"
            )
            == workflow
        )
