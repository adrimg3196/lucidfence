#!/usr/bin/env python3
"""Healthy LucidFence health monitor (#18) — monitoring-expert hardened.

Usage:
    python3 scripts/health_monitor.py            # single shot
    python3 scripts/health_monitor.py --help     # show options

Behavior:
    - hits /api/health on host
    - on failure: creates or reopens GH issue with environment snapshot
    - on success: leaves existing open issue closed if desired
    - optional structured JSON log lines + metrics endpoint
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DEFAULT_HOST = "http://127.0.0.1:8765"
REQUIRED_LABELS = ["infrastructure", "WS3-platform-ops", "P1", "roadmap"]


def _gh(args: argparse.Namespace, path: str, data: dict) -> dict:
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
        raise SystemExit("delegar llamada real con gh cliquea gh api/issue create desde la CLI")
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
    subprocess.check_call([
        "gh", "issue", "comment", str(issue_number),
        "--repo", args.repo, "--body", comment + f"\n\nClosed automatically by health monitor at {datetime.datetime.now(datetime.timezone.utc).isoformat()}."
    ], text=True)
    subprocess.check_call([
        "gh", "issue", "close", str(issue_number),
        "--repo", args.repo, "--reason", "not planned"
    ], text=True)


def classify_severity(check: dict) -> tuple[str, list[str]]:
    if check.get("ok") or (isinstance(check.get("status"), str) and check.get("status") == "ok"):
        return "ok", []
    http_status = check.get("http_status")
    canonical: list[str] = []
    status = "critical"
    if isinstance(http_status, int):
        if http_status in (401, 403):
            status = "critical"
            canonical.append("auth_problem")
        elif 500 <= http_status < 600:
            status = "critical"
            canonical.append("http_5xx")
        else:
            status = "degraded"
            canonical.append("http_client_error")
    else:
        status = "critical"
        canonical.append("health_unreachable")
    return status, canonical


def render_metrics_text(snapshot: dict) -> str:
    check = snapshot.get("result", {}) if isinstance(snapshot, dict) else {}
    status = "ok" if check.get("ok") or check.get("status") == "ok" else "fail"
    http_status = check.get("http_status", 0) if isinstance(check, dict) else 0
    lines = [
        "# HELP lucidfence_health_check G=ok, 1=fail",
        "# TYPE lucidfence_health_check gauge",
        f'lucidfence_health_check{{status="{status}"}} {1 if status == "ok" else 0}',
        "",
        "# HELP lucidfence_health_http_status Last /api/health HTTP status",
        "# TYPE lucidfence_health_http_status gauge",
        f"lucidfence_health_http_status {int(http_status)}",
        "",
    ]
    return "\n".join(lines)


class _MetricsHandler(BaseHTTPRequestHandler):
    metrics_text = ""
    health_status = "ok"
    ready_status = "ready"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/metrics":
            self._text(200, _MetricsHandler.metrics_text or "# no metrics yet\n")
        elif path == "/healthz":
            self._text(200 if _MetricsHandler.health_status == "ok" else 503, _MetricsHandler.health_status + "\n")
        elif path == "/readyz":
            self._text(200 if _MetricsHandler.ready_status == "ready" else 503, _MetricsHandler.ready_status + "\n")
        else:
            self._text(404, "not found\n")

    def _text(self, code: int, body: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *__args: object, **__kwargs: object) -> None:
        return


def _serve_metrics(port: int, metrics_text: str, ready: threading.Event, stop: threading.Event) -> None:
    _MetricsHandler.metrics_text = metrics_text
    _MetricsHandler.health_status = "ok"
    _MetricsHandler.ready_status = "ready"
    server = HTTPServer(("127.0.0.1", port), _MetricsHandler)
    ready.set()
    server.timeout = 0.5
    while not stop.is_set():
        server.handle_request()
    server.server_close()


class JsonLineLogger:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def log(self, event: str, payload: dict) -> None:
        if not self.enabled:
            return
        record = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "event": event, **payload}
        print(json.dumps(record, ensure_ascii=False), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST, help="Base URL")
    ap.add_argument("--repo", default="adrimg3196/lucidfence", help="repo OWNER/NAME")
    ap.add_argument("--gh-issue", type=int, help="Open GitHub issue to keep updated")
    ap.add_argument("--reopen-if-closed", action="store_true", help="Reopen closed issue on failure")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-log", action="store_true", help="Emit structured JSON log lines")
    ap.add_argument("--serve-metrics", action="store_true", help="Serve metrics endpoint")
    ap.add_argument("--metrics-port", type=int, default=9105, help="Metrics bind port")
    args = ap.parse_args()

    check = health_check(args)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshot = {"checked_at": now, "host": args.host, "result": check}
    status, canonical_alerts = classify_severity(check)

    logger = JsonLineLogger(args.json_log)
    logger.log("health_check", {"host": args.host, "http_status": check.get("http_status"), "status": status})

    metrics_text = render_metrics_text(snapshot)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))

    metrics_thread: threading.Thread | None = None
    metrics_stop = threading.Event()
    if args.serve_metrics:
        ready = threading.Event()
        _MetricsHandler.metrics_text = metrics_text
        metrics_thread = threading.Thread(target=_serve_metrics, args=(args.metrics_port, metrics_text, ready, metrics_stop), daemon=True)
        metrics_thread.start()
        ready.wait(timeout=3)

    try:
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

        enriched = (
            "## Health check failure\n"
            f"- **checked_at**: {now}\n"
            f"- **host**: {args.host}\n"
            f"- **severity**: `{status}`\n"
            f"- **canonical_alerts**: `{', '.join(canonical_alerts) or 'n/a'}`\n"
            f"- **result**: `{json.dumps(check)}`\n\n"
            "Fix playbook:\n1. Open `lucidfence.out.log` / `lucidfence.err.log`\n"
            "2. Restart: `launchctl unload ~/Library/LaunchAgents/com.lucidfence.engine.plist && launchctl load ~/Library/LaunchAgents/com.lucidfence.engine.plist`\n"
            "3. Re-run: `python3 scripts/health_monitor.py`\n"
        )
        if args.dry_run:
            print("Would create/update GitHub issue:")
            print(enriched)
            return 1
        title = "[INFRA] LucidFence health-check failed"
        issue = find_open_issue(args)
        if issue:
            num = issue["number"]
            subprocess.check_call([
                "gh", "issue", "comment", str(num), "--repo", args.repo, "--body", enriched
            ], text=True)
            print(f"Updated existing issue #{num}")
        else:
            data = {"title": title, "body": enriched, "labels": REQUIRED_LABELS}
            out = subprocess.check_output([
                "gh", "issue", "create", "--repo", args.repo,
                "--title", data["title"], "--body", data["body"], "--label", ",".join(data["labels"])
            ], text=True)
            print(f"Created issue: {out.strip()}")
        return 1
    finally:
        if metrics_thread is not None:
            metrics_stop.set()


if __name__ == "__main__":
    raise SystemExit(main())
