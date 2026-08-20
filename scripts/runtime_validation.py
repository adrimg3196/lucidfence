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

        # ============ 2b. Lockdown Mode como postura (Apple DDM OS 27) ======
        # Prueba el camino en vivo: lockdown_mode=False produce la señal
        # lockdown_mode_off y sube el riesgo con razón textual; lockdown_mode
        # desconocido (None) NO penaliza (desconocido nunca inventa riesgo).
        print("\n== Lockdown Mode posture (readback DDM OS 27) ==")
        from lucidfence.core.policies import RiskEngine, sig_device_posture
        rk = RiskEngine()
        dev_off = {"device_id": "ld-off", "lockdown_mode": False, "fence_state": "outside"}
        dev_unk = {"device_id": "ld-unk", "lockdown_mode": None, "fence_state": "outside"}
        post_off = sig_device_posture(dev_off, {})
        post_unk = sig_device_posture(dev_unk, {})
        risk_off = rk.evaluate(dev_off, "outside", {})
        risk_unk = rk.evaluate(dev_unk, "outside", {})
        off_reason = "Lockdown Mode desactivado" in risk_off.get("reasons", [])
        unk_reason = "Lockdown Mode desactivado" in risk_unk.get("reasons", [])
        check("lockdown_mode=False -> señal + riesgo con razón; None no penaliza",
              post_off.get("lockdown_mode_off") is True
              and post_unk.get("lockdown_mode_off") is False
              and off_reason and not unk_reason
              and risk_off["risk_score"] > risk_unk["risk_score"],
              f"off_signal={post_off.get('lockdown_mode_off')}, unk_signal={post_unk.get('lockdown_mode_off')}, "
              f"off_reason={off_reason}, unk_reason={unk_reason}, "
              f"score_off={risk_off['risk_score']}, score_unk={risk_unk['risk_score']}")

        # ============ 2c. Enrolment supervision como postura (DDM OS 27) ====
        # Camino en vivo: supervised=False -> señal unsupervised + riesgo con
        # razón textual; supervised desconocido (None) NO penaliza; True tampoco.
        print("\n== Enrolment supervision posture (readback DDM OS 27) ==")
        dev_uns = {"device_id": "sup-off", "supervised": False, "fence_state": "outside"}
        dev_sup = {"device_id": "sup-on", "supervised": True, "fence_state": "outside"}
        dev_sunk = {"device_id": "sup-unk", "supervised": None, "fence_state": "outside"}
        post_uns = sig_device_posture(dev_uns, {})
        post_sup = sig_device_posture(dev_sup, {})
        post_sunk = sig_device_posture(dev_sunk, {})
        risk_uns = rk.evaluate(dev_uns, "outside", {})
        risk_sup = rk.evaluate(dev_sup, "outside", {})
        risk_sunk = rk.evaluate(dev_sunk, "outside", {})
        _sup_reason = "dispositivo sin supervisión (enrolamiento personal)"
        check("supervised=False -> señal + riesgo con razón; None/True no penalizan",
              post_uns.get("unsupervised") is True
              and post_sunk.get("unsupervised") is False
              and post_sup.get("unsupervised") is False
              and _sup_reason in risk_uns.get("reasons", [])
              and _sup_reason not in risk_sunk.get("reasons", [])
              and _sup_reason not in risk_sup.get("reasons", [])
              and risk_uns["risk_score"] > risk_sunk["risk_score"]
              and risk_sunk["risk_score"] == risk_sup["risk_score"],
              f"uns={post_uns.get('unsupervised')}, unk={post_sunk.get('unsupervised')}, "
              f"on={post_sup.get('unsupervised')}, score_uns={risk_uns['risk_score']}, "
              f"score_unk={risk_sunk['risk_score']}, score_on={risk_sup['risk_score']}")

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

        # ============ 3b. Enforcement: rollout seguro por defecto ===========
        print("\n== Enforcement (observe por defecto, wipe con doble llave) ==")
        s, st_full, _ = http_req("GET", "/api/status", cookie=cookie)
        enf = (st_full or {}).get("enforcement") or {}
        check("status expone enforcement y arranca en observe",
              s == 200 and enf.get("mode") == "observe" and enf.get("allow_wipe") is False,
              f"http={s}, enforcement={enf}")

        # Editar la fase desde el dashboard: POST /api/settings/enforcement con
        # engine:config cambia el modo y /api/settings/status lo refleja tras el
        # reload del engine. Se revierte a observe para no alterar los checks
        # siguientes (que asumen el rollout seguro por defecto).
        s, sw, _ = http_req("POST", "/api/settings/enforcement",
                            cookie=cookie, body={"mode": "enforce"})
        s2, st_after, _ = http_req("GET", "/api/settings/status", cookie=cookie)
        enf_after = (st_after or {}).get("enforcement") or {}
        check("POST /api/settings/enforcement cambia el modo y status lo refleja",
              s == 200 and sw.get("enforcement", {}).get("mode") == "enforce"
              and s2 == 200 and enf_after.get("mode") == "enforce",
              f"post={s}/{sw.get('enforcement')}, status={s2}/{enf_after.get('mode')}")
        s, sinv, _ = http_req("POST", "/api/settings/enforcement",
                              cookie=cookie, body={"mode": "no-such-mode"})
        check("modo de enforcement inválido rechazado con 400", s == 400,
              f"http={s}, body={sinv}")
        http_req("POST", "/api/settings/enforcement", cookie=cookie, body={"mode": "observe"})

        s, wres, _ = http_req("POST", f"/api/devices/{first_dev}/command",
                              cookie=cookie, body={"action": "wipe"})
        check("wipe en observe queda en dry-run (jamás toca el dispositivo)",
              s == 200 and wres.get("dry_run") is True and not wres.get("blocked"),
              f"http={s}, dry_run={wres.get('dry_run')}, blocked={wres.get('blocked')}")

        s, cres, _ = http_req("POST", f"/api/devices/{first_dev}/command",
                              cookie=cookie,
                              body={"action": "set_compliance",
                                    "params": {"compliant": False}})
        check("set_compliance aceptado por la API de comandos",
              s == 200 and cres.get("ok") is True and cres.get("action") == "set_compliance",
              f"http={s}, adapter={cres.get('adapter')}, ok={cres.get('ok')}")

        # ============ 3c. Multi-UEM: registrar un provider en vivo ===========
        # El flujo Admin-value de flota mixta: registrar un UEM (con su etiqueta
        # de segmento) con engine:config y verificar que el listado lo refleja.
        # Se usa el provider 'simulation' (mock offline, sin credenciales) para
        # no exigir tokens reales, y se limpia al final.
        print("\n== Multi-UEM (POST /api/providers registra y GET lo lista) ==")
        s, preg, _ = http_req("POST", "/api/providers", cookie=cookie,
                              body={"name": "simulation", "segment": "portátiles"})
        s2, plist, _ = http_req("GET", "/api/providers", cookie=cookie)
        provs = (plist or {}).get("providers") or []
        sim = next((p for p in provs if p.get("name") == "simulation"), None)
        check("POST /api/providers registra y GET lo lista con su segmento",
              s == 200 and preg.get("ok") is True and s2 == 200
              and sim is not None and sim.get("segment") == "portátiles",
              f"post={s}/{preg.get('ok')}, get={s2}, segment={(sim or {}).get('segment')}")
        s, pinv, _ = http_req("POST", "/api/providers", cookie=cookie,
                             body={"name": "no_tal_uem"})
        check("provider no soportado rechazado con 400", s == 400,
              f"http={s}, body={pinv}")
        http_req("DELETE", "/api/providers/simulation", cookie=cookie)

        # ============ 3d. RBAC gestionable: ver miembros y cambiar un rol =====
        # El ciclo Admin-value nº3: el propietario da de alta un miembro, GET
        # /api/members lo lista, POST /api/members/role le cambia el rol en vivo,
        # y can() del backend cambia en consecuencia (operator sí puede
        # engine:run, viewer no). El guardarraíl del último owner se ejercita.
        print("\n== RBAC (GET /api/members + POST /api/members/role) ==")
        from lucidfence.saas.auth import AuthStore
        rbac_email = f"rbac-runtime-{int(time.time())}@demo.test"
        http_req("POST", "/api/users", cookie=cookie,
                 body={"email": rbac_email, "name": "RBAC RT", "role": "operator"})
        s, listing, _ = http_req("GET", "/api/members", cookie=cookie)
        member = next((m for m in (listing or {}).get("members", []) if m["email"] == rbac_email), None)
        list_ok = s == 200 and member is not None and member.get("role") == "operator" \
            and member.get("role_label") == "Operador" \
            and all("pw_hash" not in m and "pw_salt" not in m for m in listing.get("members", []))
        check("GET /api/members lista con rol+label y sin secretos", list_ok,
              f"http={s}, miembro={rbac_email}, rol={(member or {}).get('role')}")

        s, chg, _ = http_req("POST", "/api/members/role", cookie=cookie,
                             body={"email": rbac_email, "role": "viewer"})
        s2, listing2, _ = http_req("GET", "/api/members", cookie=cookie)
        now_role = {m["email"]: m["role"] for m in (listing2 or {}).get("members", [])}.get(rbac_email)
        # can() del backend refleja el cambio: operator tiene engine:run, viewer no.
        can_flip = AuthStore.can("operator", "engine:run") and not AuthStore.can("viewer", "engine:run")
        check("POST /api/members/role cambia el rol, GET lo refleja y can() cambia",
              s == 200 and chg.get("ok") and chg.get("member", {}).get("role") == "viewer"
              and s2 == 200 and now_role == "viewer" and can_flip,
              f"post={s}/{chg.get('member', {}).get('role')}, get_role={now_role}, can_flip={can_flip}")

        # rol inválido -> 400
        s, rinv, _ = http_req("POST", "/api/members/role", cookie=cookie,
                             body={"email": rbac_email, "role": "root"})
        check("rol inválido rechazado con 400", s == 400, f"http={s}, body={rinv}")

        # guardarraíl: degradar al único propietario (el demo owner) -> 400
        owner_id = next((m["id"] for m in (listing or {}).get("members", []) if m["role"] == "owner"), "")
        s, gres, _ = http_req("POST", "/api/members/role", cookie=cookie,
                             body={"user_id": owner_id, "role": "operator"})
        s2, laudit, _ = http_req("GET", "/api/audit", cookie=cookie)
        audited = any(e.get("event") == "member.role.changed" for e in (laudit or {}).get("events", []))
        check("guardarraíl del último owner (400) y cambio auditado",
              s == 400 and s2 == 200 and audited,
              f"http={s}, guardrail_ok={s == 400}, member.role.changed_en_audit={audited}")

        # ---- Auditoría visible en el dashboard (GET /api/audit) ----
        # La tarjeta "Registro de auditoría" renderiza tal cual esta respuesta:
        # eventos + verdicto de integridad + export CEF alineado 1:1.
        print("\n== Auditoría visible (GET /api/audit: events + integrity + cef) ==")
        s, adt, _ = http_req("GET", "/api/audit", cookie=cookie)
        ev = (adt or {}).get("events", [])
        integ = (adt or {}).get("integrity", {})
        cef = (adt or {}).get("cef", [])
        check("GET /api/audit devuelve cadena íntegra, eventos y CEF alineado",
              s == 200 and integ.get("ok") is True and len(ev) > 0 and len(cef) == len(ev),
              f"http={s}, integridad_ok={integ.get('ok')}, eventos={len(ev)}, cef={len(cef)}")

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

        # ============ 6b. Backlog #15: informe de puntos ciegos =============
        # Claim: sobre el tenant simulado, un dispositivo sin cerca (sin señal
        # utilizable) y una cerca sin dispositivos aparecen ambos en el informe.
        print("\n== Backlog #15 Puntos ciegos (GET /api/coverage) ==")
        s, cov0, _ = http_req("GET", "/api/coverage", cookie=cookie)
        res0 = (cov0 or {}).get("resumen") or {}
        shape_ok = s == 200 and all(
            k in (cov0 or {}) for k in ("devices_sin_senal", "devices_sin_reportar",
                                        "fences_vacias", "resumen"))
        check("GET /api/coverage responde con las 3 listas + resumen",
              shape_ok and res0.get("devices_total", 0) > 0,
              f"http={s}, resumen={res0}")

        # cerca vacía inyectada en vivo (mitad del Atlántico: nadie dentro)
        http_req("POST", "/api/fences", cookie=cookie,
                 body={"id": "qa-vacia", "name": "QA cerca vacia", "type": "circle",
                       "center": {"lat": 0.0, "lng": -30.0}, "radius_m": 500})
        s, cov1, _ = http_req("GET", "/api/coverage", cookie=cookie)
        vacias = [f["fence_id"] for f in (cov1 or {}).get("fences_vacias", [])]
        check("cerca sin dispositivos aparece en fences_vacias",
              s == 200 and "qa-vacia" in vacias, f"http={s}, fences_vacias={vacias}")
        http_req("DELETE", "/api/fences/qa-vacia", cookie=cookie)

        # dispositivo ciego inyectado en el estado REAL del engine local: sin
        # coordenadas -> sin_senal; sin last_seen -> sin_reportar con motivo.
        from lucidfence.core.coverage import coverage_report
        from lucidfence.core.state_store import DeviceState
        eng.store.upsert(DeviceState(device_id="dev-ciego", name="Sin señal QA", platform="android"))
        rep = coverage_report([d.to_dict() for d in eng.store.snapshot().values()], eng.fences)
        ciegos = [d["device_id"] for d in rep["devices_sin_senal"]]
        mudos = [d["device_id"] for d in rep["devices_sin_reportar"]]
        check("dispositivo sin señal listado en sin_senal y sin_reportar (sin last_seen)",
              "dev-ciego" in ciegos and "dev-ciego" in mudos
              and rep["resumen"]["coverage_percent"] < 100.0,
              f"sin_senal={ciegos}, sin_reportar={mudos}, "
              f"coverage={rep['resumen']['coverage_percent']}%")

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
        # Mini-runner stdlib (el repo es stdlib-first: sin depender de pytest).
        runner = (
            f"import sys; sys.path.insert(0, {str(fake)!r}); "
            f"import importlib.util as u; "
            f"spec = u.spec_from_file_location('t', {str(fake / 'tests' / 'test_adapter_validaqa.py')!r}); "
            "m = u.module_from_spec(spec); spec.loader.exec_module(m); "
            "fns = [getattr(m, n) for n in dir(m) if n.startswith('test_')]; "
            "[f() for f in fns]; print(f'{len(fns)} checks OK')"
        )
        test_run = subprocess.run([sys.executable, "-c", runner], cwd=fake,
                                  text=True, capture_output=True, timeout=120)
        check("CLI genera adapter y su contract test pasa",
              gen_ok and test_run.returncode == 0 and "4 checks OK" in test_run.stdout,
              f"cli_rc={cli.returncode}, tests={test_run.stdout.strip() or test_run.stderr[-120:]}")

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

        # ============ 11. CLI quickstart: del install a ver la flota ==========
        print("\n== CLI quickstart (time-to-first-value del admin) ==")
        qs_env = dict(os.environ, LUCIDFENCE_PORT="8793",
                      LUCIDFENCE_DATA_DIR=str(tmp / "qs-data"))
        qs = subprocess.run([sys.executable, "lucidfence/cli.py", "quickstart"],
                            text=True, capture_output=True, timeout=120, env=qs_env)
        s_qs = 0
        try:
            s_qs, _b, _c = http_req("GET", "/api/health", port=8793)
        except OSError:
            pass
        subprocess.run([sys.executable, "lucidfence/cli.py", "stop"],
                       text=True, capture_output=True, timeout=60, env=qs_env)
        check("CLI quickstart arranca y guía hasta la flota viva",
              qs.returncode == 0 and s_qs == 200
              and "[1/4] OK" in qs.stdout and "Abre tu flota" in qs.stdout,
              f"qs_rc={qs.returncode}, health={s_qs}")

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
