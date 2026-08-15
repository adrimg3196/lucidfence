"""Incident lifecycle notifiers (Slack/Teams, webhook firmado, ntfy, email).

Stdlib only. The notifier NEVER raises: a failed delivery is recorded and
returns False so the dashboard/engine never crash on a bad webhook URL.

Channels:
- IncidentNotifier — Slack incoming-webhook shape (Teams also accepts it):
    {"text": "...", "attachments": [{"color": ..., "fields": [...]}]}
- SignedWebhookNotifier — full incident JSON to any endpoint, optionally
  signed with HMAC-SHA256 (header X-LucidFence-Signature) so the receiver
  can verify origin without any shared infrastructure.
- NtfyNotifier — plain-text push to an ntfy topic (ntfy.sh or self-hosted).
- AtomicMailNotifier — email via the tenant's Atomic Mail inbox.
- IncidentFanoutNotifier — best-effort fan-out over any of the above.

Config (tenant config / config.json):
    incident_webhook_url: "https://hooks.slack.com/..."   # legacy, Slack-shape
    incident_webhooks:                                     # multi-canal
      - {"type": "slack",   "url": "https://hooks.slack.com/..."}
      - {"type": "generic", "url": "https://mi-endpoint/hook", "secret": "s3cr3t"}
      - {"type": "ntfy",    "url": "https://ntfy.sh/mi-topic", "token": "tk_..."}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Callable, Optional
from urllib.parse import urlparse

# Severity -> Slack attachment color
_SEVERITY_COLOR = {
    "critical": "#b42318",
    "high": "#d92d20",
    "medium": "#f79009",
    "low": "#2e90fa",
    "info": "#475467",
}

_VERB = {
    "open": "nuevo incidente",
    "acknowledged": "incidente en investigación",
    "resolved": "incidente resuelto",
}


def _default_http_post(url: str, payload, headers: Optional[dict] = None) -> dict:
    """Real HTTP POST via stdlib http.client. Never raises.

    `payload` dict/list → JSON body; str/bytes → raw body (ntfy usa texto plano).
    """
    import http.client
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    if isinstance(payload, bytes):
        body = payload
        default_ct = "text/plain; charset=utf-8"
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
        default_ct = "text/plain; charset=utf-8"
    else:
        body = json.dumps(payload).encode("utf-8")
        default_ct = "application/json"
    send_headers = {"Content-Type": default_ct}
    send_headers.update(headers or {})
    try:
        if parsed.scheme == "https":
            import ssl
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=10, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=10)
        conn.request("POST", parsed.path or "/", body=body, headers=send_headers)
        r = conn.getresponse()
        status = r.status
        conn.close()
        return {"ok": 200 <= status < 300, "status": status}
    except Exception as exc:  # noqa: BLE001 - never propagate
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


class IncidentNotifier:
    def __init__(self, webhook_url: str = "", http_post: Optional[Callable] = None):
        self.webhook_url = (webhook_url or "").strip()
        self._post = http_post or _default_http_post
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def notify(self, transition: str, incident: dict) -> bool:
        """POST an incident event to the webhook. Returns True if delivered.

        `transition` is one of: open | acknowledged | resolved. Suppressed
        transitions (reopen etc.) are still delivered but labeled generically.
        Never raises.
        """
        if not self.webhook_url:
            return False
        try:
            payload = self._build(transition, incident)
            res = self._post(self.webhook_url, payload)
            self.last_result = res
            self.deliveries.append({"transition": transition,
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "result": res})
            return bool(res.get("ok")) if isinstance(res, dict) else False
        except Exception:  # noqa: BLE001 - never propagate
            return False

    def _build(self, transition: str, inc: dict) -> dict:
        severity = (inc.get("severity") or "info").lower()
        color = _SEVERITY_COLOR.get(severity, "#475467")
        verb = _VERB.get(transition, transition)
        title = inc.get("title") or inc.get("id") or "Incidente"
        device = inc.get("device_name") or inc.get("device_id") or "—"
        text = f"[{severity.upper()}] {verb}: {title} ({device})"
        fields = [
            {"title": "ID", "value": str(inc.get("id") or "—"), "short": True},
            {"title": "Severidad", "value": severity, "short": True},
            {"title": "Dispositivo", "value": device, "short": True},
            {"title": "Estado", "value": transition, "short": True},
        ]
        if inc.get("assignee"):
            fields.append({"title": "Asignado a", "value": str(inc["assignee"]), "short": True})
        if inc.get("fence_id"):
            fields.append({"title": "Geocerca", "value": str(inc["fence_id"]), "short": True})
        return {
            "text": text,
            "attachments": [{
                "color": color,
                "fields": fields,
                "footer": "LucidFence",
            }],
        }


class IncidentFanoutNotifier:
    """Fan out one incident transition to multiple notification channels.

    Used when a tenant configures both an incoming webhook and Atomic Mail.
    Delivery is best-effort per channel: one failing channel must not prevent the
    other from receiving a real-time geofence/incident alert.
    """

    def __init__(self, notifiers: list[Any]):
        self.notifiers = [n for n in notifiers if n is not None]
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        for notifier in self.notifiers:
            try:
                enabled = getattr(notifier, "enabled", None)
                if enabled is None or enabled():
                    return True
            except Exception:  # noqa: BLE001 - ignore broken channel probes
                continue
        return False

    def notify(self, transition: str, incident: dict) -> bool:
        results = []
        delivered = False
        for notifier in self.notifiers:
            try:
                ok = bool(notifier.notify(transition, incident))
                results.append({
                    "channel": type(notifier).__name__,
                    "ok": ok,
                    "last_result": getattr(notifier, "last_result", None),
                })
                delivered = delivered or ok
            except Exception as exc:  # noqa: BLE001 - never propagate
                results.append({
                    "channel": type(notifier).__name__,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                })
        self.last_result = {"ok": delivered, "results": results}
        self.deliveries.append({
            "transition": transition,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "result": self.last_result,
        })
        return delivered


class AtomicMailNotifier:
    """Incident lifecycle notifier that emails via Atomic Mail Agentic.

    Wraps a ``core.atomicmail_client.TenantMailbox`` so incidents (open /
    acknowledged / resolved) are delivered as real email through the tenant's
    @atomicmail.ai inbox. Never raises: a failed send is recorded and returns
    False so the engine cycle never 500s because email is down.

    ``to`` is the recipient address (e.g. the SOC mailbox). The mailbox itself
    is the sender and is owned by the tenant's data directory.
    """

    def __init__(self, mailbox, to: str = "", subject_prefix: str = "[LucidFence]"):
        self.mailbox = mailbox
        self.to = (to or "").strip()
        self.subject_prefix = subject_prefix
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.to) and self.mailbox is not None

    def notify(self, transition: str, incident: dict) -> bool:
        if not self.enabled():
            return False
        try:
            severity = (incident.get("severity") or "info").lower()
            verb = _VERB.get(transition, transition)
            title = incident.get("title") or incident.get("id") or "Incidente"
            device = incident.get("device_name") or incident.get("device_id") or "—"
            subject = f"{self.subject_prefix} [{severity.upper()}] {verb}: {title}"
            text = (
                f"{verb.capitalize()} de incidente\n"
                f"ID: {incident.get('id') or '—'}\n"
                f"Severidad: {severity}\n"
                f"Dispositivo: {device}\n"
                f"Estado: {transition}\n"
            )
            if incident.get("fence_id"):
                text += f"Geocerca: {incident['fence_id']}\n"
            if incident.get("assignee"):
                text += f"Asignado a: {incident['assignee']}\n"
            ok = self.mailbox.send(to=self.to, subject=subject, text=text)
            self.last_result = {"ok": ok}
            self.deliveries.append({
                "transition": transition,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "result": self.last_result,
            })
            return bool(ok)
        except Exception:  # noqa: BLE001 - never propagate
            return False


class SignedWebhookNotifier:
    """Generic webhook: full incident JSON, optionally HMAC-SHA256 signed.

    Payload: {"event": "lucidfence.incident", "transition": ..., "ts": ...,
              "incident": {...}}
    With `secret` set, adds header:
        X-LucidFence-Signature: sha256=<hex hmac of the exact request body>
    so the receiver can verify origin and integrity offline — no shared infra.
    """

    def __init__(self, url: str, secret: str = "", http_post: Optional[Callable] = None):
        self.url = (url or "").strip()
        self.secret = (secret or "").strip()
        self._post = http_post or _default_http_post
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.url)

    @staticmethod
    def signature(secret: str, body: bytes) -> str:
        return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    @staticmethod
    def verify(secret: str, body: bytes, header_value: str) -> bool:
        """Receiver-side helper: constant-time signature check."""
        expected = SignedWebhookNotifier.signature(secret, body)
        return hmac.compare_digest(expected, (header_value or "").strip())

    def notify(self, transition: str, incident: dict) -> bool:
        if not self.url:
            return False
        try:
            payload = {
                "event": "lucidfence.incident",
                "transition": transition,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "incident": incident,
            }
            # Firmamos los bytes exactos que se envían: el body va como bytes
            # para que la firma no dependa de re-serializaciones del receptor.
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self.secret:
                headers["X-LucidFence-Signature"] = self.signature(self.secret, body)
            res = self._post(self.url, body, headers)
            self.last_result = res
            self.deliveries.append({"transition": transition,
                                    "ts": payload["ts"], "result": res})
            return bool(res.get("ok")) if isinstance(res, dict) else False
        except Exception:  # noqa: BLE001 - never propagate
            return False


# ntfy priority per incident severity (https://docs.ntfy.sh/publish/#message-priority)
_NTFY_PRIORITY = {"critical": "5", "high": "4", "medium": "3", "low": "2", "info": "1"}


class NtfyNotifier:
    """Push to an ntfy topic (ntfy.sh or self-hosted) — plain text + headers.

    `url` is the full topic URL (e.g. https://ntfy.sh/lucidfence-alertas).
    `token` (optional) is an ntfy access token sent as Bearer auth.
    """

    def __init__(self, url: str, token: str = "", http_post: Optional[Callable] = None):
        self.url = (url or "").strip()
        self.token = (token or "").strip()
        self._post = http_post or _default_http_post
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.url)

    def notify(self, transition: str, incident: dict) -> bool:
        if not self.url:
            return False
        try:
            severity = (incident.get("severity") or "info").lower()
            verb = _VERB.get(transition, transition)
            title = incident.get("title") or incident.get("id") or "Incidente"
            device = incident.get("device_name") or incident.get("device_id") or "—"
            lines = [f"{verb.capitalize()}: {title}", f"Dispositivo: {device}"]
            if incident.get("fence_id"):
                lines.append(f"Geocerca: {incident['fence_id']}")
            headers = {
                "Title": f"[LucidFence] [{severity.upper()}] {verb}",
                "Priority": _NTFY_PRIORITY.get(severity, "3"),
                "Tags": "round_pushpin" if transition == "open" else "white_check_mark",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            res = self._post(self.url, "\n".join(lines), headers)
            self.last_result = res
            self.deliveries.append({"transition": transition,
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "result": res})
            return bool(res.get("ok")) if isinstance(res, dict) else False
        except Exception:  # noqa: BLE001 - never propagate
            return False


def build_incident_notifiers(config: dict, http_post: Optional[Callable] = None) -> list:
    """Build the incident notifier channels declared in config.

    Reads the legacy `incident_webhook_url` (Slack-shape, kept for
    compatibility) plus the multi-channel `incident_webhooks` list. Unknown
    types and empty URLs are skipped: a config typo must never take the
    engine down. Returns a (possibly empty) list of notifier objects.
    """
    notifiers: list = []
    legacy = (config.get("incident_webhook_url") or "").strip()
    if legacy:
        notifiers.append(IncidentNotifier(webhook_url=legacy, http_post=http_post))
    entries = config.get("incident_webhooks") or []
    if not isinstance(entries, list):
        return notifiers
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = (entry.get("url") or "").strip()
        if not url:
            continue
        kind = (entry.get("type") or "generic").strip().lower()
        if kind == "slack":
            notifiers.append(IncidentNotifier(webhook_url=url, http_post=http_post))
        elif kind == "ntfy":
            notifiers.append(NtfyNotifier(url, token=entry.get("token") or "",
                                          http_post=http_post))
        elif kind == "generic":
            notifiers.append(SignedWebhookNotifier(url, secret=entry.get("secret") or "",
                                                   http_post=http_post))
        # tipos desconocidos: se ignoran (fail-soft)
    return notifiers
