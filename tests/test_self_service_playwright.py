"""Playwright E2E: flujo self-service issue -> tenant -> vitrina.

Este test no toca GitHub ni tenants reales. Simula el issue de signup con un
payload local, crea el tenant mediante la misma operación serverless que usa el
workflow, publica un cloud_state aislado y abre static/cloud.html en Chromium
headless interceptando el fetch público para que lea ese snapshot hermético.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
STATE_URL = "https://raw.githubusercontent.com/adrimg3196/lucidfence/main/data/cloud_state.json"


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _skip(msg: str) -> None:
    print(f"  SKIP test_self_service_issue_to_tenant_to_vitrina_playwright: {msg}")


def test_self_service_issue_to_tenant_to_vitrina_playwright():
    try:
        sync_api = importlib.import_module("playwright.sync_api")
        PlaywrightError = sync_api.Error
        sync_playwright = sync_api.sync_playwright
    except Exception as exc:  # pragma: no cover - depende del entorno local/CI
        _skip(f"Playwright no disponible ({type(exc).__name__}: {exc})")
        return

    with tempfile.TemporaryDirectory(prefix="lucidfence-selfservice-e2e-") as tmp_raw:
        tmp = Path(tmp_raw)
        tenant_id = "issue-qa-playwright-42"
        issue_payload = {
            "name": "QA Playwright Logistics",
            "fleet": [
                {
                    "id": "zebra-qa-01",
                    "name": "Zebra QA 01",
                    "platform": "android",
                    "lat": 40.4168,
                    "lng": -3.7038,
                    "compliant": True,
                    "department": "Reparto",
                },
                {
                    "id": "iphone-qa-02",
                    "name": "iPhone QA 02",
                    "platform": "ios",
                    "lat": 40.4300,
                    "lng": -3.6900,
                    "compliant": False,
                    "department": "Ventas",
                },
            ],
            "fences": [
                {
                    "id": "qa-hq",
                    "name": "QA HQ",
                    "kind": "circle",
                    "center": {"lat": 40.4168, "lng": -3.7038},
                    "radius_m": 500,
                }
            ],
        }

        # issue -> tenant: misma función que ejecuta scripts/saas_api_op.py en Actions.
        api = cast(Any, _load_module(ROOT / "scripts" / "saas_api_op.py"))
        api.BASE = tmp / "data" / "cloud_tenants"
        api.create_tenant(tenant_id, issue_payload)
        tenant_dir = api.BASE / tenant_id / "data"
        assert (tenant_dir / "fleet_seed.json").exists(), "el issue no creó fleet_seed.json"
        assert (tenant_dir / "fences.json").exists(), "el issue no creó fences.json"

        # tenant -> cloud_state: publicador real, pero apuntando a un cwd temporal.
        out = tmp / "data" / "cloud_state.json"
        result = subprocess.run(
            [sys.executable, str(ROOT / "cloud_publisher.py"), "--cycles", "1", "--out", str(out)],
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        state = json.loads(out.read_text(encoding="utf-8"))
        tenants = state.get("tenants") or []
        published = [t for t in tenants if t.get("tenant") == tenant_id]
        assert published, f"tenant {tenant_id} no aparece en cloud_state.json"
        assert published[0].get("totals", {}).get("devices") == 2

        # cloud_state -> vitrina: navegador headless real sobre static/cloud.html.
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except PlaywrightError as exc:  # pragma: no cover - depende de browsers instalados
                _skip(f"Chromium/Playwright no ejecutable ({type(exc).__name__}: {exc})")
                return
            page = browser.new_page()
            page.route(
                STATE_URL,
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(state),
                ),
            )
            page.goto((ROOT / "static" / "cloud.html").as_uri(), wait_until="domcontentloaded")
            page.fill("#tenantFilter", tenant_id)
            page.wait_for_function(
                """
                ([tenantId]) => {
                  const opt = document.querySelector('#tenantSel option');
                  return opt && opt.textContent.includes(`${tenantId} — 2 dev`);
                }
                """,
                arg=[tenant_id],
                timeout=5000,
            )
            visible_text = page.locator("body").inner_text(timeout=5000)
            browser.close()

        assert tenant_id in visible_text
        assert "Zebra QA 01" in visible_text
        assert "iPhone QA 02" in visible_text
        assert "Reparto" in visible_text
        assert "Ventas" in visible_text
