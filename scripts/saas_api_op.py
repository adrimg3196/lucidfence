#!/usr/bin/env python3
"""Operaciones serverless del SaaS LucidFence sobre GitHub Actions.

Invocado por .github/workflows/saas-api.yml con env:
  ACTION     create_tenant | add_fence | remove_tenant
  TENANT_ID  slug del tenant
  PAYLOAD    JSON con los datos

Escribe el estado del tenant en data/cloud_tenants/<id>/data/*.json de forma
que cloud_publisher.py lo procese y lo publique en la vitrina cloud.

Paylodads:
  create_tenant:
    {"name":"Acme Logistics","fleet":[{id,name,platform,lat,lng,compliant,
      os_version,manufacturer,model,battery_level,storage_free_gb,
      storage_total_gb,department}],
     "fences":[{"id","name","kind":"circle","center":{"lat","lng"},"radius_m"}]}
  add_fence:
    {"fence":{...}}  (se añade al tenant)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = ROOT / "data" / "cloud_tenants"


def _tenant_dir(tid: str) -> Path:
    tid = (tid or "").strip().lower()
    if not tid or not tid.replace("-", "").replace("_", "").isalnum():
        raise ValueError("tenant_id inválido (solo alfanumérico, - y _)")
    return BASE / tid / "data"


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
