"""Incident lifecycle webhook notifier (Slack/Teams incoming-webhook shape).

Stdlib only. The notifier NEVER raises: a failed delivery is recorded and
returns False so the dashboard/engine never crash on a bad webhook URL.

Payload shape follows the Slack incoming-webhook contract
(https://api.slack.com/messaging/webhooks) which Teams also accepts:
    {"text": "...", "attachments": [{"color": ..., "fields": [...]}]}
"""
from __future__ import annotations

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


def _default_http_post(url: str, payload: dict) -> dict:
    """Real HTTP POST via stdlib http.client. Never raises."""
    import http.client
    parsed = urlparse(url)
    host, port = parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
    body = json.dumps(payload).encode("utf-8")
    try:
        if parsed.scheme == "https":
            import ssl
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=10, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=10)
        conn.request("POST", parsed.path or "/", body=body,
                     headers={"Content-Type": "application/json"})
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
