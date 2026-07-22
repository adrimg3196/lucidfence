#!/usr/bin/env python3
"""Webapp-testing E2E for LucidFence dashboard."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:
    sync_playwright = None
    _PLAYWRIGHT_ERROR = exc

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_browser_smoke() -> None:
    assert sync_playwright is not None, f"Playwright es obligatorio para E2E: {_PLAYWRIGHT_ERROR}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            console_msgs, page_errors, request_failures, bad_responses = [], [], [], []
            page.on("console", lambda msg: console_msgs.append(f"{msg.type}: {msg.text}"))
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.on("requestfailed", lambda req: request_failures.append(f"{req.method} {req.url}: {req.failure}"))
            page.on("response", lambda response: bad_responses.append(f"{response.status} {response.url}") if response.status >= 400 else None)

            page.goto("http://127.0.0.1:8765/static/dashboard.html", wait_until="domcontentloaded")
            page.wait_for_load_state("load", timeout=30000)

            page.wait_for_timeout(1000)
            page.wait_for_selector("body >> text=Command Center", timeout=15000)
            assert page.title() == "LucidFence · Command Center"
            assert page.locator("text=OPERACIÓN").count() >= 1
            assert page.locator("text= Ciclo ").count() >= 1

            # Reset expected anonymous /api/auth/me=401 from bootstrap, then
            # traverse every active product view and demand real rendered data.
            bad_responses.clear(); request_failures.clear(); console_msgs.clear(); page_errors.clear()
            hrefs = page.locator("#nav a").evaluate_all("els => els.map(e => e.getAttribute('href'))")
            assert len(hrefs) == 19, f"Expected 19 product views, got {len(hrefs)}"
            assert "#company" in hrefs
            for href in hrefs:
                page.locator(f'#nav a[href="{href}"]').click()
                view_id = "view-" + href.lstrip("#")
                page.wait_for_function("id => { const n=document.getElementById(id); return n && !n.classList.contains('hidden') && n.innerText.trim().length>0; }", arg=view_id, timeout=15000)

            page.locator('#nav a[href="#company"]').click()
            page.wait_for_selector("#companyNewGoal")
            assert "Compañía autónoma" in page.locator("#view-company").inner_text()
            assert "Mission Control" in page.locator("#view-company").inner_text()
            page.locator("#companyNewGoal").click()
            page.locator("#companyGoalTitle").fill("Objetivo E2E geofencing")
            page.locator("#companyGoalOutcome").fill("Reducir outside con simulación verificable")
            page.locator("#companyCreateGoal").click()
            page.wait_for_selector("#view-company >> text=Objetivo E2E geofencing", timeout=10000)
            assert "dashboard.html" in page.url
            page.locator("#companyRun").click()
            page.wait_for_selector("#view-company >> text=simulate_geofence", timeout=10000)

            page.locator("#lfLangBtn").click()
            page.wait_for_function("document.documentElement.lang === 'en'")
            assert "Inventory" in page.locator("#nav").inner_text()
            page.get_by_role("link", name="Autonomous company", exact=True).click()
            page.wait_for_selector("#view-company >> text=Autonomous geofencing company", timeout=5000)
            page.get_by_role("link", name="Devices", exact=True).click()
            page.wait_for_selector('input[placeholder^="Search device"]', state="attached", timeout=5000)
            page.locator("#lfLangBtn").click()
            page.wait_for_function("document.documentElement.lang === 'es'")
            assert page.get_by_role("link", name="Inventario", exact=True).count() == 1

            page.wait_for_timeout(500)
            new_errors = [m for m in console_msgs if m.startswith("error:")]
            assert not page_errors, f"Page errors: {page_errors}"
            assert not request_failures, f"Request failures: {request_failures}"
            assert not bad_responses, f"HTTP errors while traversing views: {bad_responses}"
            assert not new_errors, f"Console errors: {new_errors}"

            page.goto("http://127.0.0.1:8765/static/dashboard.html#company", wait_until="load")
            page.wait_for_selector("#view-company >> text=Compañía autónoma de geofencing", timeout=10000)

            page.screenshot(path="/tmp/lucidfence-dashboard-e2e.png", full_page=False)
            print("webapp-e2e-ok: 19 views rendered; no HTTP/request/page/console errors")
        finally:
            browser.close()


def main() -> int:
    test_dashboard_browser_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
