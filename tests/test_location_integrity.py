"""Tests de anti-spoofing de ubicación (P0.2): heurísticas + señal de riesgo."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.location_integrity import assess
from lucidfence.core.policies import RiskEngine

NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)

# Madrid y Buenos Aires: ~10.000 km. En 15 minutos = ~40.000 km/h.
MADRID = {"lat": 40.4168, "lng": -3.7038}
BUENOS_AIRES = {"lat": -34.6037, "lng": -58.3816}


def _prev(lat, lng, minutes_ago=15, country="es"):
    ts = NOW.timestamp() - minutes_ago * 60
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"lat": lat, "lng": lng, "country": country, "last_report_ts": iso}


def test_impossible_speed_detected_on_teleport() -> None:
    result = assess(
        dict(BUENOS_AIRES, country="ar", location_source="gps"),
        _prev(**MADRID), now=NOW,
    )
    assert result["suspicious"] is True
    assert "impossible_speed" in result["checks"]
    assert result["speed_kmh"] > 1000
    assert result["distance_km"] > 9000


def test_normal_commute_speed_is_clean() -> None:
    # ~11 km en 15 min ≈ 45 km/h: desplazamiento urbano normal.
    result = assess(
        {"lat": 40.5168, "lng": -3.7038, "country": "es", "location_source": "gps"},
        _prev(**MADRID), now=NOW,
    )
    assert result["suspicious"] is False and result["checks"] == []


def test_gps_jitter_below_min_distance_never_flags_speed() -> None:
    # 300 m en 5 segundos daría 216 km/h "implícitos": el umbral de distancia
    # mínima evita castigar jitter GPS de reports casi simultáneos.
    prev = _prev(40.4168, -3.7038)
    prev["last_report_ts"] = "2026-08-15T11:59:55Z"
    result = assess({"lat": 40.4195, "lng": -3.7038, "location_source": "gps"}, prev, now=NOW)
    assert "impossible_speed" not in result["checks"]


def test_country_flip_without_movement() -> None:
    result = assess(
        dict(MADRID, country="fr", location_source="gps"),
        _prev(**MADRID, country="es"), now=NOW,
    )
    assert "country_flip_without_movement" in result["checks"]


def test_country_change_with_real_travel_is_clean() -> None:
    # Madrid → París (~1.050 km) en 15 min sí es velocidad imposible, pero el
    # flip de país con movimiento real no debe añadirse como señal aparte.
    paris = {"lat": 48.8566, "lng": 2.3522, "country": "fr", "location_source": "gps"}
    result = assess(paris, _prev(**MADRID, country="es", minutes_ago=24 * 60), now=NOW)
    assert "country_flip_without_movement" not in result["checks"]
    assert "impossible_speed" not in result["checks"]  # 1050 km en 24 h ≈ 44 km/h


def test_accuracy_anomalies() -> None:
    assert "accuracy_invalid" in assess({"lat": 1, "lng": 1, "accuracy_m": 0}, None)["checks"]
    assert "accuracy_invalid" in assess({"lat": 1, "lng": 1, "accuracy_m": -5}, None)["checks"]
    assert "accuracy_too_perfect" in assess(
        {"lat": 1, "lng": 1, "accuracy_m": 10, "location_source": "coarse_ip"}, None
    )["checks"]
    # GPS de verdad puede dar 10 m: solo coarse_ip es sospechoso.
    assert assess({"lat": 1, "lng": 1, "accuracy_m": 10, "location_source": "gps"}, None)["checks"] == []


def test_engine_like_call_without_now_uses_observation_clock() -> None:
    # Regresión del hallazgo de validación runtime: el engine no pasa `now`,
    # y el last_seen del report (reloj del dispositivo, redondeado o
    # manipulable) podía quedar ANTES del last_report_ts previo → dt <= 0 y
    # el teletransporte pasaba en silencio. El reloj de observación debe ser
    # el nuestro: sin `now`, assess usa datetime.now(utc), no last_seen.
    prev_ts = datetime.now(timezone.utc).timestamp() - 15 * 60
    prev = {"lat": MADRID["lat"], "lng": MADRID["lng"], "country": "es",
            "last_report_ts": datetime.fromtimestamp(prev_ts, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")}
    stale_seen = datetime.fromtimestamp(prev_ts - 3600, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = assess(dict(BUENOS_AIRES, country="ar", location_source="gps",
                         last_seen=stale_seen), prev)
    assert "impossible_speed" in result["checks"]
    assert result["speed_kmh"] > 1000


def test_first_cycle_and_missing_data_are_clean() -> None:
    assert assess(dict(MADRID), None)["suspicious"] is False
    assert assess({}, _prev(**MADRID))["suspicious"] is False
    assert assess({"lat": "no-num", "lng": None}, _prev(**MADRID))["suspicious"] is False


def test_risk_engine_scores_spoofing_with_explainable_reasons() -> None:
    engine = RiskEngine()
    device = {
        "device_id": "dev-1", "compliant": True,
        "location_integrity": {
            "suspicious": True,
            "checks": ["impossible_speed", "country_flip_without_movement"],
            "speed_kmh": 40000.0,
        },
    }
    risk = engine.evaluate(device, "inside", {})
    assert risk["risk_score"] >= 45  # 30 + 15
    joined = " | ".join(risk["reasons"])
    assert "spoofing" in joined and "40000 km/h" in joined
    assert risk["verified"] is True and risk["provenance"] == "tool"
    assert risk["signals"]["location_integrity"]["suspicious"] is True


def test_risk_engine_clean_report_adds_no_spoofing_reasons() -> None:
    risk = RiskEngine().evaluate(
        {"device_id": "dev-2", "compliant": True,
         "location_integrity": {"suspicious": False, "checks": [], "speed_kmh": 12.0}},
        "inside", {},
    )
    assert not any("spoofing" in r for r in risk["reasons"])
