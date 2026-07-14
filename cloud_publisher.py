#!/usr/bin/env python3
"""LucidFence cloud publisher — backend serverless sobre GitHub Actions.

Este módulo es el "compute" de la nube: en cada ejecución de Actions
(engine-cron, cada 15 min, o por workflow_dispatch on-demand) construye un
Engine de LucidFence en modo simulación con una flota representativa, corre
uno o varios ciclos y vuelca un snapshot plano a data/cloud_state.json.

Ese JSON es servido por GitHub Pages al dashboard estático, de modo que el
prospecto ve el producto funcionando EN VIVO, alimentado por la nube, $0 y
fuera de cualquier máquina local. Las operaciones (crear geocerca, forzar
ciclo) las dispara el agente vía gh/API o workflow_dispatch, y se reflejan
en el próximo ciclo.

Uso:
    python3 cloud_publisher.py [--cycles N] [--tenant TENANT_ID]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from saas.tenant import TenantStore  # noqa: E402
from core.engine import Engine  # noqa: E402
from core.location_source import SimulationLocationSource, LocationReport  # noqa: E402


# Flota simulada representativa (dispositivos frontline multi-plataforma).
DEMO_FLEET = [
    {"device_id": "dev-001", "name": "Samsung Tab Active5", "platform": "android",
     "lat": 40.4168, "lng": -3.7038, "os_version": "Android 14",
     "manufacturer": "Samsung", "model": "SM-G906B", "battery_level": 88,
     "compliant": True, "encryption_enabled": True, "rooted": False,
     "storage_free_gb": 48, "storage_total_gb": 64, "department": "Logística"},
    {"device_id": "dev-002", "name": "iPhone 13 Industrial", "platform": "ios",
     "lat": 40.4200, "lng": -3.7100, "os_version": "iOS 17.4",
     "manufacturer": "Apple", "model": "iPhone13,3", "battery_level": 62,
     "compliant": False, "encryption_enabled": True, "rooted": False,
     "storage_free_gb": 30, "storage_total_gb": 128, "department": "Almacén"},
    {"device_id": "dev-003", "name": "Zebra TC52", "platform": "android",
     "lat": 40.4100, "lng": -3.6950, "os_version": "android 12",
     "manufacturer": "Zebra", "model": "TC52", "battery_level": 11,
     "compliant": False, "encryption_enabled": False, "rooted": True,
     "storage_free_gb": 2, "storage_total_gb": 16, "department": "Reparto"},
    {"device_id": "dev-004", "name": "iPad Air Field", "platform": "ios",
     "lat": 40.4300, "lng": -3.6900, "os_version": "iOS 16.5",
     "manufacturer": "Apple", "model": "iPad13,1", "battery_level": 95,
     "compliant": True, "encryption_enabled": True, "rooted": False,
     "storage_free_gb": 64, "storage_total_gb": 64, "department": "Ventas"},
    {"device_id": "dev-005", "name": "Samsung XCover Pro", "platform": "android",
     "lat": 40.4050, "lng": -3.7150, "os_version": "Android 13",
     "manufacturer": "Samsung", "model": "SM-G715", "battery_level": 40,
     "compliant": True, "encryption_enabled": True, "rooted": False,
     "storage_free_gb": 20, "storage_total_gb": 64, "department": "Terreno"},
]


def _write_demo_seed(seed_path: Path):
    """Siembra la flota demo en el seed que el Engine SÍ lee (data/fleet_seed.json)."""
    seed = {"devices": [
        {"id": d["device_id"], "name": d["name"], "platform": d["platform"],
         "waypoints": [{"lat": d["lat"], "lng": d["lng"]}],
         "compliant": d["compliant"], "os_version": d["os_version"],
         "manufacturer": d["manufacturer"], "model": d["model"],
         "battery_level": d["battery_level"],
         "storage_free_gb": d["storage_free_gb"], "storage_total_gb": d["storage_total_gb"],
         "department": d["department"],
         "rooted": d.get("rooted", False), "encryption_enabled": d["encryption_enabled"],
         "os_outdated": d.get("os_outdated", False)}
        for d in DEMO_FLEET
    ]}
    seed_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")


def build_demo_engine(workdir: Path) -> Engine:
    workdir.mkdir(parents=True, exist_ok=True)
    ts = TenantStore(workdir)
    org = ts.create(name="LucidFence Cloud Demo", owner_id="cloud", plan="pro")
    tdir = ts.data_dir(org.id)

    # Geocercas demo (Madrid HQ + Almacén Central).
    fences = [
        {"id": "fence-hq", "name": "Madrid HQ", "kind": "circle",
         "center": {"lat": 40.4168, "lng": -3.7038}, "radius_m": 600},
        {"id": "fence-almacen", "name": "Almacén Central", "kind": "circle",
         "center": {"lat": 40.4200, "lng": -3.7100}, "radius_m": 400},
    ]
    (tdir / "fences.json").write_text(json.dumps({"fences": fences}), encoding="utf-8")
    (tdir / "policies.json").write_text(json.dumps([]), encoding="utf-8")
    (tdir / "routes.json").write_text(json.dumps([]), encoding="utf-8")
    # Flota demo determinista (el Engine la lee desde este seed).
    _write_demo_seed(tdir / "fleet_seed.json")

    cfg = {
        "mode": "simulation",
        "autostart": False,
        "data_dir": str(tdir),
        "org_id": org.id,
        "sim_seed_path": str(tdir / "fleet_seed.json"),
        "fences_path": str(tdir / "fences.json"),
        "routes_path": str(tdir / "routes.json"),
        "policies_path": str(tdir / "policies.json"),
        "action_cooldown_seconds": 3600,
        "incident_webhook_url": "",
    }
    return Engine(cfg)


def serialize(eng: Engine, org_id: str) -> dict:
    status = eng.status()
    snap = list(eng.store.snapshot().values())
    devices = []
    for s in snap:
        d = getattr(s, "__dict__", {})
        devices.append({
            "device_id": getattr(s, "device_id", ""),
            "name": getattr(s, "name", ""),
            "platform": getattr(s, "platform", ""),
            "fence_state": getattr(s, "fence_state", "unknown"),
            "compliant": getattr(s, "compliant", None),
            "risk_score": getattr(s, "risk_score", 0),
            "battery_level": getattr(s, "battery_level", None),
            "department": getattr(s, "department", ""),
            "os_version": getattr(s, "os_version", ""),
            "lat": getattr(s, "lat", None),
            "lng": getattr(s, "lng", None),
        })
    inside = sum(1 for d in devices if d["fence_state"] == "inside")
    outside = sum(1 for d in devices if d["fence_state"] == "outside")
    noncompliant = sum(1 for d in devices if d["compliant"] is False)
    total = len(devices)
    compliance_rate = round(100.0 * (total - noncompliant) / total, 1) if total else 0.0
    return {
        "service": "lucidfence-cloud",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "org_id": org_id,
        "mode": "simulation",
        "totals": {
            "devices": total,
            "inside": inside,
            "outside": outside,
            "non_compliant": noncompliant,
            "compliance_rate_pct": compliance_rate,
        },
        "devices": devices,
        "fences": status.get("fences", []),
        "incidents": status.get("incidents", []),
        # En modo simulación el engine no carga feeds externos; inyectamos un
        # resumen CVE/SOAR de ejemplo determinista para que la vitrina sea
        # representativa (claramente marcado como demo, no datos de tenant live).
        "cve_summary": (status.get("cve_summary") if (status.get("cve_summary") or {}).get("vulnerable_apps") else {
            "demo": True,
            "apps_total": 3 * max(1, total),
            "vulnerable_apps": max(1, total // 2),
            "critical_cve_apps": max(1, total // 3),
            "high_cve_apps": max(1, total // 2),
            "ejemplos": [
                {"app": "Chrome", "version": "120.0.0", "cve": "CVE-2024-1234", "severity": "critical"},
                {"app": "Zoom", "version": "5.17.0", "cve": "CVE-2024-5678", "severity": "high"},
            ],
        }),
        "soar": status.get("soar") or {
            "demo": True,
            "playbooks": [
                {"id": "quarantine-rooted", "name": "Poner en cuarentena dispositivo rooteado"},
                {"id": "notify-geo-exit", "name": "Alertar salida de geocerca"},
                {"id": "patch-cve-critical", "name": "Forzar parche por CVE crítico"},
            ],
            "matched": [d["device_id"] for d in devices if d["fence_state"] == "outside" or d["compliant"] is False],
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--out", default="data/cloud_state.json")
    args = ap.parse_args()

    # 1) Tenant demo determinista (siempre presente, flota fija).
    workdir = Path(tempfile.mkdtemp(prefix="lucidfence-cloud-"))
    demo_eng = build_demo_engine(workdir)
    for _ in range(max(1, args.cycles)):
        demo_eng.run_once()
        time.sleep(0.3)
    demo_payload = serialize(demo_eng, demo_eng.org_id)
    demo_payload["tenant"] = "demo"

    # 2) Tenants de la nube persistidos en el repo (creados vía saas-api.yml /
    #    agente). Directorio dedicado data/cloud_tenants/ para no mezclar con la
    #    basura de tenants de tests en data/tenants/. Cada uno tiene
    #    data/cloud_tenants/<id>/data/{fleet_seed,fences}.json
    tenants_payload = []
    repo_tenants = Path("data/cloud_tenants")
    if repo_tenants.exists():
        for tdir in sorted(repo_tenants.iterdir()):
            tdata = tdir / "data"
            if not tdata.is_dir():
                continue
            seed = tdata / "fleet_seed.json"
            fences = tdata / "fences.json"
            if not (seed.exists() and fences.exists()):
                continue
            try:
                cfg = {
                    "mode": "simulation", "autostart": False,
                    "data_dir": str(tdata), "org_id": tdir.name,
                    "sim_seed_path": str(seed),
                    "fences_path": str(fences),
                    "routes_path": str(tdata / "routes.json"),
                    "policies_path": str(tdata / "policies.json"),
                    "action_cooldown_seconds": 3600, "incident_webhook_url": "",
                }
                eng = Engine(cfg)
                for _ in range(max(1, args.cycles)):
                    eng.run_once()
                    time.sleep(0.2)
                p = serialize(eng, tdir.name)
                p["tenant"] = tdir.name
                tenants_payload.append(p)
            except Exception as exc:  # never fatal: one bad tenant shouldn't kill the run
                print(f"  [warn] tenant {tdir.name} omitido: {type(exc).__name__}: {exc}")

    # 3) Agregado global.
    all_devices = demo_payload["devices"] + [d for t in tenants_payload for d in t["devices"]]
    total = len(all_devices)
    noncompliant = sum(1 for d in all_devices if d["compliant"] is False)
    inside = sum(1 for d in all_devices if d["fence_state"] == "inside")
    outside = sum(1 for d in all_devices if d["fence_state"] == "outside")
    agg = {
        "devices": total,
        "inside": inside,
        "outside": outside,
        "non_compliant": noncompliant,
        "compliance_rate_pct": round(100.0 * (total - noncompliant) / total, 1) if total else 0.0,
    }

    payload = {
        "service": "lucidfence-cloud",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "simulation",
        "totals": agg,
        "tenants": [demo_payload] + tenants_payload,
        "devices": all_devices,
        "fences": demo_payload["fences"],
        "cve_summary": demo_payload.get("cve_summary", {}),
        "soar": demo_payload.get("soar", {}),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"cloud_state escrito: {out} ({agg['devices']} dispositivos en "
          f"{len(tenants_payload)+1} tenants, compliance={agg['compliance_rate_pct']}%)")


if __name__ == "__main__":
    main()
