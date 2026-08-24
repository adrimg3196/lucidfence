"""Pure decision engine for the GitHub Actions cron watchdog.

The evaluator is deliberately independent from GitHub and the network.  The
workflow owns API calls; this module only decides whether an already fetched
run history proves that an alert should be opened, kept, closed, or skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Sequence, TextIO


HEALTH_EVENTS = frozenset({"schedule", "workflow_dispatch"})
FAILURE_CONCLUSIONS = frozenset(
    {
        "action_required",
        "cancelled",
        "failure",
        "neutral",
        "skipped",
        "stale",
        "startup_failure",
        "timed_out",
    }
)


@dataclass(frozen=True)
class WatchdogDecision:
    """Mutation (or safe no-op) selected for one watched workflow."""

    action: str
    reason: str
    consecutive_failures: int
    latest_run_id: int | None
    latest_created_at: str | None
    primary_issue: int | None = None
    issues_to_close: tuple[int, ...] = ()


def evaluate_workflow(
    runs: Sequence[dict[str, Any]],
    *,
    existing_issues: Sequence[int] = (),
    default_branch: str = "main",
    min_failures: int = 2,
    lookback: int = 10,
) -> WatchdogDecision:
    """Return the safe action for runs ordered newest first.

    An existing alert is closed only by positive evidence: the newest run must
    be both ``completed`` and ``success``.  Missing history and any unfinished
    newest run are indeterminate and therefore never mutate issues.
    """

    if min_failures < 1:
        raise ValueError("min_failures must be at least 1")
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    issues = tuple(sorted(set(existing_issues)))
    if any(issue < 1 for issue in issues):
        raise ValueError("existing issue numbers must be positive")
    primary_issue = issues[0] if issues else None
    if not runs:
        return WatchdogDecision(
            action="skip",
            reason="no_runs",
            consecutive_failures=0,
            latest_run_id=None,
            latest_created_at=None,
            primary_issue=primary_issue,
        )

    eligible_runs = [
        run
        for run in runs
        if run.get("head_branch") == default_branch
        and run.get("event") in HEALTH_EVENTS
    ][:lookback]
    if not eligible_runs:
        return WatchdogDecision(
            action="skip",
            reason="no_eligible_runs",
            consecutive_failures=0,
            latest_run_id=None,
            latest_created_at=None,
            primary_issue=primary_issue,
        )

    latest = eligible_runs[0]
    latest_status = str(latest.get("status") or "unknown")
    if latest_status != "completed":
        return WatchdogDecision(
            action="skip",
            reason=f"latest_run_{latest_status}",
            consecutive_failures=0,
            latest_run_id=latest.get("id"),
            latest_created_at=latest.get("created_at"),
            primary_issue=primary_issue,
        )

    latest_conclusion = latest.get("conclusion")
    if latest_conclusion == "success":
        return WatchdogDecision(
            action="close" if issues else "keep",
            reason=(
                "latest_run_recovered"
                if issues
                else "latest_run_healthy"
            ),
            consecutive_failures=0,
            latest_run_id=latest.get("id"),
            latest_created_at=latest.get("created_at"),
            primary_issue=primary_issue,
            issues_to_close=issues,
        )
    if latest_conclusion not in FAILURE_CONCLUSIONS:
        return WatchdogDecision(
            action="skip",
            reason="latest_conclusion_unknown",
            consecutive_failures=0,
            latest_run_id=latest.get("id"),
            latest_created_at=latest.get("created_at"),
            primary_issue=primary_issue,
        )

    consecutive_failures = 0
    for run in eligible_runs:
        conclusion = run.get("conclusion")
        if run.get("status") != "completed" or conclusion == "success":
            break
        if conclusion not in FAILURE_CONCLUSIONS:
            break
        consecutive_failures += 1

    if len(issues) > 1:
        return WatchdogDecision(
            action="reconcile",
            reason="duplicate_alerts_open",
            consecutive_failures=consecutive_failures,
            latest_run_id=latest.get("id"),
            latest_created_at=latest.get("created_at"),
            primary_issue=primary_issue,
            issues_to_close=issues[1:],
        )

    if consecutive_failures >= min_failures:
        return WatchdogDecision(
            action="keep" if issues else "open",
            reason=(
                "alert_already_open"
                if issues
                else "failure_threshold_reached"
            ),
            consecutive_failures=consecutive_failures,
            latest_run_id=latest.get("id"),
            latest_created_at=latest.get("created_at"),
            primary_issue=primary_issue,
        )

    return WatchdogDecision(
        action="keep",
        reason="failure_below_threshold",
        consecutive_failures=consecutive_failures,
        latest_run_id=latest.get("id"),
        latest_created_at=latest.get("created_at"),
        primary_issue=primary_issue,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    """Evaluate JSON read from stdin and emit one machine-readable decision."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-issue", action="append", type=int, default=[])
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--min-failures", type=int, default=2)
    parser.add_argument("--lookback", type=int, default=10)
    args = parser.parse_args(argv)
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout

    try:
        runs = json.load(source)
    except json.JSONDecodeError as exc:
        parser.error(f"invalid runs JSON: {exc}")
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        parser.error("runs JSON must be a list of objects")

    decision = evaluate_workflow(
        runs,
        existing_issues=args.existing_issue,
        default_branch=args.default_branch,
        min_failures=args.min_failures,
        lookback=args.lookback,
    )
    json.dump(asdict(decision), target, separators=(",", ":"), sort_keys=True)
    target.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
