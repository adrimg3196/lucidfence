#!/usr/bin/env python3
"""Smoke browser check for static cloud install panel."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

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
            panel = page.locator("text=Descarga LucidFence")
            assert panel.count() == 1, panel.count()
            panel.scroll_into_view_if_needed()
            brew = page.locator("text=brew install adrimg3196/lucidfence/lucidfence")
            assert brew.count() == 1, brew.count()
            dl = page.locator("text=Descargar v1.0.1")
            assert dl.count() == 1, dl.count()
            text = page.locator("body").inner_text(timeout=5000)
            assert "Tu geofencing corre en tu máquina" in text
            print("smoke-ok: cloud install panel present and readable")
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
