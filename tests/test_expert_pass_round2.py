"""Pase experto, segunda tanda (2026-09-02): memoria de cerca sin señal,
placeholders OEM como identidad y coordenada basura de Applivery.

1. inside(A) -> unknown -> outside no disparaba on_exit(A): al persistir el
   estado "unknown" se perdía la cerca (inside_fence=None) y al reaparecer
   fuera no había cerca abandonada que resolver. DeviceState.last_inside_fence
   conserva la memoria mientras no hay señal.
2. normalize_identity aceptaba como serial/IMEI los placeholders que un UEM
   devuelve cuando no lo sabe ("To Be Filled By O.E.M.", "System Serial
   Number", "000000000000000"): dos dispositivos distintos se fusionaban.
3. Applivery: un solo dispositivo con latitud no numérica ("") hacía saltar
   float() dentro de fetch() y abortaba el ciclo de TODA la flota.

Ejecuta: python3 tests/run_tests.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.location_source import LocationReport, LiveLocationSource  # noqa: E402
from lucidfence.core.multiuem import normalize_identity  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


class _FuenteGuiada:
    def __init__(self, puntos):
        self._puntos = list(puntos)
        self._ultimo = None

    def fetch(self):
        if self._puntos:
            self._ultimo = self._puntos.pop(0)
        lat, lng = self._ultimo
        return [LocationReport(device_id="dev-r2", name="R2", platform="android",
                               status="active", compliant=True, lat=lat, lng=lng)]


def _engine_con_cerca(acciones):
    eng = make_temp_engine()
    eng.routes = []
    eng.fences = []
    eng.fence_by_id = {}
    f = eng.add_fence({"id": "fence-A", "name": "A", "type": "circle",
                       "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
                       "actions": acciones})
    return eng, f


# ---- 1. inside -> unknown -> outside dispara on_exit ------------------------

def test_perder_senal_dentro_y_reaparecer_fuera_dispara_on_exit():
    eng, f = _engine_con_cerca([{"action": "notify", "when": "on_exit", "params": {}}])
    eng.source = _FuenteGuiada([(40.5, -3.7), (None, None), (40.6, -3.7)])
    eng.run_once()
    eng.run_once()
    oscuro = eng.store.snapshot()["dev-r2"]
    assert oscuro.fence_state == "unknown" and oscuro.last_inside_fence == f.id, oscuro
    eng.run_once()
    fuera = eng.store.snapshot()["dev-r2"]
    assert fuera.fence_state == "outside" and fuera.last_inside_fence is None, fuera
    assert any(a.get("trigger") == "on_exit" and a.get("fence_id") == f.id
               for a in eng._cycle_actions), eng._cycle_actions


def test_fuera_sin_senal_y_fuera_no_inventa_on_exit():
    eng, f = _engine_con_cerca([{"action": "notify", "when": "on_exit", "params": {}}])
    eng.source = _FuenteGuiada([(40.6, -3.7), (None, None), (40.61, -3.7)])
    for _ in range(3):
        eng.run_once()
    assert not eng._cycle_actions, eng._cycle_actions


def test_senal_perdida_varios_ciclos_conserva_la_memoria():
    eng, f = _engine_con_cerca([{"action": "notify", "when": "on_exit", "params": {}}])
    eng.source = _FuenteGuiada([(40.5, -3.7), (None, None), (None, None), (None, None), (40.6, -3.7)])
    for _ in range(4):
        eng.run_once()
    assert eng.store.snapshot()["dev-r2"].last_inside_fence == f.id
    eng.run_once()
    assert any(a.get("trigger") == "on_exit" for a in eng._cycle_actions), eng._cycle_actions


# ---- 2. placeholders OEM no son identidad -----------------------------------

def test_placeholders_oem_y_ceros_no_son_identidad():
    for basura in ("To Be Filled By O.E.M.", "System Serial Number", "Default string",
                   "Not Specified", "000000000000000", "0000", "N/A", "unknown", ""):
        assert normalize_identity(basura) is None, basura
    assert normalize_identity("C02XG1ABJG5H") == "C02XG1ABJG5H"
    assert normalize_identity("35-209900-176148-1") == "352099001761481"


# ---- 3. coordenada basura de Applivery no aborta el ciclo -------------------

def test_applivery_coordenada_no_numerica_devuelve_sin_fix():
    dev = {"id": "d1", "lastLocation": {"latitude": "", "longitude": "-3.7",
                                         "date": "2026-09-02T00:00:00Z"}}
    assert LiveLocationSource._extract_last_location(dev) is None
    dev_nan = {"id": "d2", "lastLocation": {"latitude": "nan", "longitude": "-3.7"}}
    assert LiveLocationSource._extract_last_location(dev_nan) is None
    ok = {"id": "d3", "lastLocation": {"latitude": "40.5", "longitude": "-3.7"}}
    loc = LiveLocationSource._extract_last_location(ok)
    assert loc and loc["lat"] == 40.5 and loc["lng"] == -3.7
