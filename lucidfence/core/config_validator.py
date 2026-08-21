"""Validate a LucidFence location_source mapping against the live API.

Works for ANY UEM/MDM configured via the generic HTTP source: Fleet, Intune
(Graph), Jamf, Mosyle, Workspace ONE, or a custom endpoint. It hits the real
API once, takes the returned devices, and reports which configured field
paths resolve — so a user knows in one command if their mapping is right.

Usage:
    python3 -m lucidfence.core.config_validator --config config.json
    lucidfence validate-config --config config.json
"""
from __future__ import annotations

import json
import sys

from lucidfence.core.generic_http_source import GenericHTTPLocationSource, _dig
from lucidfence.core.config_loader import load


def validate_location_source(cfg: dict) -> dict:
    """Return a report dict for a location_source mapping.

    Resolves the API, then for every configured `fields` path reports how many
    of the returned devices yielded a non-null value. Also flags devices with no
    lat/lng (silently dropped by the engine) and the overall fetch error if any.
    """
    src = GenericHTTPLocationSource(cfg)
    reports = src.fetch()  # uses the real URL + headers (env-expanded)
    fields = cfg.get("fields", {})
    total = len(reports)
    # Count raw devices returned by the API (before geo filtering) so the user
    # sees how many were dropped for lacking lat/lng.
    devices_raw = 0
    try:
        import urllib.request as _ur
        req = _ur.Request(src.url, headers=src.headers, method=src.method)
        with _ur.urlopen(req, timeout=src.timeout) as resp:
            devices_raw = len(src._parse_items(resp.read()))
    except Exception:
        devices_raw = total  # best-effort; fall back to parsed count
    per_field = {}
    for label, path in fields.items():
        resolved = sum(1 for r in reports if _dig(r.raw, path) is not None)
        per_field[label] = {"path": path, "resolved": resolved, "total": total}
    no_geo = 0
    for r in reports:
        if r.lat is None or r.lng is None:
            no_geo += 1
    return {
        "url": cfg.get("url", ""),
        "devices_raw": devices_raw,
        "devices_returned": total,
        "devices_with_geo": total - no_geo,
        "devices_dropped_no_geo": (devices_raw - total) if devices_raw >= total else 0,
        "fetch_error": src.last_error,
        "field_resolution": per_field,
        "ok": total > 0 and (total - no_geo) > 0 and src.last_error is None,
    }


def validate_config(config_path: str) -> dict:
    from pathlib import Path
    cfg = load(Path(config_path))
    ls = cfg.get("location_source")
    if not ls or not ls.get("url"):
        return {"ok": False, "reason": "no location_source.url in config; nothing to validate"}
    return validate_location_source(ls)


def _main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Validate a LucidFence location_source mapping")
    p.add_argument("--config", default="config.json", help="path to config.json")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)
    result = validate_config(args.config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if not result.get("ok") and result.get("reason"):
            print(f"SKIP: {result['reason']}")
            return 1
        print(f"URL: {result['url']}")
        print(f"Devices returned: {result['devices_returned']} "
              f"(with geo: {result['devices_with_geo']}, without: {result['devices_without_geo']})")
        if result["fetch_error"]:
            print(f"FETCH ERROR: {result['fetch_error']}")
        print("Field resolution:")
        for label, info in result["field_resolution"].items():
            flag = "OK" if info["resolved"] == info["total"] and info["total"] else \
                   ("PARTIAL" if info["resolved"] else "MISSING")
            print(f"  {label:12s} {info['path']:30s} {info['resolved']}/{info['total']}  [{flag}]")
        print("RESULT:", "OK" if result["ok"] else "CHECK MAPPING")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
