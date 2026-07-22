from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_web_core_rejects_secrets_and_generates_safe_tasks():
    script = r'''
const core = require('./static/web-core.js');
let rejected = false;
try { core.sanitizeImport({devices: [], api_key: 'must-not-live-in-browser'}); }
catch (error) { rejected = /secret/i.test(error.message); }
const state = core.initialState();
const goal = core.createGoal(state, {title:'Reducir outside', outcome:'Cero salidas', target:0, autonomy:'simulate'});
const result = core.runCycle(state, {devices:6,outside:2,unknown:1,critical:3,compliance:66});
console.log(JSON.stringify({rejected, goal:goal.id, tasks:result.tasks, state}));
'''
    result = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["rejected"] is True
    assert data["goal"].startswith("goal_")
    assert data["tasks"] and all(task["evidence"] for task in data["tasks"])
    assert all(task.get("sideEffects") is False for task in data["tasks"] if task["status"] == "executed")
    assert not any(task["action"] in {"wipe", "factory_reset"} for task in data["tasks"])


def test_optional_edge_gateway_is_read_only_and_origin_scoped():
    script = r'''
import worker from './edge/uem-gateway/worker.mjs';
const env={ALLOWED_ORIGIN:'https://adrimg3196.github.io'};
const health=await worker.fetch(new Request('https://gateway.test/health'),env);
const denied=await worker.fetch(new Request('https://gateway.test/v1/fleet',{headers:{origin:'https://evil.test'}}),env);
const mutation=await worker.fetch(new Request('https://gateway.test/v1/fleet',{method:'POST',headers:{origin:env.ALLOWED_ORIGIN}}),env);
console.log(JSON.stringify({health:health.status,healthBody:await health.json(),denied:denied.status,mutation:mutation.status}));
'''
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data == {"health": 200, "healthBody": {"ok": True, "mode": "read_only", "configured": False}, "denied": 403, "mutation": 405}


def test_free_web_app_goal_cycle_and_indexeddb_persistence():
    base = os.environ.get("LUCIDFENCE_WEB_URL", "http://127.0.0.1:8765/static/web.html")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors, failed, bad = [], [], []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("requestfailed", lambda req: failed.append(req.url))
        page.on("response", lambda response: bad.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        try:
            landing = base.rsplit("/", 1)[0] + "/index.html"
            page.goto(landing, wait_until="networkidle")
            if page.title() != "LucidFence Web · Geofencing gratis":
                page.locator('a[href="web.html#company"]').first.click()
                page.wait_for_load_state("networkidle")
            assert page.title() == "LucidFence Web · Geofencing gratis"
            assert page.get_by_text("100% web · 0 €/mes", exact=True).count() == 1
            page.locator("#goalTitle").fill("Objetivo E2E web")
            page.locator("#goalOutcome").fill("Reducir salidas sin ejecutar comandos destructivos")
            page.locator("#createGoal").click()
            page.wait_for_selector("text=Objetivo E2E web")
            page.locator("#runCycle").click()
            page.wait_for_selector("text=simulate_geofence")
            page.evaluate("""() => {
                window.fetch = async (url) => {
                    if (String(url).endsWith('/v1/fleet')) return new Response(JSON.stringify({
                        source:'live_gateway', readOnly:true, devices:[{
                            id:'customer-001', name:'Tablet del cliente', platform:'Android',
                            fenceState:'inside', risk:'low', compliant:true
                        }]
                    }), {status:200, headers:{'content-type':'application/json'}});
                    throw new Error('Unexpected network call: '+url);
                };
            }""")
            parsed = urlsplit(base)
            gateway_origin = f"{parsed.scheme}://{parsed.netloc}"
            page.get_by_role("button", name="Conectar").click()
            page.locator("#gatewayUrl").fill(gateway_origin)
            page.locator("#saveGateway").click()
            page.wait_for_selector("text=URL pública guardada")
            page.locator("#syncGateway").click()
            page.wait_for_selector("text=Tablet del cliente")
            cycle_before = page.locator("#cycleValue").inner_text()
            assert int(cycle_before) >= 1
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="Compañía").click()
            page.wait_for_selector("text=Objetivo E2E web")
            assert int(page.locator("#cycleValue").inner_text()) >= int(cycle_before)
            stored = page.evaluate("WebStore.load().then(s => ({goals:s.goals.length, cycle:s.cycle}))")
            assert stored["goals"] >= 1 and stored["cycle"] >= 1
            page.evaluate("navigator.serviceWorker.ready")
            page.context.set_offline(True)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("text=Objetivo E2E web")
            page.context.set_offline(False)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(100)
            dimensions = page.evaluate("({width:document.documentElement.scrollWidth, viewport:innerWidth})")
            assert dimensions["width"] <= dimensions["viewport"], dimensions
            assert page.get_by_role("button", name="Flota").is_visible()
            assert not errors and not failed and not bad, (errors, failed, bad)
        finally:
            browser.close()
