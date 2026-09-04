"""Máquina de estados de geocercas: pase experto 2026-09-01.

Tres defectos reproducidos contra el Engine real y confirmados por
verificación adversarial (reproducción + intención de diseño):

1. Salto directo cerca A -> cerca B en un ciclo: solo disparaba on_enter(B);
   los on_exit de A (la cerca ABANDONADA) se perdían en silencio.
2. on_unknown aceptaba y despachaba acciones destructivas (lock/wipe/...):
   en enforce, perder GPS dentro de una cerca emitía una orden real.
   Desconocido nunca penaliza: el engine las salta y validate_fences las
   rechaza al configurar.
3. StateStore._load descartaba la fila entera si el JSON traía una clave
   que el DeviceState actual no conoce (build nuevo + rollback): toda la
   flota "recién vista" y on_enter re-disparado en masa.

Ejecuta: python3 tests/run_tests.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.fences import Fence, validate_fences  # noqa: E402
from lucidfence.core.location_source import LocationReport  # noqa: E402
from lucidfence.core.state_store import DeviceState, StateStore  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


class _FuenteGuiada:
    def __init__(self, puntos):
        self._puntos = list(puntos)
        self._ultimo = None

    def fetch(self):
        if self._puntos:
            self._ultimo = self._puntos.pop(0)
        lat, lng = self._ultimo
        return [LocationReport(device_id="dev-fsm", name="FSM", platform="android",
                               status="active", compliant=True, lat=lat, lng=lng)]


def _engine_vacio():
    eng = make_temp_engine()
    eng.routes = []
    eng.fences = []
    eng.fence_by_id = {}
    return eng


def _inyectar(eng, raw):
    """Cerca directa al engine (sin validate_fences) para poder probar el
    guardarraíl del engine con una configuración que la validación rechaza."""
    f = Fence.from_raw(raw)
    eng.fences.append(f)
    eng.fence_by_id[f.id] = f
    return f


# ---- 1. A -> B dispara on_exit(A) y luego on_enter(B) ----------------------

def test_salto_directo_entre_cercas_dispara_on_exit_de_la_abandonada():
    eng = _engine_vacio()
    a = eng.add_fence({"id": "fence-A", "name": "A", "type": "circle",
                       "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
                       "actions": [{"action": "notify", "when": "on_exit", "params": {}},
                                   {"action": "notify", "when": "on_enter", "params": {}}]})
    b = eng.add_fence({"id": "fence-B", "name": "B", "type": "circle",
                       "center": {"lat": 40.6, "lng": -3.7}, "radius_m": 300,
                       "actions": [{"action": "notify", "when": "on_enter", "params": {}}]})
    eng.source = _FuenteGuiada([(40.5, -3.7), (40.6, -3.7)])
    eng.run_once()
    eng.run_once()
    assert eng.store.snapshot()["dev-fsm"].inside_fence == b.id
    disparos = [(x.get("trigger"), x.get("fence_id")) for x in eng._cycle_actions]
    assert ("on_exit", a.id) in disparos, disparos
    assert ("on_enter", b.id) in disparos, disparos
    assert disparos.index(("on_exit", a.id)) < disparos.index(("on_enter", b.id)), disparos


def test_reentrada_en_la_misma_cerca_no_dispara_on_exit():
    eng = _engine_vacio()
    a = eng.add_fence({"id": "fence-A", "name": "A", "type": "circle",
                       "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
                       "actions": [{"action": "notify", "when": "on_exit", "params": {}}]})
    eng.source = _FuenteGuiada([(40.5, -3.7), (40.5001, -3.7)])
    eng.run_once()
    eng.run_once()
    assert eng.store.snapshot()["dev-fsm"].inside_fence == a.id
    assert not any(x.get("trigger") == "on_exit" for x in eng._cycle_actions), eng._cycle_actions


# ---- 2. on_unknown jamás despacha una acción destructiva -------------------

def test_on_unknown_no_despacha_lock_pero_si_notify():
    eng = _engine_vacio()
    _inyectar(eng, {"id": "fence-U", "name": "U", "type": "circle",
                    "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
                    "actions": [{"action": "lock", "when": "on_unknown", "params": {}},
                                {"action": "notify", "when": "on_unknown", "params": {}}]})
    eng.source = _FuenteGuiada([(40.5, -3.7), (None, None)])
    eng.run_once()
    eng.run_once()
    assert eng.store.snapshot()["dev-fsm"].fence_state == "unknown"
    acciones = [(x.get("trigger"), x.get("action")) for x in eng._cycle_actions]
    assert ("on_unknown", "notify") in acciones, acciones
    assert not any(act in {"lock", "wipe", "clear_passcode", "reboot"} for _, act in acciones), acciones


def test_validate_fences_rechaza_destructiva_en_on_unknown():
    mala = Fence.from_raw({"id": "u", "name": "u", "type": "circle",
                           "center": {"lat": 0, "lng": 0}, "radius_m": 10,
                           "actions": [{"action": "wipe", "when": "on_unknown"}]})
    assert any("on_unknown" in p for p in validate_fences([mala]))
    buena = Fence.from_raw({"id": "b", "name": "b", "type": "circle",
                            "center": {"lat": 0, "lng": 0}, "radius_m": 10,
                            "actions": [{"action": "notify", "when": "on_unknown"},
                                        {"action": "lock", "when": "on_exit"}]})
    assert validate_fences([buena]) == []


# ---- 3. una clave desconocida en device_states.json no borra la fila -------

def test_state_store_ignora_claves_desconocidas_en_vez_de_descartar_la_fila():
    d = tempfile.mkdtemp(prefix="lf-state-")
    fila = DeviceState(device_id="dev-1", name="Uno", platform="ios",
                       fence_state="inside", inside_fence="f1").to_dict()
    fila["campo_de_un_build_futuro"] = 42
    with open(os.path.join(d, "device_states.json"), "w", encoding="utf-8") as fh:
        json.dump([fila], fh)
    store = StateStore(d)
    ds = store.get("dev-1")
    assert ds is not None, "la fila con una clave extra fue descartada"
    assert ds.fence_state == "inside" and ds.inside_fence == "f1"
