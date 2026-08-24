"""Offline contract tests for the scheduled-workflow watchdog."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.cron_watchdog import evaluate_workflow


def _run(
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    run_id: int = 100,
    head_branch: str = "main",
    event: str = "schedule",
) -> dict[str, object]:
    return {
        "status": status,
        "conclusion": conclusion,
        "id": run_id,
        "created_at": "2026-08-24T08:00:00Z",
        "head_branch": head_branch,
        "event": event,
    }


def test_closes_existing_alert_only_after_completed_success() -> None:
    decision = evaluate_workflow([_run()], existing_issues=[42])

    assert decision.action == "close"
    assert decision.reason == "latest_run_recovered"
    assert decision.consecutive_failures == 0


def test_skips_when_latest_run_is_queued_or_in_progress() -> None:
    for status in ("queued", "in_progress"):
        decision = evaluate_workflow(
            [
                _run(status=status, conclusion=None, run_id=102),
                _run(conclusion="failure", run_id=101),
                _run(conclusion="failure", run_id=100),
            ],
            existing_issues=[42],
        )

        assert decision.action == "skip"
        assert decision.reason == f"latest_run_{status}"
        assert decision.latest_run_id == 102


def test_failure_alert_is_idempotent_when_issue_already_exists() -> None:
    failures = [
        _run(conclusion="failure", run_id=102),
        _run(conclusion="timed_out", run_id=101),
        _run(conclusion="success", run_id=100),
    ]

    first = evaluate_workflow(failures)
    repeated = evaluate_workflow(failures, existing_issues=[42])

    assert first.action == "open"
    assert repeated.action == "keep"
    assert repeated.reason == "alert_already_open"
    assert first.consecutive_failures == repeated.consecutive_failures == 2


def test_does_not_close_alert_until_a_completed_success_exists() -> None:
    one_failure = evaluate_workflow(
        [_run(conclusion="failure")],
        existing_issues=[42],
    )
    no_history = evaluate_workflow([], existing_issues=[42])

    assert one_failure.action == "keep"
    assert one_failure.reason == "failure_below_threshold"
    assert no_history.action == "skip"
    assert no_history.reason == "no_runs"


def test_ignores_non_health_events_and_non_default_branches() -> None:
    runs = [
        _run(conclusion="failure", run_id=104, event="pull_request"),
        _run(conclusion="failure", run_id=103, head_branch="feature/demo"),
        _run(conclusion="success", run_id=102, event="workflow_dispatch"),
    ]

    decision = evaluate_workflow(runs, existing_issues=[42], default_branch="main")

    assert decision.action == "close"
    assert decision.latest_run_id == 102


def test_reconciles_all_duplicate_issues_deterministically() -> None:
    failures = [
        _run(conclusion="failure", run_id=102),
        _run(conclusion="failure", run_id=101),
    ]

    failing = evaluate_workflow(failures, existing_issues=[44, 42, 43, 42])
    recovered = evaluate_workflow([_run()], existing_issues=[44, 42, 43, 42])

    assert failing.action == "reconcile"
    assert failing.primary_issue == 42
    assert failing.issues_to_close == (43, 44)
    assert recovered.action == "close"
    assert recovered.issues_to_close == (42, 43, 44)


def test_unknown_completed_conclusion_is_indeterminate() -> None:
    decision = evaluate_workflow(
        [_run(conclusion="future_github_state")],
        existing_issues=[42],
    )

    assert decision.action == "skip"
    assert decision.reason == "latest_conclusion_unknown"


def test_lookback_applies_after_branch_and_event_filtering() -> None:
    failures = [
        _run(conclusion="failure", run_id=103),
        _run(conclusion="failure", run_id=102),
        _run(conclusion="failure", run_id=101),
    ]

    decision = evaluate_workflow(failures, min_failures=3, lookback=2)

    assert decision.action == "keep"
    assert decision.consecutive_failures == 2


def test_workflow_has_idempotent_label_and_query_guards() -> None:
    workflow = (ROOT / ".github/workflows/cron-watchdog.yml").read_text(
        encoding="utf-8"
    )

    assert 'gh_retry label create "$LABEL"' in workflow
    assert "--force" in workflow
    assert 'jq -c --arg wf "$wf"' in workflow
    assert "--jq --arg" not in workflow
    assert '"loop-audit"' not in workflow
    assert "source scripts/gh_retry.sh" in workflow
    assert "gh_retry --reconcile" in workflow
    assert "$(gh api" not in workflow
    assert "if ! gh api" not in workflow
    workflow_commands = [
        line.strip()
        for line in workflow.splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert not any(
        line.startswith(("gh api ", "gh label ")) for line in workflow_commands
    )


def _run_fake_gh(
    *,
    status: int,
    succeed_at: int,
    reconcile_result: int | None = None,
) -> tuple[subprocess.CompletedProcess[str], int]:
    with tempfile.TemporaryDirectory(prefix="lucidfence-gh-retry-") as tmp:
        temp_dir = Path(tmp)
        state_file = temp_dir / "attempts"
        fake_gh = temp_dir / "gh"
        fake_gh.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
count=0
if [[ -f "$FAKE_GH_STATE" ]]; then
  read -r count < "$FAKE_GH_STATE"
fi
count=$((count + 1))
printf '%s\n' "$count" > "$FAKE_GH_STATE"
if ((count < FAKE_GH_SUCCEED_AT)); then
  printf 'gh: fake failure (HTTP %s)\n' "$FAKE_GH_STATUS" >&2
  exit 1
fi
printf '{"ok":true}\n'
""",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        env = os.environ.copy()
        env.update(
            {
                "FAKE_GH_STATE": str(state_file),
                "FAKE_GH_STATUS": str(status),
                "FAKE_GH_SUCCEED_AT": str(succeed_at),
                "GH_RETRY_MAX_ATTEMPTS": "3",
                "GH_RETRY_BASE_DELAY": "0",
                "PATH": f"{temp_dir}{os.pathsep}{env['PATH']}",
            }
        )
        command = "source scripts/gh_retry.sh; gh_retry api repos/acme/demo"
        if reconcile_result is not None:
            command = (
                "source scripts/gh_retry.sh; "
                f"effect_exists() {{ return {reconcile_result}; }}; "
                "gh_retry --reconcile effect_exists api repos/acme/demo"
            )
        result = subprocess.run(
            [
                "bash",
                "-c",
                command,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        attempts = int(state_file.read_text(encoding="utf-8")) if state_file.exists() else 0
    return result, attempts


def test_gh_retry_recovers_from_transient_failure() -> None:
    result, attempts = _run_fake_gh(status=503, succeed_at=3)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}
    assert attempts == 3


def test_gh_retry_exhausts_and_fails_closed() -> None:
    result, attempts = _run_fake_gh(status=503, succeed_at=99)

    assert result.returncode != 0
    assert attempts == 3
    assert "agotados 3 intentos" in result.stderr


def test_gh_retry_does_not_retry_permanent_error() -> None:
    result, attempts = _run_fake_gh(status=422, succeed_at=99)

    assert result.returncode != 0
    assert attempts == 1
    assert "no reintentable" in result.stderr


def test_gh_retry_reconciles_ambiguous_side_effect() -> None:
    result, attempts = _run_fake_gh(
        status=503,
        succeed_at=99,
        reconcile_result=0,
    )

    assert result.returncode == 0, result.stderr
    assert attempts == 1
    assert "efecto ya confirmado" in result.stderr


def test_gh_retry_does_not_repeat_indeterminate_side_effect() -> None:
    result, attempts = _run_fake_gh(
        status=503,
        succeed_at=99,
        reconcile_result=2,
    )

    assert result.returncode == 2
    assert attempts == 1
    assert "reconciliación indeterminada" in result.stderr


def test_cli_evaluates_fetched_json_without_network() -> None:
    completed_failures = [
        _run(conclusion="failure", run_id=102),
        _run(conclusion="cancelled", run_id=101),
    ]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lucidfence.core.cron_watchdog",
            "--min-failures",
            "2",
            "--existing-issue",
            "44",
            "--existing-issue",
            "42",
        ],
        cwd=ROOT,
        input=json.dumps(completed_failures),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["action"] == "reconcile"
    assert payload["primary_issue"] == 42
    assert payload["issues_to_close"] == [44]


if __name__ == "__main__":
    test_closes_existing_alert_only_after_completed_success()
    test_skips_when_latest_run_is_queued_or_in_progress()
    test_failure_alert_is_idempotent_when_issue_already_exists()
    test_does_not_close_alert_until_a_completed_success_exists()
    test_ignores_non_health_events_and_non_default_branches()
    test_reconciles_all_duplicate_issues_deterministically()
    test_unknown_completed_conclusion_is_indeterminate()
    test_lookback_applies_after_branch_and_event_filtering()
    test_workflow_has_idempotent_label_and_query_guards()
    test_gh_retry_recovers_from_transient_failure()
    test_gh_retry_exhausts_and_fails_closed()
    test_gh_retry_does_not_retry_permanent_error()
    test_gh_retry_reconciles_ambiguous_side_effect()
    test_gh_retry_does_not_repeat_indeterminate_side_effect()
    test_cli_evaluates_fetched_json_without_network()
