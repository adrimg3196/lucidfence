#!/usr/bin/env python3
"""Operaciones serverless del SaaS LucidFence sobre GitHub Actions.

Invocado por .github/workflows/saas-api.yml con env:
  ACTION     create_tenant | add_fence | remove_tenant
  TENANT_ID  slug del tenant
  PAYLOAD    JSON con los datos
  LUCIDFENCE_API_SIGNATURE  HMAC-SHA256 del mensaje "<ACTION>|<PAYLOAD>"
                            calculado por el solicitante con el secreto de
                            operador (LUCIDFENCE_API_SECRET, solo server-side).
  LUCIDFENCE_API_ROLE       scopes separados por coma que el solicitante
                            presenta (p.ej. "org:write,org:delete").
  LUCIDFENCE_API_SECRET     (server-side) secreto compartido usado para
                            verificar la firma. Si no está configurado,
                            NINGUNA petición es aceptada (fail-closed).

Seguridad (SEC t_1ff47164):
  Toda acción serverless valida (1) una firma HMAC del solicitante y
  (2) un rol/scope con privilegio vinculado a la ACTION. Sin firma válida o
  sin el scope requerido, main() RECHAZA (exit != 0) y NO ejecuta mutación
  alguna. Nadie que sólo pueda setear ACTION/TENANT_ID/PAYLOAD puede borrar
  tenants de la vitrina cloud.

Mensaje firmado:  ACTION + "|" + PAYLOAD (la cadena cruda tal cual llega en
la env var PAYLOAD). El cliente debe firmar exactamente esa concatenación.

Escribe el estado del tenant en data/cloud_tenants/<id>/data/*.json de forma
que lucidfence/core/cloud_publisher.py lo procese y lo publique en la vitrina cloud.

Paylodads:
  create_tenant:
    {"name":"Acme Logistics","fleet":[{id,name,platform,lat,lng,compliant,
      os_version,manufacturer,model,battery_level,storage_free_gb,
      storage_total_gb,department}],
     "fences":[{"id","name","kind":"circle","center":{"lat","lng"},"radius_m"}]}
  add_fence:
    {"fence":{...}}  (se añade al tenant)
"""
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = ROOT / "data" / "cloud_tenants"

# --- Auth env vars ---
SIGNATURE_ENV = "LUCIDFENCE_API_SIGNATURE"
ROLE_ENV = "LUCIDFENCE_API_ROLE"
SECRET_ENV = "LUCIDFENCE_API_SECRET"

# RBAC: cada ACTION requiere un scope con privilegio.
ACTION_REQUIRED_SCOPE = {
    "create_tenant": "org:write",
    "add_fence": "org:write",
    "remove_tenant": "org:delete",
}


def _tenant_dir(tid: str) -> Path:
    tid = (tid or "").strip().lower()
    if not tid or not tid.replace("-", "").replace("_", "").isalnum():
        raise ValueError("tenant_id inválido (solo alfanumérico, - y _)")
    return BASE / tid / "data"


def verify_request_signature(action: str, raw_payload: str, signature: str) -> bool:
    """Verifica la firma HMAC-SHA256 del solicitante.

    Mensaje = "<action>|<raw_payload>", firmado con LUCIDFENCE_API_SECRET
    (secreto server-side). Fail-closed: si falta el secreto o la firma,
    o no coinciden, devuelve False. Comparación en tiempo constante.
    """
    secret = os.environ.get(SECRET_ENV, "")
    if not secret or not signature:
        return False
    message = f"{action}|{raw_payload}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def check_authz(action: str, role: str) -> bool:
    """Devuelve True si `role` (scopes separados por coma) concede el scope
    requerido por `action`."""
    required = ACTION_REQUIRED_SCOPE.get(action)
    if not required:
        return False
    granted = [r.strip() for r in (role or "").split(",")]
    return required in granted


