"""Detección de spoofing de ubicación — heurísticas 100% locales.

El geofencing sin anti-spoofing es teatro de seguridad: si un report puede
teletransportar el dispositivo dentro de la geocerca, la política que cuelga de
"inside" no protege nada. Este módulo puntúa la VEROSIMILITUD del report con
lo que ya tenemos en local (report actual + último estado persistido), sin
servicios externos ni datasets:

- impossible_speed: la velocidad implícita entre el último estado y el report
  actual supera lo físicamente plausible (> IMPOSSIBLE_SPEED_KMH, con distancia
  mínima para no penalizar el jitter GPS de reports casi simultáneos).
- country_flip_without_movement: el país declarado cambia entre reports pero la
  posición apenas se movió — metadatos incoherentes, típico de reports
  manipulados o de fuente que mezcla dispositivos.
- accuracy_invalid: accuracy_m <= 0 no existe en ningún GPS real.
- accuracy_too_perfect: una fuente coarse_ip no puede dar precisión < 100 m;
  si la da, alguien está falseando el campo.

Cada check es explicable y va al Risk Engine como señal con provenance. Un
report sospechoso NO se descarta (el operador decide): sube el score y deja
evidencia en `reasons`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from lucidfence.core.geo import Point, haversine_m

# Umbral de velocidad físicamente plausible entre dos reports. Un avión
# comercial cruza a ~900 km/h; por encima de 1000 km/h sostenidos entre
# ciclos asumimos spoofing (o reloj roto — igual de inaceptable como evidencia).
IMPOSSIBLE_SPEED_KMH = 1000.0
# Distancia mínima para evaluar velocidad: evita que el jitter GPS entre dos
# reports muy seguidos dispare falsas "velocidades" enormes.
MIN_DISTANCE_KM = 5.0
# Flip de país sin movimiento: umbral de "apenas se movió".
COUNTRY_FLIP_MAX_KM = 50.0
# Precisión imposible para una fuente coarse_ip (geolocalización por IP).
COARSE_IP_MIN_ACCURACY_M = 100.0


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _coords(d: dict) -> Optional[Point]:
    lat, lng = d.get("lat"), d.get("lng")
    if lat is None or lng is None:
        return None
    try:
        return Point(float(lat), float(lng))
    except (TypeError, ValueError):
        return None


def assess(current: dict, previous: Optional[dict], now: Optional[datetime] = None) -> dict:
    """Evalúa la integridad del report actual contra el último estado conocido.

    `current`: report normalizado (lat, lng, accuracy_m, country,
    location_source, last_seen). `previous`: DeviceState previo como dict
    (lat, lng, country, last_report_ts) o None en el primer ciclo.

    Devuelve un dict serializable:
        {"suspicious": bool, "checks": [str, ...], "speed_kmh": float|None,
         "distance_km": float|None}
    Nunca lanza: ante datos incompletos simplemente no hay señal.
    """
    checks: list[str] = []
    speed_kmh: Optional[float] = None
    distance_km: Optional[float] = None
    try:
        cur = _coords(current)
        prev = _coords(previous or {})

        # --- velocidad imposible / flip de país -------------------------
        if cur is not None and prev is not None:
            distance_km = haversine_m(prev, cur) / 1000.0
            prev_ts = _parse_ts((previous or {}).get("last_report_ts")
                                or (previous or {}).get("last_seen"))
            # El reloj de observación es SIEMPRE el nuestro, nunca el
            # last_seen del report: (1) prev.last_report_ts se grabó con
            # nuestro reloj, y mezclar relojes daba dt <= 0 y silenciaba el
            # check en producción; (2) last_seen lo controla el dispositivo,
            # y un spoofer podría inflarlo para diluir la velocidad.
            now_ts = now or datetime.now(timezone.utc)
            if prev_ts is not None and distance_km >= MIN_DISTANCE_KM:
                dt_h = (now_ts - prev_ts).total_seconds() / 3600.0
                if dt_h > 0:
                    speed_kmh = distance_km / dt_h
                    if speed_kmh > IMPOSSIBLE_SPEED_KMH:
                        checks.append("impossible_speed")

            prev_country = ((previous or {}).get("country") or "").strip().lower()
            cur_country = (current.get("country") or "").strip().lower()
            if (prev_country and cur_country and prev_country != cur_country
                    and distance_km < COUNTRY_FLIP_MAX_KM):
                checks.append("country_flip_without_movement")

        # --- accuracy anómala -------------------------------------------
        accuracy = current.get("accuracy_m")
        if accuracy is not None:
            try:
                accuracy_f = float(accuracy)
                if accuracy_f <= 0:
                    checks.append("accuracy_invalid")
                elif ((current.get("location_source") or "") == "coarse_ip"
                      and accuracy_f < COARSE_IP_MIN_ACCURACY_M):
                    checks.append("accuracy_too_perfect")
            except (TypeError, ValueError):
                pass
    except Exception:  # noqa: BLE001 — la integridad nunca tira el ciclo
        pass

    return {
        "suspicious": bool(checks),
        "checks": checks,
        "speed_kmh": round(speed_kmh, 1) if speed_kmh is not None else None,
        "distance_km": round(distance_km, 2) if distance_km is not None else None,
    }
