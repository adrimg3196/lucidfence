#!/usr/bin/env python3
"""Webapp-testing E2E for LucidFence dashboard."""
from __future__ import annotations

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
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto("http://127.0.0.1:8765/static/dashboard.html", wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=30000)

            page.wait_for_timeout(1000)
            page.wait_for_selector("body >> text=Command Center", timeout=15000)
            assert page.title() == "LucidFence · Command Center"
            assert page.locator("text=OPERACIÓN").count() >= 1
            assert page.locator("text= Ciclo ").count() >= 1

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"{msg.type}: {msg.text}"))
            before = len(console_msgs)
            page.reload(wait_until="load")
            page.wait_for_timeout(500)
            new_errors = [m for m in console_msgs[before:] if m.startswith("error:")]
            assert not new_errors, f"Console errors after reload: {new_errors}"

            page.screenshot(path="/tmp/lucidfence-dashboard-e2e.png", full_page=False)
            print("webapp-e2e-ok: dashboard title + Operation block visible")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
