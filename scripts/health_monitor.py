#!/usr/bin/env python3
"""Healthy LucidFence health monitor (#18).

Usage:
    python3 scripts/health_monitor.py            # single shot
    python3 scripts/health_monitor.py --help     # show options

Behavior:
    - hits /api/health on host
    - on failure: creates or reopens GH issue with environment snapshot
    - on success: leaves existing open issue closed if desired
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_HOST = "http://127.0.0.1:8765"
REQUIRED_LABELS = ["infrastructure", "WS3-platform-ops", "P1", "roadmap"]


def _gh(args: argparse.Namespace, path: str, data: dict) -> dict:
    import subprocess
    cmd = [
        "gh", "api", path,
        "-F", "title=" + data.get("title", ""),
        "-f", "body=" + data.get("body", ""),
        "--jq", ".",
    ]
    if path.endswith("/comments"):
        cmd = ["gh", "issue", "comment", str(data.pop("issue")), "--body", data.get("body", "")]
    env = os.environ.copy()
    out = subprocess.check_output(cmd, env=env, text=True)
    return json.loads(out)


def _post(args: argparse.Namespace, path: str, payload: dict) -> dict:
    if path.startswith("repos/"):
        # use gh CLI for convenience only if available
        raise SystemExit("delegar llamada real con gh cliquea gh api/issue create desde la CLI")
    # network path (no auth needed)
    req = urllib.request.Request(
        args.host + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"ok": False, "http_status": e.code, "body": body}
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def health_check(args: argparse.Namespace) -> dict:
    url = args.host.rstrip("/") + "/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lucidfence-health-monitor"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "http_status": e.code, "body": e.read().decode(errors="replace")}
    except Exception as exc:
        return {"ok": False, "error": repr(exc)}


def find_open_issue(args: argparse.Namespace) -> dict | None:
    import subprocess, json
    try:
        out = subprocess.check_output([
            "gh", "issue", "list", "--repo", args.repo, "--state", "open",
            "--search", "type:issue [WS3] Monitor health-check que crea tareas",
            "--json", "number,title", "--limit", "1", "--jq", ".[0]"
        ], text=True)
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(out) or None
    except Exception:
        return None


def ensure_closed(args: argparse.Namespace, issue_number: int, comment: str) -> None:
    # comment first, then close
    import subprocess
    subprocess.check_call([
        "gh", "issue", "comment", str(issue_number),
        "--repo", args.repo, "--body", comment + f"\n\nClosed automatically by health monitor at {datetime.datetime.now(datetime.timezone.utc).isoformat()}."
    ], text=True)
    subprocess.check_call([
        "gh", "issue", "close", str(issue_number),
        "--repo", args.repo, "--reason", "not planned"
    ], text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST, help="Base URL")
    ap.add_argument("--repo", default="adrimg3196/lucidfence", help="repo OWNER/NAME")
    ap.add_argument("--gh-issue", type=int, help="Open GitHub issue to keep updated")
    ap.add_argument("--reopen-if-closed", action="store_true", help="Reopen closed issue on failure")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    check = health_check(args)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot = {"checked_at": now, "host": args.host, "result": check}
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))

    if check.get("ok") or (isinstance(check.get("status"), str) and check.get("status") == "ok"):
        issue = find_open_issue(args) if not args.gh_issue else None
        num = args.gh_issue or (issue.get("number") if issue else None)
        if num:
            comment = f"✅ health OK at {now}.\n```json\n{json.dumps(check, indent=2)}\n```"
            if args.dry_run:
                print(f"Would comment on issue #{num}: {comment[:160]}...")
                return 0
            try:
                ensure_closed(args, num, comment)
                print(f"Closed/fixed open issue #{num}")
            except SystemExit:
                pass
        return 0

    body = (
        "## Health check failure\n"
        f"- **checked_at**: {now}\n"
        f"- **host**: {args.host}\n"
        f"- **result**: `{json.dumps(check)}`\n\n"
        f"Fix playbook:\n1. Open `lucidfence.out.log` / `lucidfence.err.log`\n"
        "2. Restart: `launchctl unload ~/Library/LaunchAgents/com.lucidfence.engine.plist && launchctl load ~/Library/LaunchAgents/com.lucidfence.engine.plist`\n"
        "3. Re-run: `python3 scripts/health_monitor.py`\n"
    )
    if args.dry_run:
        print("Would create/update GitHub issue:")
        print(body)
        return 1
    title = "[INFRA] LucidFence health-check failed"
    issue = find_open_issue(args)
    if issue:
        num = issue["number"]
        import subprocess
        subprocess.check_call([
            "gh", "issue", "comment", str(num), "--repo", args.repo, "--body", body
        ], text=True)
        print(f"Updated existing issue #{num}")
    else:
        data = {"title": title, "body": body, "labels": REQUIRED_LABELS}
        out = subprocess.check_output([
            "gh", "issue", "create", "--repo", args.repo,
            "--title", data["title"], "--body", data["body"], "--label", ",".join(data["labels"])
        ], text=True)
        print(f"Created issue: {out.strip()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
