"""Umbral de precisión del veredicto de geocerca (`location_max_accuracy_m`).

Hallazgo del pase experto (lente máquina de estados, 2026-09-01): el engine
decidía dentro/fuera con el punto crudo del fix e ignoraba `accuracy_m`. Un
fix de 5 km de precisión (IP gruesa, celda) "fuera" del almacén disparaba
on_exit y contaba como salida: veredicto punitivo fabricado a partir de una
evidencia que no lo sostiene. Regla del producto: desconocido nunca penaliza.

Contrato:
- Por defecto (0) nada cambia: la ubicación por red declara accuracy_m =
  radio del sitio a propósito y no debe filtrarse sin decisión del admin.
- Con umbral, un fix más impreciso es "unknown": ni on_exit, ni "outside";
  evento `location_rejected` con el motivo y contador en las stats del ciclo.
- Precisión ausente o basura nunca descarta el fix.
- La memoria de cerca (last_inside_fence) sobrevive al fix rechazado: cuando
  llega un fix preciso fuera, entonces sí dispara on_exit.

Ejecuta: python3 tests/run_tests.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.engine import Engine  # noqa: E402
from lucidfence.core.location_source import LocationReport  # noqa: E402
from helpers import make_temp_engine  # noqa: E402

CENTRO = (40.5, -3.7)
LEJOS = (40.6, -3.7)  # ~11 km


class _Fuente:
    """Cada fetch devuelve el siguiente (lat, lng, accuracy_m)."""

    def __init__(self, fixes):
        self._fixes = list(fixes)
        self._ultimo = None

    def fetch(self):
        if self._fixes:
            self._ultimo = self._fixes.pop(0)
        lat, lng, acc = self._ultimo
        return [LocationReport(device_id="dev-acc", name="Acc", platform="android",
                               status="active", compliant=True, lat=lat, lng=lng,
                               accuracy_m=acc, location_source="gps")]


def _engine(umbral=None):
    extra = {"location_max_accuracy_m": umbral} if umbral is not None else None
    eng = make_temp_engine(extra_config=extra)
    eng.routes = []
    eng.fences = []
    eng.fence_by_id = {}
    f = eng.add_fence({"id": "fence-acc", "name": "Almacén", "type": "circle",
                       "center": {"lat": CENTRO[0], "lng": CENTRO[1]}, "radius_m": 300,
                       "actions": [{"action": "notify", "when": "on_exit", "params": {}}]})
    return eng, f


def _eventos(eng, kind):
    return [e for e in eng.store.recent_events(50) if e.get("kind") == kind]


def test_sin_umbral_nada_cambia():
    eng, f = _engine()
    assert eng.location_max_accuracy_m == 0.0
    eng.source = _Fuente([(*CENTRO, 5000.0), (*LEJOS, 5000.0)])
    eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "inside"
    eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "outside"
    assert any(a.get("trigger") == "on_exit" for a in eng._cycle_actions)


def test_fix_impreciso_es_desconocido_y_no_dispara_on_exit():
    eng, f = _engine(umbral=100)
    eng.source = _Fuente([(*CENTRO, 12.0), (*LEJOS, 5000.0)])
    eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "inside"
    stats = eng.run_once()
    ds = eng.store.snapshot()["dev-acc"]
    assert ds.fence_state == "unknown", ds
    assert ds.last_inside_fence == f.id
    assert not any(a.get("trigger") == "on_exit" for a in eng._cycle_actions), eng._cycle_actions
    assert stats["location_rejected_inaccurate"] == 1, stats
    ev = _eventos(eng, "location_rejected")
    assert ev and ev[-1]["reason"] == "inaccurate" and ev[-1]["accuracy_m"] == 5000.0, ev


def test_fix_preciso_posterior_si_dispara_on_exit():
    eng, f = _engine(umbral=100)
    eng.source = _Fuente([(*CENTRO, 12.0), (*LEJOS, 5000.0), (*LEJOS, 15.0)])
    eng.run_once()
    eng.run_once()
    eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "outside"
    assert any(a.get("trigger") == "on_exit" and a.get("fence_id") == f.id
               for a in eng._cycle_actions), eng._cycle_actions


def test_precision_dentro_del_umbral_o_desconocida_no_descarta():
    eng, f = _engine(umbral=100)
    eng.source = _Fuente([(*LEJOS, 99.0), (*LEJOS, None)])
    stats = eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "outside"
    assert stats["location_rejected_inaccurate"] == 0
    eng.run_once()
    assert eng.store.snapshot()["dev-acc"].fence_state == "outside"


def test_umbral_basura_desactiva_el_filtro():
    for raw in (None, "abc", -5, float("nan"), float("inf"), 0, "0"):
        assert Engine._parse_max_accuracy(raw) == 0.0, raw
    assert Engine._parse_max_accuracy("250") == 250.0
    assert Engine._parse_max_accuracy(80.5) == 80.5
    eng, _ = _engine(umbral=50)
    for acc in ("nan", "x", float("inf"), None, 50.0):
        assert eng._location_too_inaccurate(acc) is False, acc
    assert eng._location_too_inaccurate(50.1) is True
