#!/usr/bin/env python3
"""Offline validation of the cron-watchdog consecutive-failure algorithm.

Mirrors the jq logic in cron-watchdog.yml but runs locally against the
real last-12 runs of nightly-health-check fetched via gh (read-only).
Prints what the workflow WOULD decide for each watched workflow.
"""
import json
import subprocess
import sys

WORKFLOWS = [
    "nightly-health-check",
    "monitor-hourly",
    "engine-cron",
    "merge-train",
    "loop-audit",
]
OWNER, REPO = "adrimg3196", "lucidfence"
MIN_FAILS = 2
LOOKBACK = 10


def gh_api(path, jq="."):
    out = subprocess.run(
        ["gh", "api", path, "--jq", jq],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def main():
    print(f"Repo: {OWNER}/{REPO}  MIN_FAILS={MIN_FAILS}  LOOKBACK={LOOKBACK}")
    for wf in WORKFLOWS:
        print(f"\n---- {wf} ----")
        runs = gh_api(
            f"repos/{OWNER}/{REPO}/actions/workflows/{wf}.yml/runs?per_page={LOOKBACK}",
            jq='.workflow_runs | map({conclusion, status, id, created_at})',
        )
        if runs is None:
            print("  (no runs / API error)")
            continue
        runs = json.loads(runs)
        if not runs:
            print("  (0 runs)")
            continue
        most_recent_status = runs[0]["status"]
        print(f"  most_recent_status={most_recent_status}")

        # Mirror the jq: if most recent not completed -> 0; else count
        # consecutive failures from the top (runs are newest-first).
        if runs[0]["status"] != "completed":
            consecutive = 0
        else:
            consecutive = 0
            for r in runs:
                if r["status"] == "completed" and r["conclusion"] != "success":
                    consecutive += 1
                else:
                    break

        print(f"  consecutive_failures(confirmed)={consecutive}")
        verdict = "OPEN ISSUE" if consecutive >= MIN_FAILS else "OK / close"
        print(f"  -> decision: {verdict}")


if __name__ == "__main__":
    main()
