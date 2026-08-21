"""Informe de puntos ciegos (coverage gap): qué NO cubre la config actual.

El negativo que ningún panel del sector enseña. Tres listas honestas sobre
estado ya existente (cero llamadas de red, cero escritura):

  - devices_sin_senal: dispositivos del inventario sin ubicación utilizable
    (ni coordenadas válidas ni match de red) — existen pero no se pueden
    evaluar contra ninguna geocerca.
  - devices_sin_reportar: el "lost sheep" — dispositivos cuyo last_seen supera
    el umbral. LucidFence lo hace VISIBLE; el admin decide qué hacer (jamás
    una acción automática — frontera inviolable del producto).
  - fences_vacias: geocercas configuradas con cero dispositivos dentro.

Readback-honesto: un dato ausente/None nunca inventa cobertura ni penaliza
más allá de listar el punto ciego con su motivo.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from lucidfence.core.fences import Fence
from lucidfence.core.geo import Point


def _device_point(dev: dict) -> Optional[Point]:
    """Coordenadas utilizables del dispositivo, o None si no las hay.

    No usa point_from(): aquí una coordenada basura no debe fallar en alto,
    solo dejar al dispositivo honesto en la lista de puntos ciegos.
    """
    lat, lng = dev.get("lat"), dev.get("lng")
    if lat is None or lng is None:
        return None
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lng_f)):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
        return None
    return Point(lat=lat_f, lng=lng_f)


def _last_seen_age_s(raw, now: datetime) -> tuple[Optional[float], Optional[str]]:
    """(edad en segundos, None) si last_seen es parseable, (None, motivo) si no."""
    if not raw:
        return None, "sin last_seen"
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None, "last_seen ilegible"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds(), None


def coverage_report(devices: list[dict], fences: list, now: Optional[datetime] = None,
                    stale_after_s: int = 86400) -> dict:
    """Informe de puntos ciegos sobre dicts estilo DeviceState.to_dict().

    `fences` acepta objetos Fence o sus dicts crudos (circle y polygon).
    Función pura: no toca disco ni red y no muta sus argumentos.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    fence_objs = [f if isinstance(f, Fence) else Fence.from_raw(f) for f in fences]

    sin_senal: list[dict] = []
    sin_reportar: list[dict] = []
    located: list[Point] = []
    for dev in devices:
        ident = {"device_id": dev.get("device_id"), "name": dev.get("name")}
        p = _device_point(dev)
        if p is None:
            sin_senal.append({**ident,
                              "location_source": dev.get("location_source") or "unknown",
                              "reason": "sin coordenadas válidas ni match de red"})
        else:
            located.append(p)

        raw_last_seen = dev.get("last_seen")
        age_s, why = _last_seen_age_s(raw_last_seen, now)
        if why is not None:
            sin_reportar.append({**ident, "last_seen": raw_last_seen or None,
                                 "age_s": None, "reason": why})
        elif age_s > stale_after_s:
            sin_reportar.append({**ident, "last_seen": raw_last_seen,
                                 "age_s": int(age_s),
                                 "reason": f"sin reportar desde hace {int(age_s // 3600)}h"})

    fences_vacias = [
        {"fence_id": f.id, "name": f.name, "type": f.type}
        for f in fence_objs
        if not any(f.contains(p) for p in located)
    ]

    total = len(devices)
    evaluables = total - len(sin_senal)
    return {
        "devices_sin_senal": sin_senal,
        "devices_sin_reportar": sin_reportar,
        "fences_vacias": fences_vacias,
        "resumen": {
            "devices_total": total,
            "devices_evaluables": evaluables,
            "devices_sin_senal": len(sin_senal),
            "devices_sin_reportar": len(sin_reportar),
            "fences_total": len(fence_objs),
            "fences_vacias": len(fences_vacias),
            "stale_after_s": stale_after_s,
            "coverage_percent": 100.0 if total == 0 else round(evaluables / total * 100, 1),
        },
    }
