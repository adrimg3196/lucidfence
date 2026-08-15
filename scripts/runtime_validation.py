#!/usr/bin/env python3
"""Batería de validación RUNTIME: cada claim anunciado, ejecutado de verdad.

No sustituye a la suite: la complementa. Arranca el saas_server real, un
receptor webhook real, el MCP real por stdio, y ejercita cada feature por su
interfaz pública. Imprime PASS/FAIL por claim y no se detiene al primer fallo.
"""
from __future__ import annotations

import http.client
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, evidence: str) -> None:
    RESULTS.append((name, bool(ok), evidence))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {evidence}")


PORT = 8791  # puerto propio: no chocar con una instancia real en 8765


def http_req(method, path, body=None, cookie="", port=PORT, raw=False):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    r = conn.getresponse()
    data = r.read()
    cookies = [v.split(";", 1)[0] for k, v in r.getheaders() if k.lower() == "set-cookie"]
    conn.close()
    if raw:
        return r.status, data, "; ".join(cookies)
    try:
        return r.status, json.loads(data), "; ".join(cookies)
    except Exception:
        return r.status, data.decode("utf-8", "replace"), "; ".join(cookies)


# ---------------------------------------------------------------- receptor
CAPTURED: list[dict] = []


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        CAPTURED.append({
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": self.rfile.read(length),
        })
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def main() -> int:
    os.chdir(REPO)
    tmp = Path(tempfile.mkdtemp(prefix="lf-runtime-"))
    server_proc = None
    receiver = http.server.ThreadingHTTPServer(("127.0.0.1", 9099), Receiver)
    threading.Thread(target=receiver.serve_forever, daemon=True).start()

    try:
        # ============ 1. Webhooks multi-canal: entrega HTTP REAL + firma ====
        print("\n== P0.3 Webhooks (entrega HTTP real al receptor local) ==")
        from lucidfence.core.notifier import (IncidentFanoutNotifier, NtfyNotifier,
                                              SignedWebhookNotifier, build_incident_notifiers)
        incident = {"id": "inc-rt-1", "title": "Salida de geocerca (runtime QA)",
                    "severity": "high", "device_id": "dev-rt", "device_name": "Runtime QA", "fence_id": "hq"}
        signed = SignedWebhookNotifier("http://127.0.0.1:9099/hook", secret="qa-secret")
        ok = signed.notify("open", incident)
        got = CAPTURED[-1] if CAPTURED else None
        sig_ok = bool(got) and SignedWebhookNotifier.verify(
            "qa-secret", got["body"], got["headers"].get("X-Lucidfence-Signature")
            or got["headers"].get("X-LucidFence-Signature", ""))
        payload_ok = bool(got) and json.loads(got["body"])["incident"]["id"] == "inc-rt-1"
        check("webhook firmado entregado y verificado", ok and sig_ok and payload_ok,
              f"delivered={ok}, firma_valida={sig_ok}, payload_ok={payload_ok}")

        ntfy = NtfyNotifier("http://127.0.0.1:9099/ntfy-topic", token="tk-qa")
        ok = ntfy.notify("open", incident)
        got = CAPTURED[-1]
        check("ntfy entregado con Title/Priority/Bearer",
              ok and got["headers"].get("Priority") == "4"
              and "Bearer tk-qa" in got["headers"].get("Authorization", "")
              and "[HIGH]" in got["headers"].get("Title", ""),
              f"headers={ {k: got['headers'].get(k) for k in ('Title','Priority','Authorization')} }")

        # Cableado real del Engine con la config multi-canal
        from lucidfence.core.engine import Engine
        eng_dir = tmp / "eng-webhooks"
        eng = Engine({"mode": "simulation", "dry_run": True, "data_dir": str(eng_dir),
                      "sim_seed_path": "data/fleet_seed.json",
                      "incident_webhooks": [
                          {"type": "generic", "url": "http://127.0.0.1:9099/hook", "secret": "s"},
                          {"type": "ntfy", "url": "http://127.0.0.1:9099/t"}]})
        is_fanout = isinstance(eng.incidents.notifier, IncidentFanoutNotifier)
        n_channels = len(getattr(eng.incidents.notifier, "notifiers", []))
        check("Engine cablea fan-out desde config", is_fanout and n_channels == 2,
              f"notifier={type(eng.incidents.notifier).__name__}, canales={n_channels}")

        # Incidente REAL -> webhooks: merge() es el mismo camino que usa el
        # ciclo del engine; deben llegar los dos canales del fan-out.
        before = len(CAPTURED)
        eng.incidents.merge([{"id": "inc-rt-e2e", "title": "Incidente e2e runtime",
                              "severity": "critical", "device_id": "dev-rt",
                              "device_name": "Runtime QA", "fence_id": "hq"}])
        nuevos = CAPTURED[before:]
        rutas = sorted(c["path"] for c in nuevos)
        firma_e2e = any(
            c["path"] == "/hook" and SignedWebhookNotifier.verify(
                "s", c["body"], c["headers"].get("X-Lucidfence-Signature")
                or c["headers"].get("X-LucidFence-Signature", ""))
            for c in nuevos)
        check("incidente real dispara los 2 canales del fan-out",
              rutas == ["/hook", "/t"] and firma_e2e,
              f"rutas={rutas}, firma_generic_valida={firma_e2e}")

        # ============ 2. Anti-spoofing: ciclo real + teletransporte =========
        print("\n== P0.2 Anti-spoofing (ciclos reales del engine) ==")
        r1 = eng.run_once()
        states = eng.store.snapshot()
        dev_id, st = next(iter(states.items()))
        has_field = isinstance(st.location_integrity, dict)
        check("ciclo real adjunta location_integrity", has_field,
              f"device={dev_id}, integrity={st.location_integrity}")
        # Teletransporte: retrocedemos el estado persistido a Buenos Aires hace 1 min
        st.lat, st.lng, st.country = -34.6037, -58.3816, "AR"
        from lucidfence.core.state_store import now_iso
        st.last_report_ts = now_iso()
        eng.store.upsert(st)
        eng.run_once()
        st2 = eng.store.snapshot()[dev_id]
        li = st2.location_integrity or {}
        risk_row = eng.risk.evaluate(dict(st2.to_dict()), st2.fence_state, {})
        spoof_reason = any("spoofing" in r for r in risk_row.get("reasons", []))
        check("teletransporte detectado en ciclo real",
              li.get("suspicious") is True and "impossible_speed" in (li.get("checks") or []),
              f"checks={li.get('checks')}, speed={li.get('speed_kmh')} km/h")
        check("risk engine puntúa el spoofing con razón textual", spoof_reason,
              f"reasons={[r for r in risk_row.get('reasons', []) if 'spoof' in r or 'imposible' in r]}")

        # ============ 3. Server real: arranque + sesión demo ================
        print("\n== Servidor real (saas_server.py) ==")
        env = dict(os.environ, LUCIDFENCE_DATA_DIR=str(tmp / "server-data"),
                   LUCIDFENCE_PORT=str(PORT), PYTHONUNBUFFERED="1")
        server_proc = subprocess.Popen([sys.executable, "saas_server.py"], env=env,
                                       stdout=open(tmp / "server.log", "wb"), stderr=subprocess.STDOUT)
        up = False
        for _ in range(60):
            try:
                s, _b, _c = http_req("GET", "/api/health")
                if s == 200:
                    up = True
                    break
            except OSError:
                pass
            time.sleep(0.5)
        check("servidor arranca y /api/health responde", up, f"pid={server_proc.pid}")

        s, _b, cookie = http_req("POST", "/api/auth/demo", body={})
        check("sesión demo (loopback)", s == 200 and bool(cookie), f"http={s}")

        # Dos ciclos para poblar estados y trails
        for _ in range(2):
            http_req("POST", "/api/run-once", body={}, cookie=cookie)
        s, devices, _ = http_req("GET", "/api/devices", cookie=cookie)
        dev_ok = s == 200 and isinstance(devices, list) and devices
        first_dev = devices[0]["device_id"] if dev_ok else ""
        check("flota viva vía /api/devices", dev_ok,
              f"{len(devices) if dev_ok else 0} dispositivos, integrity_presente={'location_integrity' in (devices[0] if dev_ok else {})}")

        s, risk, _ = http_req("GET", "/api/risk", cookie=cookie)
        rows = risk if isinstance(risk, list) else (risk.get("risk") or risk.get("devices") or [])
        check("riesgo explicable vía /api/risk", s == 200 and rows and rows[0].get("factors") is not None,
              f"{len(rows)} filas, top={rows[0].get('device_id') if rows else None} score={rows[0].get('score') if rows else None}")

        # ============ 4. What-if replay vía API =============================
        print("\n== P0.1 Simulador what-if (POST /api/policies/replay) ==")
        s, replay, _ = http_req("POST", "/api/policies/replay", cookie=cookie, body={
            "policy": {"id": "qa-outside", "name": "QA outside notify",
                       "when": [{"field": "fence_state", "op": "eq", "value": "outside"}],
                       "actions": [{"action": "notify", "params": {}}]}})
        check("replay responde con plan dry-run",
              s == 200 and replay.get("dry_run") is True and replay.get("points_evaluated", 0) > 0,
              f"http={s}, puntos={replay.get('points_evaluated')}, disparos={replay.get('fires_total')}, exacto={replay.get('approximation', {}).get('exact')}")

        s, replay2, _ = http_req("POST", "/api/policies/replay", cookie=cookie, body={
            "policy": {"id": "qa-outside2", "name": "QA recompute",
                       "when": [{"field": "fence_state", "op": "eq", "value": "outside"}],
                       "actions": [{"action": "notify", "params": {}}]},
            "recompute_fences": True})
        check("replay recalcula contra geocercas actuales",
              s == 200 and replay2.get("fence_state_source") == "recomputed",
              f"http={s}, source={replay2.get('fence_state_source')}")

        # ============ 5. Evidencia: export vía API + verificación offline ===
        print("\n== P1.7 Evidencia (GET /api/evidence/export) ==")
        s, report, _ = http_req("GET", "/api/evidence/export", cookie=cookie)
        from lucidfence.core.evidence_export import verify_evidence_report
        verdict = verify_evidence_report(report) if s == 200 else {"ok": False, "error": f"http {s}"}
        check("export encadenado verifica offline", s == 200 and verdict.get("ok") is True,
              f"http={s}, registros={verdict.get('records')}, chain_head={str(report.get('chain_head'))[:16] if s == 200 else '-'}…")
        if s == 200 and report.get("records"):
            tampered = json.loads(json.dumps(report))
            tampered["records"][0]["compliant"] = "manipulado"
            check("manipulación detectada offline", verify_evidence_report(tampered)["ok"] is False,
                  verify_evidence_report(tampered).get("error", ""))

        s, audit, _ = http_req("GET", "/api/audit", cookie=cookie)
        events = audit.get("events") if isinstance(audit, dict) else []
        exported = any(e.get("event") == "evidence.exported" for e in (events or []))
        integrity_ok = isinstance(audit, dict) and (audit.get("integrity") or {}).get("ok") is True
        check("el export queda en la auditoría hash-chained", s == 200 and exported and integrity_ok,
              f"http={s}, evento_presente={exported}, cadena_ok={integrity_ok}")

        # ============ 6. POIs (feature de ayer, también anunciada) ==========
        s, pois, _ = http_req("GET", "/api/pois", cookie=cookie)
        check("POIs vía /api/pois", s == 200 and isinstance(pois, list) and len(pois) >= 1,
              f"http={s}, pois={len(pois) if isinstance(pois, list) else pois}")

        # ============ 7. MCP real por stdio contra el server vivo ===========
        print("\n== P2.8 MCP explain-risk (stdio real contra el server) ==")
        rpc_in = "\n".join(json.dumps(m) for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "lucidfence_explain_risk", "arguments": {"device_id": first_dev}}},
        ]) + "\n"
        proc = subprocess.run([sys.executable, "lucidfence/mcp/lucidfence_mcp.py"],
                              input=rpc_in, text=True, capture_output=True, timeout=60,
                              env=dict(os.environ, LUCIDFENCE_URL=f"http://127.0.0.1:{PORT}"))
        lines = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
        tools = {t["name"] for t in lines[1]["result"]["tools"]}
        explain = json.loads(lines[2]["result"]["content"][0]["text"])
        check("tool listada y explicación real devuelta",
              "lucidfence_explain_risk" in tools and explain.get("device_id") == first_dev
              and "why" in explain and "score" in explain,
              f"device={explain.get('device_id')}, score={explain.get('score')}, why={(explain.get('why') or ['<sin why>'])[:2]}, error={explain.get('error')}")

        smoke_in = "\n".join(json.dumps(m) for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "lucidfence_status", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lucidfence_list_devices", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lucidfence_list_pois", "arguments": {}}},
        ]) + "\n"
        smoke = subprocess.run([sys.executable, "lucidfence/mcp/lucidfence_mcp.py"],
                               input=smoke_in, text=True, capture_output=True, timeout=60,
                               env=dict(os.environ, LUCIDFENCE_URL=f"http://127.0.0.1:{PORT}"))
        smoke_rows = [json.loads(l) for l in smoke.stdout.splitlines() if l.strip()]
        errores = [r["id"] for r in smoke_rows[1:] if r["result"].get("isError")]
        check("MCP smoke: status/devices/pois responden sin error", not errores,
              f"llamadas={len(smoke_rows) - 1}, con_error={errores}")

        # ============ 8. Páginas servidas + banda demo ======================
        print("\n== UI servida por el server real ==")
        s1, dash, _ = http_req("GET", "/", raw=True)
        s2, landing, _ = http_req("GET", "/static/index.html", raw=True)
        s3, cloud, _ = http_req("GET", "/static/cloud.html", raw=True)
        s4, wl, _ = http_req("GET", "/static/whitelabel.html", raw=True)
        s5, web, _ = http_req("GET", "/static/web.html", raw=True)
        check("dashboard servido con banda demo", s1 == 200 and b'id="demoBanner"' in dash,
              f"http={s1}, banner={'demoBanner' in dash.decode('utf-8', 'replace')}")
        check("landing nueva servida", s2 == 200 and "Geofencing".encode() in landing
              and "—".encode() not in landing, f"http={s2}, em-dashes={landing.count('—'.encode())}")
        check("vitrina servida con CTA primero", s3 == 200 and cloud.find(b"Descargar LucidFence") < cloud.find(b'id="tenantSel"'),
              f"http={s3}")
        check("whitelabel y app web servidas", s4 == 200 and s5 == 200, f"http={s4}/{s5}")

        # ============ 9. Scaffolding CLI end-to-end =========================
        print("\n== P1.5 lucidfence adapter new (CLI real + pytest del generado) ==")
        fake = tmp / "fake-checkout"
        (fake / "lucidfence" / "core").mkdir(parents=True)
        shutil.copytree(REPO / "lucidfence" / "core" / "adapters", fake / "lucidfence" / "core" / "adapters",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # __init__ vacíos: el árbol falso no incluye todo el paquete, y los
        # __init__ reales importan módulos que aquí no existen (bug del arnés
        # detectado en la primera pasada, no del producto).
        for init in ("lucidfence/__init__.py", "lucidfence/core/__init__.py"):
            (fake / init).write_text("", encoding="utf-8")
        (fake / "tests").mkdir()
        shutil.copy(REPO / "tests" / "test_sdk_contract.py", fake / "tests" / "test_sdk_contract.py")
        cli = subprocess.run([sys.executable, str(REPO / "lucidfence" / "cli.py"), "adapter", "new", "validaqa"],
                             cwd=fake, text=True, capture_output=True, timeout=60)
        gen_ok = cli.returncode == 0 and (fake / "lucidfence" / "core" / "adapters" / "validaqa.py").is_file()
        pytest_run = subprocess.run([sys.executable, "-m", "pytest", "tests/test_adapter_validaqa.py", "-q"],
                                    cwd=fake, text=True, capture_output=True, timeout=120,
                                    env=dict(os.environ, PYTHONPATH=str(fake)))
        check("CLI genera adapter y su contract test pasa",
              gen_ok and pytest_run.returncode == 0 and "4 passed" in pytest_run.stdout,
              f"cli_rc={cli.returncode}, pytest={pytest_run.stdout.strip().splitlines()[-1] if pytest_run.stdout else pytest_run.stderr[-120:]}")

        # ============ 10. CLI lifecycle: start -> status -> stop =============
        print("\n== CLI (claim de la landing: arranque local en un comando) ==")
        cli_env = dict(os.environ, LUCIDFENCE_PORT="8792",
                       LUCIDFENCE_DATA_DIR=str(tmp / "cli-data"))
        start = subprocess.run([sys.executable, "lucidfence/cli.py", "start"],
                               text=True, capture_output=True, timeout=120, env=cli_env)
        s_cli, _b, _c = (0, None, None)
        try:
            s_cli, _b, _c = http_req("GET", "/api/health", port=8792)
        except OSError:
            pass
        status = subprocess.run([sys.executable, "lucidfence/cli.py", "status"],
                                text=True, capture_output=True, timeout=60, env=cli_env)
        stop = subprocess.run([sys.executable, "lucidfence/cli.py", "stop"],
                              text=True, capture_output=True, timeout=60, env=cli_env)
        down = False
        for _ in range(10):
            try:
                http_req("GET", "/api/health", port=8792)
            except OSError:
                down = True
                break
            time.sleep(0.5)
        check("CLI start/status/stop contra servidor real",
              start.returncode == 0 and s_cli == 200 and status.returncode == 0
              and "activo" in status.stdout and stop.returncode == 0 and down,
              f"start_rc={start.returncode}, health={s_cli}, status='{status.stdout.splitlines()[0] if status.stdout else ''}', stop_rc={stop.returncode}, apagado={down}")

    finally:
        receiver.shutdown()
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _n, ok, _e in RESULTS if ok)
    print(f"\n=== RUNTIME: {passed}/{len(RESULTS)} claims validados ===")
    for name, ok, _ev in RESULTS:
        if not ok:
            print(f"  FALLO: {name}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
