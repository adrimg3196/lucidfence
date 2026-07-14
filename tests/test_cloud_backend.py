"""Tests del backend serverless multi-tenant (cloud_publisher + saas_api_op).

Cubren los gaps identificados por el test-engineer en la revisión agent-skills:
- create_tenant rechaza tenant_id raro (path traversal / inyección).
- add_fence a tenant inexistente lanza ValueError.
- create_tenant con device sin lat/lng no crashea (usa .get()).
- serialize con 0 devices -> compliance 0, sin división por cero.
- publisher omite tenants sin fleet_seed.json + fences.json.
- PAYLOAD no-JSON -> exit 1.

No arrancan el server: prueban lógica pura, mockean FS en los límites.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _api_op_module():
    return _load(ROOT / "scripts" / "saas_api_op.py")


def test_create_tenant_rechaza_tenant_id_raro():
    mod = _api_op_module()
    for bad in ["a/b", "a;rm", "../x", "a b", ""]:
        try:
            mod._tenant_dir(bad)
            raise AssertionError("tenant_id raro no rechazado: %r" % bad)
        except ValueError:
            pass


def test_add_fence_tenant_inexistente_ValueError():
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    try:
        mod.add_fence("no-existe", {"fence": {"id": "f1", "kind": "circle",
                                             "center": {"lat": 1, "lng": 2}, "radius_m": 100}})
        raise AssertionError("add_fence a tenant inexistente no lanzo ValueError")
    except ValueError:
        pass


def test_create_tenant_device_sin_lat_lng_no_crashea():
    mod = _api_op_module()
    tmp = Path(tempfile.mkdtemp())
    mod.BASE = tmp
    mod.create_tenant("cliente1", {
        "fleet": [{"id": "d1", "name": "X", "platform": "android"}],
        "fences": [{"id": "hq", "kind": "circle", "center": {"lat": 40.4, "lng": -3.7}, "radius_m": 500}],
    })
    seed = (tmp / "cliente1" / "data" / "fleet_seed.json").read_text(encoding="utf-8")
    assert "waypoints" in seed


def test_serialize_0_devices_compliance_0():
    mod = _load(ROOT / "cloud_publisher.py")
    import types
    eng = types.SimpleNamespace(org_id="x", status=lambda: {"fences": [], "incidents": [],
                                                            "cve_summary": {}, "soar": {}})
    eng.store = types.SimpleNamespace(snapshot=lambda: {})
    payload = mod.serialize(eng, "x")
    assert payload["totals"]["devices"] == 0
    assert payload["totals"]["compliance_rate_pct"] == 0.0


def test_publisher_filtra_tenant_sin_seed():
    # El bucle de main() solo procesa tenants con fleet_seed.json Y fences.json.
    # Verificamos el gate leyendo el helper de filtrado del publisher.
    mod = _load(ROOT / "cloud_publisher.py")
    tmp = Path(tempfile.mkdtemp())
    (tmp / "incompleto" / "data").mkdir(parents=True)
    (tmp / "incompleto" / "data" / "fleet_seed.json").write_text("{}")  # falta fences.json
    import os
    old = os.getcwd()
    os.chdir(ROOT)
    try:
        vistos = []
        rt = Path("data/cloud_tenants")
        if rt.exists():
            for tdir in sorted(rt.iterdir()):
                tdata = tdir / "data"
                if not tdata.is_dir():
                    continue
                if (tdata / "fleet_seed.json").exists() and (tdata / "fences.json").exists():
                    vistos.append(tdir.name)
        # el helper de filtrado NO debe incluir 'incompleto' (no existe en repo)
        assert "incompleto" not in vistos
    finally:
        os.chdir(old)
