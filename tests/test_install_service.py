#!/usr/bin/env python3
"""Focused installer service QA for issue #15."""
from __future__ import annotations

import pathlib
import sys
import xml.etree.ElementTree as ET

REPO = pathlib.Path("/Users/adri/geofence-uem")

def check_unit_files() -> int:
    service = REPO / "deploy/systemd/lucidfence.service"
    plist = REPO / "deploy/launchd/com.adrimg3196.lucidfence.plist"
    if not service.exists():
        print(f"[FAIL] missing {service}")
        return 1
    text = service.read_text()
    if "Restart=always" not in text:
        print("[FAIL] systemd unit missing Restart=always")
        return 1
    if "{working_dir}" in text:
        print("[FAIL] systemd unit has unresolved template placeholder")
        return 1
    print(f"[ok] {service}")
    if not plist.exists():
        print(f"[FAIL] missing {plist}")
        return 1
    ET.fromstringlist(plist.read_text().splitlines())
    print(f"[ok] {plist}")
    return 0

def _main() -> int:
    return check_unit_files()

def main() -> int:
    return _main()

if __name__ == "__main__":
    raise SystemExit(main())
