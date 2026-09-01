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


#: Acciones imperativas con equivalente declarativo MODELADO en este módulo.
#:
#: Solo hay uno, y es el único que `build_declarations` sabe construir: entregar
#: el perfil de la política del estado de geocerca vía
#: `com.apple.configuration.legacy`. En LucidFence `lock` es "aplica la postura
#: restrictiva de este estado de geocerca", y esa postura viaja en ese perfil.
#:
#: Lo que NO está aquí es deliberado: Apple no publica declarations para
#: `wipe` (EraseDevice), `reboot` (RestartDevice), `clear_passcode`
#: (ClearPasscode), `locate` ni `message` — siguen siendo comandos MDMv1. No se
#: inventan equivalencias: lo que Apple no modela, va imperativo.
DECLARATIVE_EQUIVALENTS = {"lock": "apply_ddm"}


def _declaration_inputs_ready(params: Any) -> bool:
    """True si el llamante aportó lo mínimo para construir las declarations.

    `build_declarations` exige la policy y una `profile_url` https (requisito de
    `com.apple.configuration.legacy`). Sin ellas no hay nada declarativo que
    enviar: se devuelve el camino imperativo en vez de fabricar un perfil vacío.
    """
    if not isinstance(params, dict):
        return False
    if not params.get("policy"):
        return False
    return str(params.get("profile_url", "") or "").startswith("https://")


def ddm_declarative_subaction(
    device: Any, action: Any, adapter: Any, params: Any = None
) -> Optional[str]:
    """[Renombrado en #205/#88] Acción declarativa a usar para `action`, o None.

    Función pura: no toca red, estado ni configuración. Decide SOLO el
    transporte — el gating (dry_run, fase observe/enforce, allow-list de
    acciones, doble llave del wipe, cooldown, audit) es del engine y se aplica
    igual sea cual sea la vía.

    Criterio (los cuatro, en AND):
      1. el adapter declara `supports_ddm` (capacidad del UEM),
      2. la acción tiene equivalente declarativo modelado aquí,
      3. el dispositivo admite DDM (`supports_ddm(device)`: plataforma + OS),
      4. el llamante aportó el perfil que ese equivalente entrega.

    Readback-honesto: cualquier dato desconocido (adapter sin flag, `os_version`
    ausente, perfil no aportado) devuelve None, es decir, exactamente el
    comportamiento imperativo de hoy. Nunca se adivina capacidad.
    """
    if not getattr(adapter, "supports_ddm", False):
        return None
    declarative = DECLARATIVE_EQUIVALENTS.get(action)
    if declarative is None:
        return None
    if not supports_ddm(device):
        return None
    if not _declaration_inputs_ready(params):
        return None
    return declarative


# Backward-compatibility alias. The bare name ``declarative_path_for`` now
# collides with the management_mode/ownership gate in
# ``lucidfence.core.declarative`` (the #88/#89 single source of truth for
# routing). This module-level alias keeps legacy import paths working but is
# DEPRECATED: new code must call ``ddm_declarative_subaction`` directly.
declarative_path_for = ddm_declarative_subaction


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


def build_mock_status_result() -> dict:
    """Mock de readback DDM para ``ddm_status`` en modo simulación (issue #71).

    Devuelve la misma FORMA que la respuesta real de Jamf (``status_items`` +
    ``device_state``), pero vacía/general, sin datos de dispositivo reales.
    El engine (#89) puede leer el contrato sin un tenant Jamf real.
    """
    return {
        "status_items": [],
        "device_state": {},
    }


def build_mock_sync_result() -> dict:
    """Mock de confirmación DDM para ``ddm_sync`` en modo simulación (issue #71).

    Devuelve la misma FORMA que la respuesta real de Jamf (204 sin cuerpo),
    expuesta como dict para que el engine pueda leerla sin un tenant Jamf real.
    """
    return {
        "jamf_status": 204,
        "synced": True,
    }


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


__all__ = [
    "DDM_MIN_OS",
    "DEFAULT_STATUS_ITEMS",
    "DECLARATIVE_EQUIVALENTS",
    "supports_ddm",
    "ddm_declarative_subaction",
    "declarative_path_for",  # deprecated alias of ddm_declarative_subaction
    "build_declarations",
    "build_status_subscriptions",
    "build_mock_status_result",
    "build_mock_sync_result",
    "parse_status_report",
]
