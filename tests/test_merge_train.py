"""Unit tests for the merge train queue logic (scripts/merge_train.py).

Covers:
  - ci_state: pending checks (conclusion null/empty) are neither green nor
    failed — counting them as green broke the FIFO (QA finding on PR #104).
  - classify: every queue status, including the ci-pending state.
  - build_queue: FIFO ordering among ready PRs, drain-mode flag, next_up.
  - render: drain banner and per-status labels appear.

Pure logic only — no gh CLI, no network.

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_merge_train.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import merge_train  # noqa: E402


def _pr(number=1, state="CLEAN", checks=(), age_days=5, title="x", author="bot"):
    import datetime
    created = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=age_days)
    ).isoformat().replace("+00:00", "Z")
    return {
        "number": number,
        "title": title,
        "createdAt": created,
        "updatedAt": created,
        "author": {"login": author},
        "labels": [],
        "mergeStateStatus": state,
        "statusCheckRollup": [{"conclusion": c} for c in checks],
        "isDraft": False,
    }


def test_ci_state_pending_is_not_green():
    pr = _pr(checks=("SUCCESS", "SUCCESS", None))
    green, failed, total = merge_train.ci_state(pr)
    assert (green, failed, total) == (2, 0, 3), (green, failed, total)


def test_ci_state_empty_conclusion_is_pending():
    pr = _pr(checks=("SUCCESS", ""))
    green, failed, total = merge_train.ci_state(pr)
    assert (green, failed, total) == (1, 0, 2), (green, failed, total)


def test_classify_pending_checks_block_ready():
    # El bug original: SUCCESS+pending contaba 2/2 y entraba al train.
    pr = _pr(state="CLEAN", checks=("SUCCESS", None))
    assert merge_train.classify(pr) == "ci-pending"


def test_classify_ready_needs_all_concluded_green():
    pr = _pr(state="CLEAN", checks=("SUCCESS", "SKIPPED", "NEUTRAL"))
    assert merge_train.classify(pr) == "ready"


def test_classify_failure_wins_over_pending():
    pr = _pr(state="CLEAN", checks=("FAILURE", None, "SUCCESS"))
    assert merge_train.classify(pr) == "ci-red"


def test_classify_conflict_wins_over_ci():
    pr = _pr(state="DIRTY", checks=("SUCCESS",))
    assert merge_train.classify(pr) == "conflict"


def test_classify_no_checks_is_not_ready():
    pr = _pr(state="CLEAN", checks=())
    assert merge_train.classify(pr) == "no-ci"


def test_classify_behind_base():
    pr = _pr(state="BEHIND", checks=("SUCCESS",))
    assert merge_train.classify(pr) == "needs-update"


def test_build_queue_fifo_among_ready():
    prs = [
        _pr(number=1, checks=("SUCCESS",), age_days=2),
        _pr(number=2, checks=("SUCCESS",), age_days=10),
        _pr(number=3, state="DIRTY", checks=("SUCCESS",), age_days=20),
    ]
    q = merge_train.build_queue(prs)
    # El listo más antiguo va primero; el conflicto detrás aunque sea más viejo.
    assert q["next_up"] == 2, q
    assert [r["number"] for r in q["rows"]] == [2, 1, 3], q["rows"]


def test_build_queue_drain_mode():
    prs = [_pr(number=i, checks=("SUCCESS",)) for i in range(1, 8)]
    q = merge_train.build_queue(prs)
    assert q["over_limit"] is True
    assert "DRENAJE" in merge_train.render(q)


def test_build_queue_under_limit_no_drain():
    prs = [_pr(number=1, checks=("SUCCESS",))]
    q = merge_train.build_queue(prs)
    assert q["over_limit"] is False
    assert q["next_up"] == 1


def test_render_shows_pending_label():
    q = merge_train.build_queue([_pr(number=9, checks=("SUCCESS", None))])
    assert "CI en curso" in merge_train.render(q)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
