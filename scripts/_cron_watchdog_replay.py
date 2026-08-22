#!/usr/bin/env python3
"""Replay the cron-watchdog detection logic against a historical window to
prove the OPEN-ISSUE branch fires. Uses the real run history of
nightly-health-check (read-only gh calls).

For each 'as-of' date we compute, over the runs available up to that date,
the newest-first consecutive-failure count and the watchdog decision -- exactly
the same logic as cron-watchdog.yml's jq.
"""
import json
import subprocess

OWNER, REPO = "adrimg3196", "lucidfence"
WF = "nightly-health-check"
MIN_FAILS = 2
LOOKBACK = 12  # wider window so we capture the whole incident


def fetch_runs():
    out = subprocess.run(
        ["gh", "api",
         f"repos/{OWNER}/{REPO}/actions/workflows/{WF}.yml/runs?per_page={LOOKBACK}",
         "--jq", ".workflow_runs | map({conclusion, status, created_at, id})"],
        capture_output=True, text=True,
    )
    return json.loads(out.stdout)


def decision_for_window(runs):
    """runs: newest-first list. Mirror of workflow jq."""
    if not runs:
        return 0, "OK / close"
    if runs[0]["status"] != "completed":
        return 0, "OK / close"
    consecutive = 0
    for r in runs:
        if r["status"] == "completed" and r["conclusion"] != "success":
            consecutive += 1
        else:
            break
    verdict = "OPEN ISSUE" if consecutive >= MIN_FAILS else "OK / close"
    return consecutive, verdict


def main():
    runs = fetch_runs()
    # runs are newest-first. Index 0 = most recent (success on 08-22).
    print("Replaying cron-watchdog decision over the real nightly-health-check history")
    print("(window = all runs up to an 'as-of' index, newest-first):\n")
    # Walk backwards: as_of_index N means we consider runs[N:] as the "known
    # history" at that moment in time.
    for i in range(len(runs) - 1, -1, -1):
        window = runs[i:]  # truncate the future (newer runs)
        as_of = window[0]["created_at"]
        consec, verdict = decision_for_window(window)
        flag = "  <-- WOULD OPEN ISSUE" if verdict == "OPEN ISSUE" else ""
        print(f"  as-of {as_of[:19]}Z  streak_from_top={consec:2d}  -> {verdict}{flag}")


if __name__ == "__main__":
    main()
