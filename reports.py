#!/usr/bin/env python3
"""Local compliance/report generator for the Geofence UEM product.

Produces Markdown + CSV + JSON reports from the local state store. Fully
offline: reads only `data/` and `fences.json`, writes to a local `--out` dir.
No network, no credentials, no device contact.

Usage:
  python3 reports.py --out /tmp/reports/            # full fleet report
  python3 reports.py --fence restricted-zone --out /tmp/reports/
  python3 reports.py --format csv --out /tmp/reports/
  python3 reports.py --violations-only --out /tmp/reports/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.fences import load_fences  # noqa: E402
from core.state_store import StateStore, now_iso  # noqa: E402


def build_report(store: StateStore, fences: list, fence_id: str | None,
                 violations_only: bool) -> dict:
    states = list(store.snapshot().values())
    fences_by_id = {f.id: f for f in fences}

    devices = []
    for s in states:
        fid = s.fence_id
        fence = fences_by_id.get(fid) if fid else None
        is_violation = (
            s.fence_state == "inside"
            and s.compliant is False
            and fence is not None
            and any(a.when == "on_violation" for a in fence.actions)
        )
        if violations_only and not is_violation:
            continue
        if fence_id and fid != fence_id:
            continue
        devices.append({
            "device_id": s.device_id,
            "name": s.name,
            "platform": s.platform,
            "status": s.status,
            "compliant": s.compliant,
            "fence_state": s.fence_state,
            "fence_id": fid,
            "fence_name": fence.name if fence else None,
            "lat": s.lat,
            "lng": s.lng,
            "accuracy_m": s.accuracy_m,
            "country": s.country,
            "city": s.city,
            "location_source": s.location_source,
            "dwell_seconds": store.dwell_seconds(s.device_id),
            "is_violation": is_violation,
        })

    total = len(states)
    inside = sum(1 for d in devices if d["fence_state"] == "inside")
    outside = sum(1 for d in devices if d["fence_state"] == "outside")
    unknown = sum(1 for d in devices if d["fence_state"] == "unknown")
    non_compliant = sum(1 for d in devices if d["compliant"] is False)
    violations = sum(1 for d in devices if d["is_violation"])

    by_fence: dict[str, dict] = {}
    for d in devices:
        fid = d["fence_id"] or "none"
        rec = by_fence.setdefault(fid, {"name": d["fence_name"], "inside": 0, "violations": 0})
        if d["fence_state"] == "inside":
            rec["inside"] += 1
        if d["is_violation"]:
            rec["violations"] += 1

    compliance_rate = round(100.0 * (total - non_compliant) / total, 1) if total else 0.0

    report = {
        "generated_at": now_iso(),
        "scope": fence_id or "all",
        "totals": {
            "devices": total,
            "inside": inside,
            "outside": outside,
            "unknown": unknown,
            "non_compliant": non_compliant,
            "violations": violations,
            "compliance_rate_pct": compliance_rate,
        },
        "by_fence": by_fence,
        "devices": devices,
        "recent_events": store.recent_events(50),
        "recent_actions": store.recent_actions(50),
    }
    return report


def render_markdown(report: dict) -> str:
    t = report["totals"]
    lines = []
    lines.append(f"# Geofence UEM Compliance Report")
    lines.append("")
    lines.append(f"- Generated: `{report['generated_at']}`")
    lines.append(f"- Scope: `{report['scope']}`")
    lines.append("")
    lines.append("## Fleet summary")
    lines.append("")
    lines.append(f"- Devices: **{t['devices']}**")
    lines.append(f"- Inside a fence: {t['inside']}")
    lines.append(f"- Outside: {t['outside']}")
    lines.append(f"- Unknown location: {t['unknown']}")
    lines.append(f"- Non-compliant: {t['non_compliant']}")
    lines.append(f"- **Active violations: {t['violations']}**")
    lines.append(f"- Compliance rate: **{t['compliance_rate_pct']}%**")
    lines.append("")
    lines.append("## Per-fence")
    lines.append("")
    lines.append("| Fence | Inside | Violations |")
    lines.append("|-------|--------|------------|")
    for fid, rec in report["by_fence"].items():
        lines.append(f"| {rec['name'] or fid} | {rec['inside']} | {rec['violations']} |")
    lines.append("")
    lines.append("## Devices")
    lines.append("")
    lines.append("| Device | Platform | State | Fence | Compliant | Dwell (s) | Violation |")
    lines.append("|--------|----------|-------|-------|-----------|-----------|-----------|")
    for d in report["devices"]:
        vc = "YES" if d["is_violation"] else ""
        comp = "no" if d["compliant"] is False else ("yes" if d["compliant"] else "?")
        lines.append(
            f"| {d['name']} | {d['platform']} | {d['fence_state']} | "
            f"{d['fence_name'] or '-'} | {comp} | {d['dwell_seconds']} | {vc} |"
        )
    lines.append("")
    lines.append("## Recent events")
    lines.append("")
    for e in report["recent_events"][-15:]:
        lines.append(f"- `{e.get('ts')}` {e.get('device_name')}: {e.get('from')} -> {e.get('to')}")
    lines.append("")
    lines.append("## Recent UEM actions")
    lines.append("")
    for a in report["recent_actions"][-15:]:
        lines.append(
            f"- `{a.get('ts')}` {a.get('action')} on {a.get('device_name')} "
            f"[{a.get('trigger')}] dry_run={a.get('dry_run')}"
        )
    lines.append("")
    return "\n".join(lines)


def render_csv(report: dict) -> str:
    out = []
    fields = ["device_id", "name", "platform", "status", "compliant", "fence_state",
              "fence_name", "lat", "lng", "accuracy_m", "country", "city",
              "location_source", "dwell_seconds", "is_violation"]
    out.append(",".join(fields))
    for d in report["devices"]:
        row = [str(d.get(f, "")) for f in fields]
        out.append(",".join(row))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Geofence UEM local compliance report")
    ap.add_argument("--out", default="reports", help="output directory")
    ap.add_argument("--fences", default="fences.json", help="fences config path")
    ap.add_argument("--data-dir", default="data", help="state store dir")
    ap.add_argument("--format", choices=["md", "csv", "json", "all"], default="all")
    ap.add_argument("--fence", default=None, help="limit to one fence id")
    ap.add_argument("--violations-only", action="store_true")
    args = ap.parse_args()

    store = StateStore(args.data_dir)
    fences = load_fences(args.fences)
    report = build_report(store, fences, args.fence, args.violations_only)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written = []
    if args.format in ("md", "all"):
        p = out / f"report_{stamp}.md"
        p.write_text(render_markdown(report), encoding="utf-8")
        written.append(str(p))
    if args.format in ("csv", "all"):
        p = out / f"report_{stamp}.csv"
        p.write_text(render_csv(report), encoding="utf-8")
        written.append(str(p))
    if args.format in ("json", "all"):
        p = out / f"report_{stamp}.json"
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(str(p))
    print(json.dumps({"ok": True, "totals": report["totals"], "files": written},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
