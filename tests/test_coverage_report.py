"""Informe de puntos ciegos (coverage gap) — core/coverage.py.

Las tres listas honestas del backlog #15: sin señal, sin reportar ("lost
sheep") y cercas vacías, más el coverage_percent del resumen. Readback-honesto:
un dato ausente lista el punto ciego con motivo, nunca inventa cobertura.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.coverage import coverage_report  # noqa: E402

NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
FRESH = NOW.isoformat()
STALE = (NOW - timedelta(days=3)).isoformat()

# Círculo de 500 m sobre Madrid centro y un polígono cuadrado al lado.
CIRCLE = {"id": "hq", "name": "Sede", "type": "circle",
          "center": {"lat": 40.4168, "lng": -3.7038}, "radius_m": 500}
POLY = {"id": "campus", "name": "Campus", "type": "polygon",
        "coordinates": [{"lat": 40.50, "lng": -3.60}, {"lat": 40.50, "lng": -3.50},
                        {"lat": 40.40, "lng": -3.50}, {"lat": 40.40, "lng": -3.60}]}


def _dev(dev_id, lat=None, lng=None, last_seen=FRESH, **extra):
    return {"device_id": dev_id, "name": dev_id, "lat": lat, "lng": lng,
            "last_seen": last_seen, **extra}


def test_device_without_coords_is_a_blind_spot():
    rep = coverage_report([_dev("d1")], [CIRCLE], now=NOW)
    ids = [d["device_id"] for d in rep["devices_sin_senal"]]
    assert ids == ["d1"], f"esperaba d1 en sin_senal, got {ids}"
    assert rep["devices_sin_senal"][0]["reason"]
    assert rep["resumen"]["coverage_percent"] == 0.0


def test_invalid_coords_count_as_no_signal_not_a_crash():
    rep = coverage_report([_dev("d1", lat=999.0, lng=-3.70),
                           _dev("d2", lat=float("nan"), lng=1.0)], [CIRCLE], now=NOW)
    assert {d["device_id"] for d in rep["devices_sin_senal"]} == {"d1", "d2"}


def test_stale_last_seen_is_a_lost_sheep():
    rep = coverage_report([_dev("d1", lat=40.4168, lng=-3.7038, last_seen=STALE)],
                          [CIRCLE], now=NOW)
    lost = rep["devices_sin_reportar"]
    assert [d["device_id"] for d in lost] == ["d1"]
    assert lost[0]["age_s"] == 3 * 86400
    # con coords válidas NO es punto ciego de señal, solo de reporte
    assert rep["devices_sin_senal"] == []
    assert rep["resumen"]["coverage_percent"] == 100.0


def test_missing_last_seen_listed_with_null_and_reason():
    rep = coverage_report([_dev("d1", lat=40.4168, lng=-3.7038, last_seen=None)],
                          [CIRCLE], now=NOW)
    lost = rep["devices_sin_reportar"]
    assert len(lost) == 1
    assert lost[0]["last_seen"] is None
    assert lost[0]["reason"] == "sin last_seen"


def test_custom_stale_threshold_respected():
    one_hour_ago = (NOW - timedelta(hours=1)).isoformat()
    dev = [_dev("d1", lat=40.4168, lng=-3.7038, last_seen=one_hour_ago)]
    assert coverage_report(dev, [], now=NOW)["devices_sin_reportar"] == []
    rep = coverage_report(dev, [], now=NOW, stale_after_s=1800)
    assert [d["device_id"] for d in rep["devices_sin_reportar"]] == ["d1"]


def test_empty_fence_is_reported():
    # d1 dentro del círculo; el polígono queda sin nadie
    rep = coverage_report([_dev("d1", lat=40.4168, lng=-3.7038)], [CIRCLE, POLY], now=NOW)
    assert [f["fence_id"] for f in rep["fences_vacias"]] == ["campus"]
    assert rep["resumen"]["fences_vacias"] == 1


def test_polygon_fence_with_device_inside_is_not_empty():
    rep = coverage_report([_dev("d1", lat=40.45, lng=-3.55)], [POLY], now=NOW)
    assert rep["fences_vacias"] == []


def test_fully_covered_fleet_yields_empty_lists_and_100():
    devs = [_dev("d1", lat=40.4168, lng=-3.7038),
            _dev("d2", lat=40.45, lng=-3.55)]
    rep = coverage_report(devs, [CIRCLE, POLY], now=NOW)
    assert rep["devices_sin_senal"] == []
    assert rep["devices_sin_reportar"] == []
    assert rep["fences_vacias"] == []
    assert rep["resumen"]["coverage_percent"] == 100.0
    assert rep["resumen"]["devices_total"] == 2


def test_covered_device_appears_in_no_list():
    rep = coverage_report([_dev("ok", lat=40.4168, lng=-3.7038),
                           _dev("mudo")], [CIRCLE], now=NOW)
    for key in ("devices_sin_senal", "devices_sin_reportar"):
        assert "ok" not in [d["device_id"] for d in rep[key]], f"ok no debería estar en {key}"
    assert rep["resumen"]["coverage_percent"] == 50.0


def test_no_devices_is_100_percent_not_a_division_crash():
    rep = coverage_report([], [CIRCLE], now=NOW)
    assert rep["resumen"]["coverage_percent"] == 100.0
    assert [f["fence_id"] for f in rep["fences_vacias"]] == ["hq"]


if __name__ == "__main__":
    for name in sorted(n for n in dir() if n.startswith("test_")):
        globals()[name]()
    print("PASS")
