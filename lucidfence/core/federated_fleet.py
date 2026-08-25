"""Vista federada multi-UEM: una sola flota con veredicto de riesgo comparable.

Una organización real corre 2+ UEMs a la vez (Intune para Windows, Jamf para
Mac, Fleet para Linux) y cada consola enseña solo su parcela. Este módulo
proyecta los dispositivos del tenant — vengan del UEM que vengan — en UNA lista
con el origen trazado (provider + segmento de flota) y el veredicto que el Risk
Engine ya produjo. Función pura sobre datos ya calculados: aquí no se recalcula
riesgo ni se consulta ningún UEM (backlog de producto §12).

Regla de honestidad (invariante del repo): un campo que el provider no reporta
se devuelve como null/None — jamás se inventa un valor ni se penaliza al
dispositivo por lo desconocido. Un dispositivo sin origen trazable queda con
``provider: null``, nunca atribuido a un UEM por conjetura.
"""
from __future__ import annotations

from typing import Any

# Mismo contrato de nombre que los providers del registro multi-UEM
# (multiuem._SAFE_NAME): minúsculas ASCII + dígitos + guion bajo. Un filtro que
# no puede ser un nombre de provider se rechaza con 400 en la API, nunca se
# ignora en silencio (un filtro ignorado devolvería una lista que miente).
_MAX_PROVIDER_NAME = 64


def valid_provider_filter(name: Any) -> bool:
    """True si ``name`` tiene forma de nombre de provider multi-UEM."""
    if not isinstance(name, str) or not name or len(name) > _MAX_PROVIDER_NAME:
        return False
    if not name.isascii() or name != name.lower():
        return False
    if not (name[0].isalpha()):
        return False
    return all(ch.isalnum() or ch == "_" for ch in name)


def _origins(device: dict) -> list[str]:
    """Providers que reportaron este dispositivo, en orden estable."""
    refs = device.get("provider_refs")
    if not isinstance(refs, dict):
        return []
    return sorted(str(name) for name in refs if name)


def _top_reasons(risk_row: dict | None, limit: int = 3) -> list[str]:
    """Las razones top del explain, tal cual las produjo el engine."""
    if not isinstance(risk_row, dict):
        return []
    labels = []
    for factor in risk_row.get("factors") or []:
        label = factor.get("label") if isinstance(factor, dict) else factor
        if isinstance(label, str) and label:
            labels.append(label)
    return labels[:limit]


def build_federated_fleet(
    devices: list[dict],
    risk_rows: list[dict],
    providers: list[dict],
    provider: str | None = None,
) -> dict:
    """Proyecta la flota del tenant en una vista federada multi-UEM.

    - ``devices``: dicts de ``DeviceState.to_dict()`` (estado ya persistido).
    - ``risk_rows``: veredicto del Risk Engine por dispositivo (las filas de
      ``product._risk_from_engine`` — las mismas que sirve ``/api/risk``). El
      panel NO recalcula: un dispositivo sin fila queda con riesgo null.
    - ``providers``: registro del tenant ({"name", "segment"?}); aporta la
      etiqueta de segmento de cada UEM de origen. No se necesitan credenciales.
    - ``provider``: filtro opcional por UEM de origen.
    """
    segments: dict[str, str | None] = {}
    for p in providers or []:
        if isinstance(p, dict) and p.get("name"):
            segments[str(p["name"])] = p.get("segment") or None

    risk_by: dict[str, dict] = {}
    for row in risk_rows or []:
        if isinstance(row, dict) and row.get("device_id"):
            risk_by[str(row["device_id"])] = row

    rows: list[dict] = []
    counts: dict[str, int] = {name: 0 for name in segments}
    without_origin = 0
    for device in devices or []:
        if not isinstance(device, dict):
            continue
        device_id = str(device.get("device_id") or "")
        if not device_id:
            continue
        origins = _origins(device)
        if origins:
            for name in origins:
                counts[name] = counts.get(name, 0) + 1
        else:
            without_origin += 1
        risk_row = risk_by.get(device_id)
        primary = origins[0] if origins else None
        rows.append({
            "device_id": device_id,
            "name": device.get("name") or None,
            "platform": device.get("platform") or None,
            # Origen trazado: TODOS los UEMs que reportaron el dispositivo
            # (un dispositivo consolidado puede venir de más de uno) y el
            # principal en orden estable. [] / null = origen desconocido.
            "providers": [
                {"name": name, "segment": segments.get(name)} for name in origins
            ],
            "provider": primary,
            "segment": segments.get(primary) if primary else None,
            "risk": {
                "score": risk_row.get("score") if risk_row else None,
                "level": risk_row.get("level") if risk_row else None,
            },
            "top_reasons": _top_reasons(risk_row),
            "compliant": device.get("compliant"),
            "fence_state": device.get("fence_state") or "unknown",
            "last_seen": device.get("last_seen"),
        })

    fleet_total = len(rows)
    if provider:
        rows = [r for r in rows if any(p["name"] == provider for p in r["providers"])]

    # Riesgo desconocido al final, nunca inflado para ordenar: lo desconocido
    # no compite con señal real.
    rows.sort(key=lambda r: (
        r["risk"]["score"] is None,
        -(r["risk"]["score"] or 0),
        r["name"] or r["device_id"],
    ))

    provider_summary = [
        {"name": name, "segment": segments.get(name), "devices": counts.get(name, 0)}
        for name in sorted(set(segments) | set(counts))
    ]
    return {
        "fleet": rows,
        "total": len(rows),
        "fleet_total": fleet_total,
        "providers": provider_summary,
        "sin_origen": without_origin,
        "filter": {"provider": provider or None},
    }
