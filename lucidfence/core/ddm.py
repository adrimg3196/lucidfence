"""Apple Declarative Device Management (DDM) para políticas de geocerca.

Genera declarations (configurations + activations) y suscripciones de status
a partir de una `Policy` de LucidFence, para que el enforcement converja en el
dispositivo en vez de en bucles imperativos del servidor.

LÍMITE HONESTO — DDM no tiene primitivas de geolocalización. El trigger de
geocerca sigue en el engine/adapters de LucidFence: el servidor decide QUÉ
conjunto de declarations activar en cada transición de estado. DDM es la capa
de configuración/enforcement, no de detección.

Los tipos y claves salen de los schemas públicos de Apple
(github.com/apple/device-management, `declarative/`):

- `com.apple.configuration.legacy`      → ProfileURL (https, alojado por el MDM)
- `com.apple.configuration.management.status-subscriptions` → StatusItems
- `com.apple.activation.simple`         → StandardConfigurations, Predicate

Disponibilidad DDM: iOS/iPadOS 15+, macOS 13+, tvOS 16+, visionOS 1.1+,
watchOS 10+ (`declarationbase.yaml`).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


#: Versión mínima de OS con soporte DDM, por plataforma (declarationbase.yaml).
DDM_MIN_OS = {
    "ios": (15, 0),
    "ipados": (15, 0),
    "macos": (13, 0),
    "tvos": (16, 0),
    "visionos": (1, 1),
    "watchos": (10, 0),
}

#: Status items por defecto de la suscripción. Todos existen en
#: `declarative/status/` del repo de Apple; no inventar nombres.
DEFAULT_STATUS_ITEMS = (
    "device.operating-system.version",
    "device.model.identifier",
    "device.identifier.serial-number",
    "passcode.is-compliant",
)

#: Mapeo status item -> campo del modelo de estado de dispositivo.
_STATUS_FIELD_MAP = {
    "device.operating-system.version": "os_version",
    "device.model.identifier": "model",
    "device.identifier.serial-number": "serial_number",
    "device.model.marketing-name": "model_marketing_name",
    "passcode.is-compliant": "passcode_compliant",
    "diskmanagement.filevault.enabled": "filevault_enabled",
}


def _get(device: Any, key: str, default=None):
    if isinstance(device, dict):
        return device.get(key, default)
    return getattr(device, key, default)


def _parse_version(raw: Any) -> Optional[tuple]:
    """'17.4.1' -> (17, 4, 1). Devuelve None si no es parseable."""
    if raw is None:
        return None
    parts = []
    for chunk in str(raw).strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) or None


def supports_ddm(device: Any) -> bool:
    """True si la plataforma y la versión de OS del dispositivo soportan DDM.

    Sin `os_version` conocida devuelve False: preferimos caer al camino
    imperativo antes que enviar declarations a un dispositivo que no las
    entiende.
    """
    platform = str(_get(device, "platform", "") or "").strip().lower()
    minimum = DDM_MIN_OS.get(platform)
    if minimum is None:
        return False
    version = _parse_version(_get(device, "os_version"))
    if version is None:
        return False
    return version >= minimum


def _server_token(payload: dict) -> str:
    """Token de revisión determinista: mismo payload => mismo token.

    Hace la generación idempotente — reenviar una policy sin cambios no
    provoca una reaplicación en el dispositivo.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _identifier(*parts: str) -> str:
    """Identifier estable <= 64 octetos (límite de `declarationbase.yaml`)."""
    ident = "com.lucidfence." + ".".join(str(p) for p in parts if p)
    if len(ident.encode("utf-8")) <= 64:
        return ident
    digest = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:16]
    return f"com.lucidfence.{digest}"


def _declaration(decl_type: str, identifier: str, payload: dict) -> dict:
    return {
        "Type": decl_type,
        "Identifier": identifier,
        "ServerToken": _server_token(payload),
        "Payload": payload,
    }


def build_status_subscriptions(status_items=None, *, identifier_suffix: str = "status") -> dict:
    """Declaration de suscripción a los status items que consumimos de vuelta."""
    items = tuple(status_items) if status_items is not None else DEFAULT_STATUS_ITEMS
    payload = {"StatusItems": [{"Name": name} for name in items]}
    return _declaration(
        "com.apple.configuration.management.status-subscriptions",
        _identifier(identifier_suffix),
        payload,
    )


