"""IA bridge for LucidFence — consume the local MoA server (127.0.0.1:8085).

Optional local AI integration for incident narratives and digest summaries.
It consumes any OpenAI-compatible MoA server configured on the loopback
interface. When that service is absent, every helper degrades gracefully to
deterministic text and the core geofencing product remains fully functional.

Endpoints used (OpenAI-compatible):
  POST http://127.0.0.1:8085/v1/chat/completions
       body: {messages, moa_dry?, moa_rounds?, moa_agg?, moa_agg_mode?, stream?:false}
       -> {choices:[{message:{content}}], moa:{...}}

Security / design:
  - Talks ONLY to 127.0.0.1 (no external calls).
  - never raises: a missing/unreachable MoA returns None and the caller falls
    back to the plain-text builder.
  - No secrets; MoA itself holds the free-tier API keys in its own .env.
"""
from __future__ import annotations

import json
import http.client
import os
import socket
from typing import Optional

MOA_HOST = os.environ.get("LUCIDFENCE_MOA_HOST", "127.0.0.1")
MOA_PORT = int(os.environ.get("LUCIDFENCE_MOA_PORT", "8085"))
MOA_TIMEOUT = float(os.environ.get("LUCIDFENCE_MOA_TIMEOUT", "25"))


def _post(messages: list, *, dry: bool = True, rounds: int = 2,
          agg_mode: str = "synthesize", stream: bool = False) -> Optional[dict]:
    """Call MoA chat/completions. Returns the parsed JSON or None on any failure."""
    payload = json.dumps({
        "messages": messages,
        "moa_dry": dry,
        "moa_rounds": rounds,
        "moa_agg_mode": agg_mode,
        "stream": stream,
    }).encode("utf-8")
    conn: Optional[http.client.HTTPConnection] = None
    try:
        conn = http.client.HTTPConnection(MOA_HOST, MOA_PORT, timeout=MOA_TIMEOUT)
        conn.request(
            "POST", "/v1/chat/completions", body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        if resp.status != 200:
            return None
        return json.loads(raw)
    except (OSError, socket.timeout, ValueError, http.client.HTTPException):
        return None
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _content(data: Optional[dict]) -> Optional[str]:
    if not data:
        return None
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return None


def available() -> bool:
    """True if MoA is reachable."""
    try:
        conn = http.client.HTTPConnection(MOA_HOST, MOA_PORT, timeout=4.0)
        conn.request("GET", "/")
        ok = conn.getresponse().status == 200
        conn.close()
        return ok
    except Exception:
        return False


# --------------------------------------------------------------------------
# Domain helpers — each returns a string (IA if available, else plain text).
# --------------------------------------------------------------------------

def incident_narrative(device: dict, *, dry: bool = True) -> str:
    """Human narrative for a geofence/incident event (used by AtomicMailNotifier)."""
    name = device.get("name") or device.get("device_id") or "dispositivo"
    state = device.get("fence_state") or device.get("state") or "desconocido"
    risk = device.get("risk_score") or 0
    compliant = device.get("compliant")
    plain = (
        f"Incidente de geocerca: {name} está {state}. "
        f"Riesgo {risk}/100"
        + (f", non-compliant." if compliant is False else ".")
    )
    if not available():
        return plain
    msg = (
        f"Eres el motor de seguridad de LucidFence (UEM/MDM). Escribe un párrafo "
        f"conciso y profesional (máx 2 frases) para el equipo SOC sobre este incidente "
        f"de geocerca, en español: dispositivo '{name}', estado '{state}', "
        f"riesgo {risk}/100"
        + (", non-compliant." if compliant is False else ".")
        + " No inventes datos técnicos que no se den."
    )
    data = _post([{"role": "user", "content": msg}], dry=dry)
    return _content(data) or plain


def digest_summary(stats: dict, devices: list, *, dry: bool = True) -> str:
    """Executive summary paragraph for the fleet digest email."""
    total = len(devices)
    outside = sum(1 for d in devices if d.get("fence_state") == "outside")
    noncompliant = sum(1 for d in devices if d.get("compliant") is False)
    high = sum(1 for d in devices if (d.get("risk_score") or 0) >= 70)
    plain = (
        f"Resumen: {total} dispositivos, {outside} fuera de geocerca, "
        f"{noncompliant} non-compliant, {high} en riesgo alto."
    )
    if not available():
        return plain
    top = sorted(devices, key=lambda x: -(x.get("risk_score") or 0))[:5]
    ctx = "; ".join(
        f"{d.get('name') or d.get('device_id')} (riesgo {d.get('risk_score') or 0}, {d.get('fence_state')})"
        for d in top
    )
    msg = (
        f"Eres LucidFence. Redacta un resumen ejecutivo de 2-3 frases para el CISO "
        f"sobre el estado de la flota (español, tono ejecutivo): {total} dispositivos, "
        f"{outside} fuera de geocerca, {noncompliant} non-compliant, {high} en riesgo alto. "
        f"Top riesgo: {ctx}. No inventes cifras."
    )
    data = _post([{"role": "user", "content": msg}], dry=dry)
    return _content(data) or plain


def alert_blurb(firing: dict, *, dry: bool = True) -> str:
    """Short blurb for a threshold alert delivery."""
    plain = (
        f"Alerta {firing.get('rule_type')} en {firing.get('device_name') or firing.get('device_id')} "
        f"(riesgo {firing.get('severity')})."
    )
    if not available():
        return plain
    msg = (
        f"Eres LucidFence. Escribe una línea (máx 1 frase, español) para notificar esta "
        f"alerta de MDM/UEM: tipo '{firing.get('rule_type')}', dispositivo "
        f"'{firing.get('device_name') or firing.get('device_id')}', severidad "
        f"'{firing.get('severity')}'. Sin tecnicismos innecesarios."
    )
    data = _post([{"role": "user", "content": msg}], dry=dry)
    return _content(data) or plain


def support_reply(ticket: dict, *, dry: bool = True) -> str:
    """Draft a support reply for a tenant ticket."""
    subject = ticket.get("subject") or ticket.get("topic") or "consulta"
    body = ticket.get("body") or ticket.get("message") or ""
    plain = f"Hola, gracias por tu consulta sobre '{subject}'. Te ayudamos en breve."
    if not available():
        return plain
    msg = (
        f"Eres el soporte de LucidFence (plataforma de geocercas UEM/MDM 100% local). "
        f"Redacta una respuesta de soporte útil y cercana (español, máx 3 frases) para "
        f"este ticket. Asunto: '{subject}'. Mensaje del cliente: '{body}'. "
        f"Si no tienes la respuesta exacta, ofrece seguimiento sin inventar."
    )
    data = _post([{"role": "user", "content": msg}], dry=dry)
    return _content(data) or plain
