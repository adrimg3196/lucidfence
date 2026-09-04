"""Tests de los eventos OCSF Detection Finding (backlog §17).

Cubre el serializador puro (`core/ocsf.py`) y su opt-in en el webhook genérico
que ya existía. Sin red: se inyecta un http_post falso.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.notifier import SignedWebhookNotifier, build_incident_notifiers
from lucidfence.core.ocsf import SCHEMA_VERSION, detection_finding

INCIDENT = {
    "id": "inc-outside-dev-7",
    "type": "geofence_exit",
    "severity": "high",
    "status": "open",
    "title": "Tablet almacén está fuera de geovalla",
    "device_id": "dev-7",
    "device_name": "Tablet almacén",
    "recommendation": "Validar ubicación reciente y ejecutar acción UEM si procede.",
    "first_seen": "2026-08-29T09:00:00+00:00",
    "last_seen": "2026-08-29T09:30:00+00:00",
    "count": 3,
    "fence_id": "hq",
}

# Coordenadas envenenadas: reconocibles a simple vista en el payload. El
# webhook nativo NO publica ubicación y OCSF no puede ampliar esa superficie.
POISONED = dict(INCIDENT, lat=41.403629, lng=2.174356,
                last_location={"lat": 41.403629, "lng": 2.174356},
                address="Carrer de Mallorca 401, Barcelona")


class _FakePost:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload, headers or {}))
        return {"ok": True, "status": 200}


def test_detection_finding_carries_the_class_required_fields() -> None:
    ev = detection_finding("open", INCIDENT)
    for field in ("activity_id", "category_uid", "class_uid", "type_uid",
                  "severity_id", "time", "metadata", "finding_info"):
        assert field in ev, f"falta el obligatorio {field}"
    assert ev["category_uid"] == 2 and ev["class_uid"] == 2004
    assert ev["type_uid"] == 2004 * 100 + ev["activity_id"] == 200401
    assert isinstance(ev["time"], int) and ev["time"] > 0
    # Esquema declarado: nombre del producto y versión de OCSF.
    assert ev["metadata"]["version"] == SCHEMA_VERSION
    assert ev["metadata"]["product"]["vendor_name"] == "LucidFence"
    # finding_info exige uid + title.
    assert ev["finding_info"]["uid"] == "inc-outside-dev-7"
    assert ev["finding_info"]["title"] == INCIDENT["title"]
    # El dispositivo viaja como recurso: identidad, no ubicación.
    assert ev["resources"] == [{"uid": "dev-7", "name": "Tablet almacén",
                                "type": "device"}]
    # Lo que es de LucidFence y no tiene equivalente OCSF va a `unmapped`,
    # nunca forzado dentro de un campo que "suena parecido".
    assert ev["unmapped"] == {"type": "geofence_exit", "fence_id": "hq"}


def test_severity_and_lifecycle_map_coherently() -> None:
    # info/low/medium/high/critical -> 1/2/3/4/5 (escala OCSF, sin estirar a 6).
    got = [detection_finding("open", dict(INCIDENT, severity=s))["severity_id"]
           for s in ("info", "low", "medium", "high", "critical")]
    assert got == [1, 2, 3, 4, 5]
    # Lo desconocido es 0 Unknown, JAMÁS 1 Informational: presentar lo que no
    # se sabe como benigno es el falso verde que el repo prohíbe.
    assert detection_finding("open", dict(INCIDENT, severity="unknown"))["severity_id"] == 0
    assert detection_finding("open", {"id": "x"})["severity_id"] == 0

    # Transición -> activity_id (Create/Update/Close) y status_id.
    assert [detection_finding(t, INCIDENT)["activity_id"]
            for t in ("open", "acknowledged", "resolved")] == [1, 2, 3]
    assert [detection_finding(t, INCIDENT)["status_id"]
            for t in ("open", "acknowledged", "resolved")] == [1, 2, 4]
    otro = detection_finding("reopen", INCIDENT)
    assert otro["activity_id"] == 99 and otro["type_uid"] == 200499


def test_ocsf_event_never_carries_coordinates() -> None:
    body = json.dumps(detection_finding("open", POISONED), ensure_ascii=False)
    for leak in ("41.403629", "2.174356", "lat", "lng", "Mallorca", "address"):
        assert leak not in body, f"fuga de ubicación en el evento OCSF: {leak}"


def test_ocsf_optin_replaces_the_payload_only_when_activated() -> None:
    post = _FakePost()
    n = SignedWebhookNotifier("https://mi-siem/hec", secret="s", http_post=post, fmt="ocsf")
    assert n.notify("open", INCIDENT) is True
    _url, body, headers = post.calls[0]
    payload = json.loads(body)
    assert payload["class_uid"] == 2004 and "incident" not in payload
    # La firma sigue cubriendo los bytes exactos enviados.
    assert SignedWebhookNotifier.verify("s", body, headers["X-LucidFence-Signature"])

    # Sin activar (y con un formato con errata) el contrato nativo no cambia.
    for fmt in ("native", "", "ocsv"):
        post = _FakePost()
        n = SignedWebhookNotifier("https://receptor/hook", http_post=post, fmt=fmt)
        assert n.notify("open", INCIDENT) is True
        payload = json.loads(post.calls[0][1])
        assert payload["event"] == "lucidfence.incident"
        assert payload["transition"] == "open" and payload["incident"]["id"] == INCIDENT["id"]


def test_build_incident_notifiers_reads_the_format_per_channel() -> None:
    channels = build_incident_notifiers({
        "incident_webhooks": [
            {"type": "generic", "url": "https://mi-siem/hec", "format": "ocsf"},
            {"type": "generic", "url": "https://receptor/hook"},
        ],
    })
    assert [c.fmt for c in channels] == ["ocsf", "native"]
