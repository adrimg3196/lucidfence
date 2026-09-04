"""Geodesia de nivel producción: antimeridiano, epsilon, degenerados y NaN.

Cada test fija un defecto reproducido en el pase experto de 2026-09-01:

1. point_in_polygon hacía ray-casting plano sobre longitudes crudas: una
   geocerca que cruza el antimeridiano (lng 178 -> -178) se evaluaba como una
   banda de 356° y daba el veredicto INVERTIDO.
2. El +1e-12 del denominador no evitaba nada (el guard de paridad ya implica
   ys[j] != ys[i]) y con dy == -1e-12 provocaba ZeroDivisionError.
3. distance_to_segment_m usaba un marco equirectangular anclado en `a`: un
   punto SOBRE un segmento que cruza el antimeridiano salía a 5,5 km, y en
   segmentos largos/altas latitudes el error era comparable al corredor.
4. Un polígono de área cero (colineal) pasaba validate_fences y contains()
   era False para todo punto: "outside" para siempre, en silencio.
5. Una coordenada NaN/fuera de rango del UEM llegaba al engine como
   fence_state="outside" (veredicto punitivo fabricado), a location_integrity
   como un salto de 20.015 km ("velocidad imposible") y al SDK como un
   {'inside': False} con cara de verdad. Desconocido nunca penaliza.

Ejecuta: python3 tests/run_tests.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.geo import (  # noqa: E402
    Point, distance_to_segment_m, haversine_m, point_in_polygon,
)
from lucidfence.core.fences import Fence, validate_fences  # noqa: E402
from lucidfence.core.location_source import LocationReport  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


# ---- 1. antimeridiano ------------------------------------------------------

_BANDA_ANTIMERIDIANO = [Point(-1, 178), Point(-1, -178), Point(1, -178), Point(1, 178)]


def test_poligono_que_cruza_el_antimeridiano_no_invierte_el_veredicto():
    assert point_in_polygon(Point(0, 179.5), _BANDA_ANTIMERIDIANO)
    assert point_in_polygon(Point(0, -179.5), _BANDA_ANTIMERIDIANO)
    assert not point_in_polygon(Point(0, 0), _BANDA_ANTIMERIDIANO)
    assert not point_in_polygon(Point(2, 179.5), _BANDA_ANTIMERIDIANO)


def test_poligono_normal_sigue_igual():
    cuadrado = [Point(40.0, -3.0), Point(40.0, -2.0), Point(41.0, -2.0), Point(41.0, -3.0)]
    assert point_in_polygon(Point(40.5, -2.5), cuadrado)
    assert not point_in_polygon(Point(39.5, -2.5), cuadrado)
    assert not point_in_polygon(Point(40.5, -3.5), cuadrado)


# ---- 2. epsilon ------------------------------------------------------------

def test_arista_con_dy_minusculo_no_divide_por_cero():
    poly = [Point(0, 0), Point(1, 0), Point(1, 1), Point(-1e-12, 1)]
    assert point_in_polygon(Point(-5e-13, 0.5), poly)  # antes: ZeroDivisionError
    assert point_in_polygon(Point(0.5, 0.5), poly)
    assert not point_in_polygon(Point(0.5, 1.5), poly)


# ---- 3. distancia a segmento exacta ---------------------------------------

def test_segmento_que_cruza_el_antimeridiano():
    d = distance_to_segment_m(Point(0, 179.95), Point(0, 179.9), Point(0, -179.9))
    assert d < 1.0, f"punto sobre el segmento a {d} m (antes ~5566 m)"


def test_distancia_perpendicular_y_recorte_a_los_extremos():
    a, b = Point(0, 0), Point(0, 1)
    un_km = 1000 / 111_195.0  # grados de latitud
    assert abs(distance_to_segment_m(Point(un_km, 0.5), a, b) - 1000) < 1.0
    # el pie de la perpendicular cae fuera: distancia al extremo más cercano
    assert abs(distance_to_segment_m(Point(0, -1), a, b) - haversine_m(Point(0, -1), a)) < 1e-6
    assert abs(distance_to_segment_m(Point(0, 2), a, b) - haversine_m(Point(0, 2), b)) < 1e-6
    assert distance_to_segment_m(a, a, b) == 0.0
    assert distance_to_segment_m(Point(1, 1), a, a) == haversine_m(Point(1, 1), a)


def test_segmento_largo_en_alta_latitud_es_exacto():
    """Punto medio del círculo máximo entre (60,10) y (60,15): distancia 0, y
    100 m al norte de él son 100 m (la aproximación plana daba cientos)."""
    a, b = Point(60, 10), Point(60, 15)
    la1, lo1, la2, lo2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    bx = math.cos(la2) * math.cos(lo2 - lo1)
    by = math.cos(la2) * math.sin(lo2 - lo1)
    la3 = math.atan2(math.sin(la1) + math.sin(la2), math.hypot(math.cos(la1) + bx, by))
    lo3 = lo1 + math.atan2(by, math.cos(la1) + bx)
    medio = Point(math.degrees(la3), math.degrees(lo3))
    assert distance_to_segment_m(medio, a, b) < 0.01
    norte = Point(medio.lat + 100 / 111_195.0, medio.lng)
    assert abs(distance_to_segment_m(norte, a, b) - 100) < 1.0


# ---- 4. polígono degenerado -------------------------------------------------

def test_poligono_de_area_cero_no_pasa_la_validacion():
    colineal = Fence.from_raw({"id": "z", "name": "z", "type": "polygon", "coordinates": [
        {"lat": 0, "lng": 0}, {"lat": 1, "lng": 1}, {"lat": 2, "lng": 2}]})
    problemas = validate_fences([colineal])
    assert any("zero area" in p for p in problemas), problemas
    triangulo = Fence.from_raw({"id": "t", "name": "t", "type": "polygon", "coordinates": [
        {"lat": 0, "lng": 0}, {"lat": 1, "lng": 1}, {"lat": 0, "lng": 2}]})
    assert validate_fences([triangulo]) == []


# ---- 5. NaN / fuera de rango = desconocido, nunca "outside" -----------------

class _FuenteFija:
    def __init__(self, lat, lng):
        self._lat, self._lng = lat, lng

    def fetch(self):
        return [LocationReport(device_id="dev-nan", name="NaN", platform="android",
                               status="active", compliant=True,
                               lat=self._lat, lng=self._lng)]


def _engine_con_cerca():
    eng = make_temp_engine()
    eng.routes = []
    eng.fences = []
    eng.fence_by_id = {}
    eng.add_fence({"name": "Almacén", "type": "circle",
                   "center": {"lat": 40.5, "lng": -3.7}, "radius_m": 300,
                   "actions": [{"action": "notify", "when": "on_exit", "params": {}}]})
    return eng


def test_coordenada_nan_en_el_engine_es_desconocido_no_outside():
    for lat, lng in ((float("nan"), -3.7), (40.5, float("inf")), (999.0, -3.7)):
        eng = _engine_con_cerca()
        eng.source = _FuenteFija(lat, lng)
        eng.run_once()
        ds = eng.store.snapshot()["dev-nan"]
        assert ds.fence_state == "unknown", (lat, lng, ds)
    # y una coordenada válida sigue evaluándose
    eng = _engine_con_cerca()
    eng.source = _FuenteFija(40.5, -3.7)
    eng.run_once()
    assert eng.store.snapshot()["dev-nan"].fence_state == "inside"


def test_nan_dentro_de_la_cerca_no_dispara_on_exit():
    eng = _engine_con_cerca()
    eng.source = _FuenteFija(40.5, -3.7)
    eng.run_once()
    eng.source = _FuenteFija(float("nan"), -3.7)
    eng.run_once()
    assert not any(a.get("trigger") == "on_exit" for a in eng._cycle_actions), eng._cycle_actions


def test_location_integrity_ignora_coordenadas_basura():
    from lucidfence.core import location_integrity as li
    assert li._coords({"lat": float("nan"), "lng": 0}) is None
    assert li._coords({"lat": 0, "lng": 181}) is None
    assert li._coords({"lat": "x", "lng": 0}) is None
    assert li._coords({"lat": 1, "lng": 2}) == Point(1.0, 2.0)


def test_sdk_rechaza_coordenadas_basura_en_vez_de_inside_false():
    import lucidfence
    g = lucidfence.GeoFencer()
    for llamada in (lambda: g.add_circle("a", float("nan"), 0, 100),
                    lambda: g.add_circle("b", 999, 0, 100),
                    lambda: g.add_circle("c", 0, 0, float("nan")),
                    lambda: g.add_polygon("d", [{"lat": 0, "lng": 0}, {"lat": 1, "lng": 1},
                                                {"lat": float("inf"), "lng": 0}]),
                    lambda: g.evaluate(float("nan"), 0)):
        try:
            llamada()
            assert False, "el SDK aceptó una coordenada basura"
        except ValueError:
            pass
    g.add_circle("ok", 0, 0, 100)
    assert g.evaluate(0.0005, 0)["inside"] is True


def test_add_route_rechaza_waypoints_nan():
    eng = make_temp_engine()
    try:
        eng.add_route({"name": "R", "waypoints": [{"lat": float("nan"), "lng": 0}, {"lat": 1, "lng": 1}]})
        assert False, "add_route aceptó un waypoint NaN"
    except ValueError:
        pass