def build_declarations(
    policy: Any,
    fence_state: str,
    profile_url: str,
    *,
    predicate: Optional[str] = None,
    status_items=None,
) -> dict:
    """Construye el juego de declarations para una policy y un estado de geocerca.

    Args:
        policy: `Policy` (o dict con `id`) que se está enforzando.
        fence_state: estado que activa este juego (`inside` / `outside` / ...).
            No viaja dentro del predicado: DDM no evalúa geocercas. El servidor
            envía el juego correspondiente al estado actual.
        profile_url: URL https del perfil MDMv1 alojado por el MDM
            (`com.apple.configuration.legacy` exige https).
        predicate: NSPredicate opcional, pasado tal cual a la activación.
            LucidFence NO sintetiza sintaxis de predicados: Apple no publica
            las variables disponibles en el repo de schemas, así que el que
            integra el MDM aporta el string si lo necesita.
        status_items: nombres de status items a suscribir (por defecto
            `DEFAULT_STATUS_ITEMS`).

    Returns:
        dict con `configurations` (lista de declarations) y `activations`.

    Raises:
        ValueError: si `profile_url` no es https (requisito de Apple).
    """
    if not str(profile_url).startswith("https://"):
        raise ValueError("profile_url must start with https:// (com.apple.configuration.legacy)")

    policy_id = str(_get(policy, "id", "policy") or "policy")
    state = str(fence_state or "unknown").lower()

    legacy = _declaration(
        "com.apple.configuration.legacy",
        _identifier(policy_id, state, "legacy"),
        {"ProfileURL": profile_url},
    )
    subscriptions = build_status_subscriptions(
        status_items, identifier_suffix=f"{policy_id}.status"
    )

    activation_payload = {"StandardConfigurations": [legacy["Identifier"], subscriptions["Identifier"]]}
    if predicate:
        activation_payload["Predicate"] = predicate
    activation = _declaration(
        "com.apple.activation.simple",
        _identifier(policy_id, state, "activation"),
        activation_payload,
    )

    return {"configurations": [legacy, subscriptions], "activations": [activation]}


def parse_status_report(report: Any) -> dict:
    """Traduce un StatusReport de DDM a campos del modelo de estado de dispositivo.

    Acepta las dos formas en que llega `StatusItems`: claves planas
    (`{"device.model.identifier": "iPhone15,2"}`) y anidadas
    (`{"device": {"model": {"identifier": ...}}}`). Los items desconocidos se
    ignoran; los errores del reporte se exponen en `ddm_errors`.
    """
    if not isinstance(report, dict):
        return {}
    items = report.get("StatusItems")
    if not isinstance(items, dict):
        items = {}

    flat: dict = {}

    def _flatten(node, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                _flatten(value, f"{prefix}.{key}" if prefix else str(key))
        elif prefix:
            flat[prefix] = node

    _flatten(items, "")

    out = {}
    for name, field in _STATUS_FIELD_MAP.items():
        if name in flat:
            out[field] = flat[name]

    errors = report.get("Errors")
    if isinstance(errors, list) and errors:
        out["ddm_errors"] = [
            e.get("StatusItem") for e in errors if isinstance(e, dict) and e.get("StatusItem")
        ]
    return out


#: Valores de ejemplo estables para el readback de `ddm_status` en mock.
#: Solo se usan los campos que el device_state del producto persiste; el
#: resto (p.ej. `model_marketing_name`) no viaja y se ignora en silencio.
_MOCK_STATUS_VALUES = {
    "os_version": "17.4.1",
    "model": "iPhone15,2",
    "serial_number": "SIMULATED-SN",
    "passcode_compliant": True,
    "filevault_enabled": None,
    "model_marketing_name": "iPhone 15 Pro",
}


def _mock_decl_status(decl: dict) -> dict:
    """Estado por declaración coherente con la respuesta real de Jamf DDM.

    Jamf no publica endpoint para subir declarations propias. En mock el
    dispositivo no rechaza nada, así que todas las declarations del juego
    convergen en `accepted` - la misma forma que #89 leerá para decidir si
    el camino declarativo es viable (todas `accepted` => declarativo).
    """
    return {
        "identifier": decl["Identifier"],
        "type": decl["Type"],
        "status": "accepted",
        "server_token": decl["ServerToken"],
        "errors": [],
    }


def build_mock_apply_result(
    policy: Any,
    fence_state: str,
    profile_url: str,
    *,
    predicate: Optional[str] = None,
    status_items=None,
) -> dict:
    """Mock de `apply_ddm`: mismo contrato de retorno que el camino real.

    Devuelve las declarations estructuradas (como el modo offline real) más
    el estado por declaración que Jamf expondría tras la entrega.
    """
    declarations = build_declarations(
        policy, fence_state, profile_url,
        predicate=predicate, status_items=status_items,
    )
    return {
        "declarations": declarations,
        "declaration_status": [
            _mock_decl_status(d)
            for d in declarations["configurations"] + declarations["activations"]
        ],
    }


def build_mock_status_result(*, status_items=None) -> dict:
    """Mock de `ddm_status`: readback de status items como lo haría Jamf."""
    items = tuple(status_items) if status_items is not None else DEFAULT_STATUS_ITEMS
    device_state: dict = {}
    for name in items:
        field = _STATUS_FIELD_MAP.get(name)
        if field is None:
            continue
        if field in _MOCK_STATUS_VALUES:
            device_state[field] = _MOCK_STATUS_VALUES[field]
    report = {
        "StatusItems": {
            name: device_state[_STATUS_FIELD_MAP[name]]
            for name in items
            if _STATUS_FIELD_MAP.get(name) in device_state
        }
    }
    return {
        "status_items": len(report["StatusItems"]),
        "device_state": parse_status_report(report),
    }


def build_mock_sync_result(*, reason: str = "declarations_updated") -> dict:
    """Mock de `ddm_sync`: respuesta 204-like coherente con el canal real."""
    return {"jamf_status": 204, "synced": True, "reason": reason}


__all__ = [
    "DDM_MIN_OS",
    "DEFAULT_STATUS_ITEMS",
    "supports_ddm",
    "build_declarations",
    "build_status_subscriptions",
    "parse_status_report",
    "build_mock_apply_result",
    "build_mock_status_result",
    "build_mock_sync_result",
]
