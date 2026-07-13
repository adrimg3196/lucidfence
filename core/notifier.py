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
                "footer": "Geofence UEM",
            }],
        }
