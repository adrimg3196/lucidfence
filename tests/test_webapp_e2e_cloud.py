#!/usr/bin/env python3
"""Webapp-testing E2E for lucidfence cloud install panel.

Uses the skill's black-box runner: `with_server.py`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:
    print(f"SKIP playwright unavailable: {exc}")
    sys.exit(0)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto((ROOT / "static" / "cloud.html").as_uri(), wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=30_000)

            # Element discovery: verify key landmarks exist
            assert page.title() == "LucidFence · Geofencing en Vivo (Cloud)"
            assert page.locator("text=Descarga LucidFence").count() == 1
            assert page.locator("text=brew install adrimg3196/lucidfence/lucidfence").count() == 1
            assert page.locator("text=Descargar v1.0.1").count() == 1
            assert page.locator("text=Ver repo").count() == 1

            # Console log capture
            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"{msg.type}: {msg.text}"))
            page.reload(wait_until="networkidle")
            errors = [m for m in console_msgs if m.startswith("error:")]
            assert not errors, f"Console errors: {errors}"

            # Screenshot for visual verification
            page.screenshot(path="/tmp/lucidfence-cloud-e2e.png", full_page=False)
            print("webapp-testing-ok: cloud page smoke passed, screenshot saved")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
