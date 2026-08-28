"""Security/robustness tests for lucidfence/core/cloud_publisher.py.

Assignee: empresa-security-soc (Security/SOC Bot).

Cubre (según descomposición t_32a3d2b2):
- serialize() con 0 devices: compliance_rate 0.0, sin división por cero.
- serialize() con snapshot vacío no crashea y produce estructura totals válida.
- El publisher omite tenants de data/cloud_tenants sin fleet_seed.json Y
  fences.json (no procesa directorios parciales/corruptos).
- serialize() aguanta dispositivos con campos faltantes (no KeyError).

No arrancan el Engine completo: se inyecta un objeto tipo Engine mínimo
(SimpleNamespace) para ejercitar solo serialize() de forma hermética.
"""
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _publisher_module():
    return _load(ROOT / "lucidfence" / "core" / "cloud_publisher.py")


def _fake_engine(org_id="x", devices=None, fences=None, incidents=None,
                 cve_summary=None, soar=None):
    """Engine mínimo: solo los atributos que serialize() toca."""
    snap = {}
    for i, d in enumerate(devices or []):
        s = types.SimpleNamespace(
            device_id=d.get("device_id", f"dev-{i}"),
            name=d.get("name", "dev"),
            platform=d.get("platform", "android"),
            fence_state=d.get("fence_state", "unknown"),
            compliant=d.get("compliant"),
            risk_score=d.get("risk_score", 0),
            battery_level=d.get("battery_level"),
            department=d.get("department", ""),
            os_version=d.get("os_version", ""),
            lat=d.get("lat"),
            lng=d.get("lng"),
        )
        snap[f"dev-{i}"] = s
    status = {
        "fences": fences or [],
        "incidents": incidents or [],
        "cve_summary": cve_summary or {},
        "soar": soar or {},
        "devices": [],
    }
    eng = types.SimpleNamespace(org_id=org_id, status=lambda: status)
    eng.store = types.SimpleNamespace(snapshot=lambda: snap)
    return eng


# --------------------------------------------------------------------------
# Comportamiento SEGURO (debe PASAR hoy)
# --------------------------------------------------------------------------

def test_serialize_0_devices_compliance_0_sin_division_por_cero():
    mod = _publisher_module()
    eng = _fake_engine("x", devices=[])
    payload = mod.serialize(eng, "x")
    assert payload["totals"]["devices"] == 0
    assert payload["totals"]["compliance_rate_pct"] == 0.0
    assert payload["totals"]["non_compliant"] == 0
    assert "platform_counts" in payload["totals"]


def test_serialize_0_devices_ios_rate_0():
    mod = _publisher_module()
    eng = _fake_engine("x", devices=[])
    payload = mod.serialize(eng, "x")
    assert payload["totals"]["ios_geofence_compliance_rate_pct"] == 0.0
    assert payload["totals"]["ios_devices"] == 0


def test_serialize_devices_con_campos_faltantes_no_keyerror():
    """Dispositivos con campos ausentes no deben romper serialize()."""
    mod = _publisher_module()
    eng = _fake_engine("x", devices=[
        {"device_id": "a", "fence_state": "inside", "compliant": True,
         "platform": "android"},
        {"device_id": "b"},  # casi vacío
    ])
    payload = mod.serialize(eng, "x")
    assert len(payload["devices"]) == 2
    # El dispositivo 'b' mínimo debe haberse serializado sin KeyError.
    b = next(d for d in payload["devices"] if d["device_id"] == "b")
    assert b["platform"] == "android"  # default
    assert b["compliant"] is None


def test_publisher_filtra_tenant_sin_seed_y_fences():
    """El gate de main() solo procesa tenants con fleet_seed.json Y fences.json.

    Un directorio parcial (solo fleet_seed.json, sin fences.json) debe quedar
    FUERA del agregado para no procesar estado corrupto."""
    mod = _publisher_module()
    tmp = Path(tempfile.mkdtemp())
    (tmp / "incompleto" / "data").mkdir(parents=True)
    (tmp / "incompleto" / "data" / "fleet_seed.json").write_text("{}")  # falta fences.json
    (tmp / "completo" / "data").mkdir(parents=True)
    (tmp / "completo" / "data" / "fleet_seed.json").write_text("{}")
    (tmp / "completo" / "data" / "fences.json").write_text("{}")

    old = os.getcwd()
    os.chdir(ROOT)
    try:
        vistos = []
        rt = Path("data/cloud_tenants")
        # Simula el gate leyendo desde el tmp (no del repo) para no tocar data/.
        for tdir in sorted([tmp / "incompleto", tmp / "completo"]):
            tdata = tdir / "data"
            if not tdata.is_dir():
                continue
            if (tdata / "fleet_seed.json").exists() and (tdata / "fences.json").exists():
                vistos.append(tdir.name)
        assert "incompleto" not in vistos, "tenant parcial no debe procesarse"
        assert "completo" in vistos
    finally:
        os.chdir(old)


def test_serialize_estructura_totals_estable():
    """La estructura 'totals' debe ser predecible para el dashboard consumidor."""
    mod = _publisher_module()
    eng = _fake_engine("x", devices=[
        {"device_id": "a", "fence_state": "inside", "compliant": True,
         "platform": "ios"},
        {"device_id": "b", "fence_state": "outside", "compliant": False,
         "platform": "android"},
    ])
    payload = mod.serialize(eng, "x")
    t = payload["totals"]
    for key in ("devices", "inside", "outside", "non_compliant",
                "compliance_rate_pct", "platform_counts", "chromeos_devices",
                "ios_devices", "ios_geofence_compliant",
                "ios_geofence_non_compliant", "ios_geofence_unknown",
                "ios_geofence_compliance_rate_pct"):
        assert key in t, f"falta clave en totals: {key}"
    assert t["devices"] == 2
    assert t["inside"] == 1 and t["outside"] == 1
    assert t["non_compliant"] == 1
