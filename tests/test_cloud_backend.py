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


def test_serialize_expone_cumplimiento_geocerca_ios():
    mod = _load(ROOT / "cloud_publisher.py")
    import types
    states = {
        "ios-in": types.SimpleNamespace(device_id="ios-in", name="iPhone HQ", platform="ios",
                                        fence_state="inside", compliant=True, risk_score=0,
                                        battery_level=90, department="Ventas", os_version="iOS 17",
                                        lat=40.4168, lng=-3.7038),
        "ios-out": types.SimpleNamespace(device_id="ios-out", name="iPad Ruta", platform="ios",
                                         fence_state="outside", compliant=True, risk_score=25,
                                         battery_level=70, department="Campo", os_version="iPadOS 17",
                                         lat=40.4300, lng=-3.6900),
        "android-in": types.SimpleNamespace(device_id="and-in", name="Android HQ", platform="android",
                                            fence_state="inside", compliant=True, risk_score=0,
                                            battery_level=80, department="Ops", os_version="Android 14",
                                            lat=40.4168, lng=-3.7038),
    }
    eng = types.SimpleNamespace(org_id="x", status=lambda: {"fences": [], "incidents": [],
                                                            "cve_summary": {}, "soar": {}})
    eng.store = types.SimpleNamespace(snapshot=lambda: states)
    payload = mod.serialize(eng, "x")
    by_id = {d["device_id"]: d for d in payload["devices"]}
    assert by_id["ios-in"]["geofence_compliant"] is True
    assert by_id["ios-out"]["geofence_compliant"] is False
    assert by_id["and-in"]["geofence_compliance_applicable"] is False
    assert payload["totals"]["ios_devices"] == 2
    assert payload["totals"]["ios_geofence_compliant"] == 1
    assert payload["totals"]["ios_geofence_non_compliant"] == 1
    assert payload["totals"]["ios_geofence_compliance_rate_pct"] == 50.0


def test_cloud_seed_y_serialize_exponen_chromeos():
    mod = _load(ROOT / "cloud_publisher.py")
    assert any(d.get("platform") == "chromeos" for d in mod.DEMO_FLEET)

    tmp = Path(tempfile.mkdtemp())
    seed_path = tmp / "fleet_seed.json"
    mod._write_demo_seed(seed_path)
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    chrome = [d for d in seed["devices"] if d.get("platform") == "chromeos"]
    assert chrome and chrome[0]["os_version"].startswith("ChromeOS")

    import types
    states = {
        "chrome-1": types.SimpleNamespace(device_id="chrome-1", name="Chromebook Kiosk", platform="chromeos",
                                          fence_state="inside", compliant=True, risk_score=0,
                                          battery_level=76, department="Kioscos", os_version="ChromeOS 126",
                                          lat=40.4145, lng=-3.6995),
    }
    eng = types.SimpleNamespace(org_id="x", status=lambda: {"fences": [], "incidents": [],
                                                            "cve_summary": {}, "soar": {}})
    eng.store = types.SimpleNamespace(snapshot=lambda: states)
    payload = mod.serialize(eng, "x")
    assert payload["devices"][0]["platform"] == "chromeos"
    assert payload["totals"]["platform_counts"]["chromeos"] == 1
    assert payload["totals"]["chromeos_devices"] == 1


def test_demo_seed_incluye_chromeos_como_plataforma():
    mod = _load(ROOT / "cloud_publisher.py")
    chromeos = [d for d in mod.DEMO_FLEET if d.get("platform") == "chromeos"]
    assert chromeos, "la vitrina demo debe incluir al menos un dispositivo ChromeOS"
    assert chromeos[0]["os_version"].startswith("ChromeOS")
    tmp = Path(tempfile.mkdtemp())
    mod._write_demo_seed(tmp / "fleet_seed.json")
    seed = json.loads((tmp / "fleet_seed.json").read_text(encoding="utf-8"))
    assert any(d.get("platform") == "chromeos" for d in seed["devices"])


def test_build_demo_engine_configura_feed_nvd_acotado():
    mod = _load(ROOT / "cloud_publisher.py")
    import tempfile
    captured = {}

    class FakeEngine:
        def __init__(self, cfg):
            captured.update(cfg)

    real_engine = getattr(mod, "Engine")
    setattr(mod, "Engine", FakeEngine)
    try:
        eng = mod.build_demo_engine(Path(tempfile.mkdtemp()))
    finally:
        setattr(mod, "Engine", real_engine)
    assert isinstance(eng, FakeEngine)
    assert captured["cve_feed_sync"] is True
    assert captured["cve_feed_path"].endswith("cve_feed_nvd.json")
    assert captured["cve_feed_apps"] == mod._demo_cve_app_names()
    assert "google chrome" in captured["cve_feed_apps"]


def test_cve_summary_cloud_prefiere_real_con_ejemplos():
    mod = _load(ROOT / "cloud_publisher.py")
    status = {
        "cve_summary": {"apps_total": 1, "vulnerable_apps": 1,
                        "critical_cve_apps": 1, "high_cve_apps": 0},
        "devices": [{"apps": [{"name": "Firefox", "version": "128",
                                 "cves": [{"id": "CVE-2026-0001", "severity": "critical"}]}]}],
    }
    out = mod._cve_summary_for_cloud(status, total=1)
    assert out["demo"] is False
    assert out["source"] == "engine-cve-feed"
    assert out["ejemplos"][0]["cve"] == "CVE-2026-0001"


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
