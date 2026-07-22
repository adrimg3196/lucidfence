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
    sync_playwright = None
    _PLAYWRIGHT_ERROR = exc

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_install_panel_browser_smoke() -> None:
    assert sync_playwright is not None, f"Playwright es obligatorio para E2E: {_PLAYWRIGHT_ERROR}"
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


def main() -> int:
    test_cloud_install_panel_browser_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
