"""Serialización de incidentes a OCSF Detection Finding (backlog §17).

El SOC de la organización ya tiene su herramienta (Splunk, Sentinel, Chronicle).
LucidFence es el complemento: en vez de pedir otro panel, habla el idioma
estándar de esas herramientas —OCSF, Open Cybersecurity Schema Framework— para
que el veredicto entre sin parser a medida. El evento se genera en LOCAL; a
dónde se envía lo decide el tenant en su webhook de siempre.

Función pura: cero red, cero disco, cero estado. Entrada: la transición del
ciclo de vida (`open` | `acknowledged` | `resolved`) y el incidente tal cual lo
maneja `IncidentStore`. Salida: un dict listo para `json.dumps`.

INVARIANTE DE PRIVACIDAD (no negociable):
    El evento se construye con una LISTA BLANCA de campos, nunca copiando el
    incidente entero. El webhook nativo de hoy no publica coordenadas y OCSF
    tampoco puede ampliar esa superficie: si mañana alguien mete `lat`/`lng` en
    un incidente, este serializador sigue sin emitirlas porque no las nombra.

HONESTIDAD DEL MAPEO (misma regla que least_privilege.py con los scopes):
    Aquí solo se rellenan atributos OCSF de los que tenemos certeza. Lo que es
    específico de LucidFence y no tiene equivalente en el esquema NO se fuerza
    dentro de un campo que "suena parecido": va en `unmapped`, que es
    exactamente el sitio que OCSF reserva para eso. Un mapeo inventado rompería
    la ingesta del SIEM del cliente, que es lo contrario de lo que venimos a
    hacer.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

#: Versión del esquema OCSF que declaramos en `metadata.version`. La clase
#: Detection Finding (2004) existe desde OCSF 1.1.0; declaramos la versión
#: concreta contra la que está construido el mapeo para que el receptor sepa
#: cómo validarlo, en vez de dejarlo a su adivinación.
SCHEMA_VERSION = "1.3.0"

CATEGORY_UID = 2      # Findings
CLASS_UID = 2004      # Detection Finding

_VENDOR_NAME = "LucidFence"

#: Severidad LucidFence -> severity_id de OCSF.
#: OCSF: 0 Unknown, 1 Informational, 2 Low, 3 Medium, 4 High, 5 Critical,
#: 6 Fatal, 99 Other. El mapeo es 1:1 con la escala del producto; `6 Fatal`
#: queda sin usar a propósito: LucidFence no tiene nada por encima de
#: `critical` y estirar la escala exageraría el veredicto en el panel del SOC.
_SEVERITY_ID = {"info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}

_SEVERITY_NAME = {0: "Unknown", 1: "Informational", 2: "Low", 3: "Medium",
                  4: "High", 5: "Critical"}

#: Transición del incidente -> (activity_id, activity_name) de Detection Finding.
#: OCSF: 1 Create, 2 Update, 3 Close, 99 Other.
_ACTIVITY = {"open": (1, "Create"),
             "acknowledged": (2, "Update"),
             "resolved": (3, "Close")}

#: Transición -> (status_id, status). OCSF: 1 New, 2 In Progress, 4 Resolved.
_STATUS = {"open": (1, "New"),
           "acknowledged": (2, "In Progress"),
           "resolved": (4, "Resolved")}

#: Lo que es de LucidFence y no tiene equivalente en el esquema. Es la lista
#: blanca que fija el invariante de privacidad: nada fuera de aquí sale.
_UNMAPPED_FIELDS = ("type", "fence_id", "route_state", "risk_score", "assignee")


def _ts_ms(value: Any) -> int | None:
    """Marca ISO-8601 del incidente -> epoch en milisegundos (OCSF).

    Devuelve None si no hay marca utilizable: un timestamp inventado en un
    hallazgo de seguridad es peor que su ausencia.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def severity_id(severity: Any) -> int:
    """Severidad del producto -> severity_id OCSF; lo desconocido es 0, no 1.

    Un nivel que no reconocemos (o el `unknown` que emite el evaluador de riesgo
    cuando falla) va a `0 Unknown`, NUNCA a `1 Informational`: presentar lo
    desconocido como benigno es el falso verde que el repo prohíbe.
    """
    return _SEVERITY_ID.get(str(severity or "").strip().lower(), 0)


def detection_finding(transition: str, incident: dict) -> dict:
    """Incidente LucidFence -> evento OCSF Detection Finding (class_uid 2004)."""
    trans = str(transition or "").strip().lower()
    activity_id, activity_name = _ACTIVITY.get(trans, (99, trans or "Other"))
    status_id, status_name = _STATUS.get(trans, (0, "Unknown"))
    sev_id = severity_id(incident.get("severity"))

    # `time` es la marca de la condición observada (last_seen), no la del
    # reenvío: el SOC correlaciona por cuándo pasó, no por cuándo llegó.
    event_time = _ts_ms(incident.get("last_seen")) or int(time.time() * 1000)

    finding_info: dict[str, Any] = {
        "uid": str(incident.get("id") or ""),
        "title": str(incident.get("title") or incident.get("id") or "Incidente"),
    }
    if incident.get("recommendation"):
        finding_info["desc"] = str(incident["recommendation"])
    if incident.get("type"):
        finding_info["types"] = [str(incident["type"])]
    first_seen = _ts_ms(incident.get("first_seen"))
    if first_seen is not None:
        finding_info["first_seen_time"] = first_seen
    last_seen = _ts_ms(incident.get("last_seen"))
    if last_seen is not None:
        finding_info["last_seen_time"] = last_seen

    event: dict[str, Any] = {
        "activity_id": activity_id,
        "activity_name": activity_name,
        "category_uid": CATEGORY_UID,
        "category_name": "Findings",
        "class_uid": CLASS_UID,
        "class_name": "Detection Finding",
        "type_uid": CLASS_UID * 100 + activity_id,
        "type_name": f"Detection Finding: {activity_name}",
        "severity_id": sev_id,
        "severity": _SEVERITY_NAME.get(sev_id, "Unknown"),
        "status_id": status_id,
        "status": status_name,
        "time": event_time,
        "message": finding_info["title"],
        "metadata": {
            "version": SCHEMA_VERSION,
            "product": {"vendor_name": _VENDOR_NAME, "name": _VENDOR_NAME},
        },
        "finding_info": finding_info,
    }

    # El dispositivo afectado viaja como recurso (identidad, nunca ubicación).
    device_id = str(incident.get("device_id") or "")
    if device_id:
        event["resources"] = [{
            "uid": device_id,
            "name": str(incident.get("device_name") or device_id),
            "type": "device",
        }]

    count = incident.get("count")
    if isinstance(count, int) and count > 0:
        event["count"] = count

    unmapped = {k: incident[k] for k in _UNMAPPED_FIELDS
                if incident.get(k) is not None}
    if unmapped:
        event["unmapped"] = unmapped
    return event
