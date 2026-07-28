"""Workflows integrados — plantillas listas para Applivery + creación fácil.

Por qué existe este módulo (pedido del usuario):
  "quiero que tenga un apartado de lógica de workflows integrados ya hechos
   de uso sencillos comunes para usar con applivery y si no de creación
   por el admin it pero poniéndoselo fácil"

El motor de políticas (core/policies.py) YA soporta "trigger (when) + acciones
Applivery". Este módulo es la CAPA DE PRESENTACIÓN sobre ese motor:
  * TEMPLATES  -> workflows ya hechos, comunes, un click para activar.
  * build_custom_policy() -> el admin IT construye uno SIN tocar JSON: elige
    disparador + condición + acción Applivery desde un formulario sencillo.

El resultado de ambos es SIEMPRE un dict Policy válido (when + actions) que el
engine ejecuta contra el LiveAdapter de Applivery (lock/wipe/message/locate/...).

100% local, stdlib only, sin deps nuevas, sin secretos hardcodeados.
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional

# ----------------------------------------------------------------------------
# Catálogo de acciones Applivery (lo que el LiveAdapter sabe ejecutar).
# Cada acción tiene label ES + params por defecto para el formulario.
# ----------------------------------------------------------------------------
APPLIVERY_ACTIONS: dict[str, dict] = {
    "lock": {
        "label": "Bloquear dispositivo",
        "desc": "Bloquea el dispositivo (pantalla de bloqueo remoto).",
        "params": {},
    },
    "wipe": {
        "label": "Borrado de datos (wipe)",
        "desc": "Borra los datos del dispositivo de forma remota.",
        "params": {},
    },
    "message": {
        "label": "Enviar mensaje / aviso",
        "desc": "Empuja un mensaje al dispositivo (p. ej. aviso al comercial).",
        "params": {"text": "Aviso de cumplimiento de ruta"},
    },
    "locate": {
        "label": "Localizar dispositivo",
        "desc": "Fuerza una localización del dispositivo.",
        "params": {},
    },
    "reboot": {
        "label": "Reiniciar dispositivo",
        "desc": "Reinicia el dispositivo de forma remota.",
        "params": {},
    },
    "clear_passcode": {
        "label": "Limpiar código de acceso",
        "desc": "Quita el código de acceso del dispositivo.",
        "params": {},
    },
    "notify": {
        "label": "Notificar equipo de seguridad (interno)",
        "desc": "Notifica al canal interno (security/ciso) sin tocar el dispositivo.",
        "params": {"channel": "security", "msg": "Evento de cumplimiento"},
    },
    "custom": {
        "label": "Comando personalizado Applivery",
        "desc": "Comando crudo de Applivery (type + params).",
        "params": {"type": "custom", "args": ""},
    },
}

# ----------------------------------------------------------------------------
# Plantillas comunes (workflows ya hechos). Cada una es una Policy llave-lista.
# Los `when` usan la misma sintaxis que core/policies.py:
#   field / op / value   (field puede ser signal:<provider>.<key>)
# ----------------------------------------------------------------------------
TEMPLATES: list[dict] = [
    {
        "id": "wf-block-on-route-exit",
        "name": "Bloquear al salir de la ruta",
        "summary": "Si el comercial se sale del corredor de su ruta asignada, "
                   "bloquear el dispositivo y avisarle.",
        "trigger_label": "Comercial fuera de ruta",
        "when": [
            {"field": "signal:route_state.route_state", "op": "eq", "value": "off_route"},
        ],
        "actions": [
            {"action": "notify", "params": {"channel": "security",
             "msg": "Comercial fuera de ruta asignada"}},
            {"action": "message", "params": {"text": "Has salido de tu ruta. Contacta con tu responsable."}},
        ],
        "severity": "high",
    },
    {
        "id": "wf-wipe-rooted-outside",
        "name": "Wipe si rooteado fuera de geocerca",
        "summary": "Dispositivo con root/jailbreak y fuera de su geocerca permitida "
                   "-> borrado de datos y aviso a CISO (fuga de datos probable).",
        "trigger_label": "Root + fuera de geocerca",
        "when": [
            {"field": "fence_state", "op": "eq", "value": "outside"},
            {"field": "signal:device_health.rooted", "op": "eq", "value": True},
        ],
        "actions": [
            {"action": "notify", "params": {"channel": "ciso",
             "msg": "CRITICO: rooteado fuera de geocerca"}},
            {"action": "wipe", "params": {}},
        ],
        "severity": "critical",
    },
    {
        "id": "wf-ciso-deviation-500",
        "name": "Avisar CISO si desviación > 500 m",
        "summary": "Desviación de ruta mayor a 500 m -> notificar al CISO "
                   "(sin acción destructiva sobre el dispositivo).",
        "trigger_label": "Desviación de ruta > 500 m",
        "when": [
            {"field": "signal:route_state.route_state", "op": "eq", "value": "off_route"},
            {"field": "signal:route_state.route_deviation_m", "op": "gt", "value": 500},
        ],
        "actions": [
            {"action": "notify", "params": {"channel": "ciso",
             "msg": "Comercial con desviación de ruta > 500 m"}},
        ],
        "severity": "high",
    },
    {
        "id": "wf-isolate-offshift-outside",
        "name": "Aislar fuera de turno y fuera de geocerca",
        "summary": "Dispositivo fuera de su geocerca Y fuera de su turno asignado "
                   "-> bloquear y notificar seguridad.",
        "trigger_label": "Fuera de turno + fuera de geocerca",
        "when": [
            {"field": "fence_state", "op": "eq", "value": "outside"},
            {"field": "signal:shift_match.shift_match", "op": "eq", "value": False},
            {"field": "signal:shift_match.shift_known", "op": "eq", "value": True},
        ],
        "actions": [
            {"action": "notify", "params": {"channel": "security",
             "msg": "Fuera de geocerca fuera de turno"}},
            {"action": "lock", "params": {}},
        ],
        "severity": "high",
    },
    {
        "id": "wf-locate-unknown-noncompliant",
        "name": "Localizar si ubicación perdida y no conforme",
        "summary": "Señal de ubicación perdida (unknown) en dispositivo no conforme "
                   "-> localizar (posible robo).",
        "trigger_label": "Ubicación perdida + no conforme",
        "when": [
            {"field": "fence_state", "op": "eq", "value": "unknown"},
            {"field": "compliant", "op": "eq", "value": False},
        ],
        "actions": [
            {"action": "locate", "params": {}},
            {"action": "notify", "params": {"channel": "security",
             "msg": "Ubicación perdida en dispositivo no conforme"}},
        ],
        "severity": "medium",
    },
]


def get_template(tpl_id: str) -> Optional[dict]:
    for t in TEMPLATES:
        if t["id"] == tpl_id:
            return t
    return None


def build_policy_from_template(tpl_id: str, device_ids: Optional[list[str]] = None) -> dict:
    """Materializa una plantilla en un dict Policy listo para policies.json.

    `device_ids`: si se pasa, se añade una condición de dispositivo (opcional).
    """
    tpl = get_template(tpl_id)
    if tpl is None:
        raise ValueError(f"plantilla desconocida: {tpl_id}")
    when = [dict(c) for c in tpl["when"]]
    if device_ids:
        when.append({"field": "device_id", "op": "in", "value": list(device_ids)})
    return {
        "id": f"pol-{tpl['id']}",
        "name": tpl["name"],
        "description": tpl["summary"],
        "severity": tpl.get("severity", "medium"),
        "enabled": True,
        "when": when,
        "actions": [dict(a) for a in tpl["actions"]],
        "source": "template",
        "template_id": tpl["id"],
    }


def build_custom_policy(form: dict) -> dict:
    """Construye una Policy desde un formulario SENCILLO del admin IT.

    Campos esperados (todos opcionales salvo name + trigger):
      name            : str  (nombre del workflow)
      trigger         : uno de los disparadores simples:
                          "route_exit"      -> comercial fuera de ruta
                          "outside_fence"   -> fuera de geocerca
                          "rooted"          -> dispositivo rooteado
                          "noncompliant"    -> no conforme
                          "unknown_location" -> ubicación perdida
                          "offshift_outside" -> fuera de turno + fuera de geocerca
      min_deviation_m : int  (opcional, solo si trigger=route_exit)
      action          : una de APPLIVERY_ACTIONS (p.ej. "lock", "wipe", "message")
      action_text     : str  (opcional, para message/notify)
      severity        : low|medium|high|critical (def. medium)
      device_ids      : list[str] (opcional, restringe a esos dispositivos)
    """
    name = (form.get("name") or "").strip()
    if not name:
        raise ValueError("el nombre del workflow es obligatorio")
    trigger = form.get("trigger")
    if trigger not in _TRIGGER_BUILDERS:
        raise ValueError(
            "trigger inválido; usa uno de: " + ", ".join(_TRIGGER_BUILDERS)
        )
    action = form.get("action")
    if action not in APPLIVERY_ACTIONS:
        raise ValueError(
            "acción inválida; usa una de: " + ", ".join(APPLIVERY_ACTIONS)
        )
    severity = form.get("severity", "medium")
    if severity not in ("low", "medium", "high", "critical"):
        severity = "medium"

    when = _TRIGGER_BUILDERS[trigger](form)
    device_ids = form.get("device_ids") or []
    if device_ids:
        when.append({"field": "device_id", "op": "in", "value": list(device_ids)})

    params: dict = {}
    if action in ("message", "notify"):
        txt = (form.get("action_text") or "").strip()
        if action == "message":
            params = {"text": txt or "Aviso de cumplimiento"}
        else:
            params = {"channel": "security", "msg": txt or name}
    elif action == "custom":
        params = {"type": form.get("custom_type", "custom"),
                  "args": form.get("custom_args", "")}

    return {
        "id": f"pol-custom-{int(time.time()*1000)}-{os.urandom(3).hex()}",
        "name": name,
        "description": form.get("description") or f"Workflow personalizado: {name}",
        "severity": severity,
        "enabled": True,
        "when": when,
        "actions": [{"action": action, "params": params}],
        "source": "custom",
    }


# --- mapeo trigger simple -> lista de condiciones `when` -----------------------
def _trig_route_exit(form: dict) -> list[dict]:
    when = [{"field": "signal:route_state.route_state", "op": "eq", "value": "off_route"}]
    md = form.get("min_deviation_m")
    if md:
        try:
            md_int = int(md)
        except (TypeError, ValueError):
            raise ValueError(f"min_deviation_m debe ser un número entero, recibí: {md!r}")
        when.append({
            "field": "signal:route_state.route_deviation_m",
            "op": "gt", "value": md_int,
        })
    return when


def _trig_outside_fence(form: dict) -> list[dict]:
    return [{"field": "fence_state", "op": "eq", "value": "outside"}]


def _trig_rooted(form: dict) -> list[dict]:
    return [{"field": "signal:device_health.rooted", "op": "eq", "value": True}]


def _trig_noncompliant(form: dict) -> list[dict]:
    return [{"field": "compliant", "op": "eq", "value": False}]


def _trig_unknown_location(form: dict) -> list[dict]:
    return [{"field": "fence_state", "op": "eq", "value": "unknown"}]


def _trig_offshift_outside(form: dict) -> list[dict]:
    return [
        {"field": "fence_state", "op": "eq", "value": "outside"},
        {"field": "signal:shift_match.shift_match", "op": "eq", "value": False},
        {"field": "signal:shift_match.shift_known", "op": "eq", "value": True},
    ]


_TRIGGER_BUILDERS = {
    "route_exit": _trig_route_exit,
    "outside_fence": _trig_outside_fence,
    "rooted": _trig_rooted,
    "noncompliant": _trig_noncompliant,
    "unknown_location": _trig_unknown_location,
    "offshift_outside": _trig_offshift_outside,
}


def trigger_options() -> list[dict]:
    """Labels ES para el <select> del formulario de creación."""
    return [
        {"value": "route_exit", "label": "Comercial fuera de su ruta"},
        {"value": "outside_fence", "label": "Fuera de geocerca permitida"},
        {"value": "rooted", "label": "Dispositivo rooteado/jailbreak"},
        {"value": "noncompliant", "label": "Dispositivo no conforme"},
        {"value": "unknown_location", "label": "Ubicación perdida (sin señal)"},
        {"value": "offshift_outside", "label": "Fuera de turno y fuera de geocerca"},
    ]


def action_options() -> list[dict]:
    """Labels ES del catálogo Applivery para el <select> de acción."""
    return [
        {"value": k, "label": v["label"], "desc": v["desc"]}
        for k, v in APPLIVERY_ACTIONS.items()
    ]