def authorize(action: str, raw_payload: str, role: str, signature: str) -> bool:
    """Gate completo de autorización: firma HMAC válida Y rol con el scope
    requerido por la ACTION. Sin ambos, la acción no debe ejecutarse."""
    if not verify_request_signature(action, raw_payload, signature):
        return False
    if not check_authz(action, role):
        return False
    return True


def create_tenant(tid: str, payload: dict):
    tdir = _tenant_dir(tid)
    tdir.mkdir(parents=True, exist_ok=True)
    fleet = payload.get("fleet", [])
    fences = payload.get("fences", [])
    # Coordenada de respaldo: el centro de la primera geocerca, o (0,0).
    fb = (fences[0].get("center", {}) if fences else {})
    fb_lat = fb.get("lat", 0.0)
    fb_lng = fb.get("lng", 0.0)
    seed = {"devices": [
        {"id": d.get("id", f"dev-{i}"), "name": d.get("name", f"Device {i}"),
         "platform": (d.get("platform") or "android").lower(),
         "waypoints": [{"lat": d.get("lat", fb_lat), "lng": d.get("lng", fb_lng)}],
         "compliant": d.get("compliant"),
         "os_version": d.get("os_version"), "manufacturer": d.get("manufacturer"),
         "model": d.get("model"), "battery_level": d.get("battery_level"),
         "storage_free_gb": d.get("storage_free_gb"),
         "storage_total_gb": d.get("storage_total_gb"),
         "department": d.get("department")}
        for i, d in enumerate(fleet)
    ]}
    (tdir / "fleet_seed.json").write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    (tdir / "fences.json").write_text(json.dumps({"fences": fences}, ensure_ascii=False, indent=2), encoding="utf-8")
    (tdir / "routes.json").write_text(json.dumps([]), encoding="utf-8")
    (tdir / "policies.json").write_text(json.dumps([]), encoding="utf-8")
    print(f"tenant {tid} creado con {len(fleet)} dispositivos, {len(fences)} geocercas")


def add_fence(tid: str, payload: dict):
    tdir = _tenant_dir(tid)
    fpath = tdir / "fences.json"
    if not fpath.exists():
        raise ValueError("tenant no existe; crealo primero")
    data = json.loads(fpath.read_text(encoding="utf-8"))
    fence = payload.get("fence")
    if not fence:
        raise ValueError("falta fence en payload")
    data.setdefault("fences", []).append(fence)
    fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"geocerca {fence.get('id')} añadida a {tid}")


def remove_tenant(tid: str, payload: dict):
    import shutil
    tdir = _tenant_dir(tid)
    if tdir.exists():
        shutil.rmtree(tdir.parent)
        print(f"tenant {tid} eliminado")
    else:
        print(f"tenant {tid} no existía")


def main():
    action = (os.environ.get("ACTION") or "create_tenant").strip()
    tid = os.environ.get("TENANT_ID", "")
    raw = os.environ.get("PAYLOAD", "{}") or "{}"
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(f"PAYLOAD no es JSON válido: {e}")
        sys.exit(1)

    # --- Authorization gate (SEC t_1ff47164): HMAC signature + RBAC by ACTION ---
    # Fail-closed: sin firma válida O sin el scope requerido por la ACTION,
    # NO se ejecuta ninguna mutación. Se devuelve sin salir del proceso para
    # que el llamador (test o workflow) pueda inspeccionar el estado intacto;
    # el mensaje ACCESS DENIED queda en stdout/stderr como señal de rechazo.
    signature = os.environ.get(SIGNATURE_ENV, "")
    role = os.environ.get(ROLE_ENV, "")
    if not authorize(action, raw, role, signature):
        msg = (
            "ACCESS DENIED: firma HMAC inválida o rol/scope insuficiente para "
            f"la acción '{action}'. No se ejecuta ninguna mutación."
        )
        print(msg, file=sys.stderr)
        return

    if action == "create_tenant":
        create_tenant(tid, payload)
    elif action == "add_fence":
        add_fence(tid, payload)
    elif action == "remove_tenant":
        remove_tenant(tid, payload)
    else:
        print(f"acción desconocida: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
