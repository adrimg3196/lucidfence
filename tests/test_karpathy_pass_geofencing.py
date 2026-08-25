"""Regresiones de la pasada Karpathy sobre el núcleo de geofencing (2026-08-25).

Dos bugs reales confirmados por verificación adversarial y una asunción fijada:

1. `sig_device_health` convertía compliant=None (el UEM nunca lo afirmó) en
   False con bool(), sumando +25 de riesgo con la razón FABRICADA "dispositivo
   no conforme". Violaba el invariante del repo: desconocido nunca penaliza.
   La línea vecina de encryption ya lo hacía bien — compliant se saltó el patrón.

2. `Engine._fire_actions` resolvía la cerca desde cur_key, que al salir es
   "None:outside": las acciones on_exit y on_unknown configuradas en una
   geocerca NO SE DISPARABAN JAMÁS. El admin configuraba "avísame al salir
   del almacén" y el aviso nunca llegaba. El único test previo cubría el CRUD
   de la configuración, no el disparo.

3. Borde exacto del círculo: distancia == radio cuenta como DENTRO (<=). Se
   fija con test para que un cambio accidental a < no pase en silencio.

Ejecuta: python3 tests/run_tests.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.policies import sig_device_health  # noqa: E402
from lucidfence.core.fences import Fence  # noqa: E402
from lucidfence.core.geo import Point, haversine_m  # noqa: E402
from lucidfence.core.location_source import LocationReport  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


# ---- 1. compliant desconocido no penaliza --------------------------------

def test_compliant_none_no_penaliza():
    """None = el UEM nunca lo afirmó: no es evidencia de incumplimiento."""
    señal = sig_device_health({"compliant": None}, {})
    assert señal["compliant"] is True, señal
    # Y False explícito SÍ penaliza: el arreglo no puede apagar la señal real.
    señal = sig_device_health({"compliant": False}, {})
    assert señal["compliant"] is False, señal
    señal = sig_device_health({"compliant": True}, {})
    assert señal["compliant"] is True, señal


def test_compliant_none_sin_razon_fabricada_en_el_score():
    """El explain de un dispositivo con compliant=None no puede decir
    "dispositivo no conforme": esa razón sería una afirmación inventada."""
    eng = make_temp_engine()
    ctx = {"hour": 12, "shift_zones": {}, "zone_risk": {}}
    r_none = eng.risk.evaluate({"device_id": "d1", "compliant": None}, "inside", ctx)
    assert "dispositivo no conforme" not in r_none.get("reasons", []), r_none
    r_false = eng.risk.evaluate({"device_id": "d2", "compliant": False}, "inside", ctx)
    assert "dispositivo no conforme" in r_false.get("reasons", []), r_false
    assert r_false["risk_score"] > r_none["risk_score"]


# ---- 2. on_exit / on_unknown disparan sobre la cerca abandonada ----------

class _FuenteGuiada:
    """Fuente de ubicación guiada: cada fetch() devuelve el siguiente punto."""

    def __init__(self, puntos):
        self._puntos = list(puntos)

    def fetch(self):
        lat, lng = self._puntos.pop(0) if self._puntos else self._puntos_final
        self._puntos_final = (lat, lng)
        return [LocationReport(device_id="dev-karpathy", name="Guiado",
                               platform="android", status="active",
                               compliant=True, lat=lat, lng=lng)]


def _engine_con_cerca(acciones):
    eng = make_temp_engine()
    eng.routes = []
    eng.fences = []
    eng.fence_by_id = {}
    f = eng.add_fence({
        "name": "Almacén Karpathy", "type": "circle",
        "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
        "actions": acciones,
    })
    return eng, f


def test_on_exit_dispara_al_abandonar_la_cerca():
    eng, f = _engine_con_cerca([
        {"action": "notify", "when": "on_exit", "params": {"msg": "Salida"}},
    ])
    # Ciclo 1: dentro (centro exacto). Ciclo 2: a ~11 km — fuera.
    eng.source = _FuenteGuiada([(40.5, -3.7), (40.6, -3.7)])
    eng.run_once()
    dentro = eng.store.snapshot()["dev-karpathy"]
    assert dentro.fence_state == "inside" and dentro.inside_fence == f.id, dentro
    eng.run_once()
    fuera = eng.store.snapshot()["dev-karpathy"]
    assert fuera.fence_state == "outside", fuera
    assert any(a.get("trigger") == "on_exit"
               and str(a.get("policy_name", "")).startswith("fence:")
               and a.get("fence_id") == f.id
               for a in eng._cycle_actions), (
        f"on_exit no disparó al salir de la cerca: {eng._cycle_actions}")


def test_on_unknown_dispara_al_perder_senal_dentro():
    eng, f = _engine_con_cerca([
        {"action": "notify", "when": "on_unknown", "params": {"msg": "Sin señal"}},
    ])
    eng.source = _FuenteGuiada([(40.5, -3.7), (None, None)])
    eng.run_once()
    eng.run_once()
    perdido = eng.store.snapshot()["dev-karpathy"]
    assert perdido.fence_state == "unknown", perdido
    assert eng._cycle_actions, "on_unknown no disparó al perder señal dentro de la cerca"


def test_on_enter_sigue_disparando_regresion():
    eng, f = _engine_con_cerca([
        {"action": "notify", "when": "on_enter", "params": {"msg": "Entrada"}},
    ])
    eng.source = _FuenteGuiada([(40.6, -3.7), (40.5, -3.7)])
    eng.run_once()
    eng.run_once()
    assert eng._cycle_actions, "on_enter dejó de disparar (regresión del arreglo on_exit)"


def test_sin_cerca_previa_on_exit_no_dispara_en_falso():
    """Primer avistamiento fuera de toda cerca: no hay cerca abandonada, así
    que on_exit no tiene sobre qué disparar. El arreglo no puede inventarla."""
    eng, f = _engine_con_cerca([
        {"action": "notify", "when": "on_exit", "params": {"msg": "Salida"}},
    ])
    eng.source = _FuenteGuiada([(40.6, -3.7), (40.61, -3.7)])
    eng.run_once()
    eng.run_once()
    assert not eng._cycle_actions, (
        f"on_exit disparó sin haber estado nunca dentro: {eng._cycle_actions}")


# ---- 3. borde exacto del círculo: inclusivo ------------------------------

def test_borde_exacto_del_circulo_es_inclusivo():
    centro = Point(lat=40.5, lng=-3.7)
    f = Fence(id="f-borde", name="Borde", type="circle", center=centro, radius_m=0.0)
    assert f.contains(centro), "distancia 0 == radio 0 debe contar como dentro (<=)"
    f2 = Fence(id="f-borde2", name="Borde2", type="circle", center=centro, radius_m=300.0)
    borde = Point(lat=40.5027, lng=-3.7)  # ~300 m al norte
    d = haversine_m(borde, centro)
    f2.radius_m = d  # el radio EXACTO a ese punto
    assert f2.contains(borde), f"borde exacto (d == radio) quedó fuera: d={d}"
