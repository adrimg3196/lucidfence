"""Tests de los canales de notificación multi-webhook (P0.3).

Cubre el webhook genérico firmado (HMAC-SHA256), el canal ntfy y la factory
`build_incident_notifiers`. Sin red: se inyecta un http_post falso.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.notifier import (
    IncidentFanoutNotifier,
    IncidentNotifier,
    NtfyNotifier,
    SignedWebhookNotifier,
    build_incident_notifiers,
)

INCIDENT = {
    "id": "inc-42", "title": "Salida de geocerca", "severity": "high",
    "device_id": "dev-7", "device_name": "Tablet almacén", "fence_id": "hq",
}


class _FakePost:
    def __init__(self, ok: bool = True):
        self.calls: list[tuple] = []
        self.ok = ok

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload, headers or {}))
        return {"ok": self.ok, "status": 200 if self.ok else 500}


def test_signed_webhook_posts_full_incident_with_valid_hmac() -> None:
    post = _FakePost()
    n = SignedWebhookNotifier("https://receptor.example/hook", secret="s3cr3t", http_post=post)
    assert n.enabled() and n.notify("open", INCIDENT) is True

    url, body, headers = post.calls[0]
    assert url == "https://receptor.example/hook"
    assert isinstance(body, bytes)
    payload = json.loads(body)
    assert payload["event"] == "lucidfence.incident"
    assert payload["transition"] == "open"
    assert payload["incident"]["id"] == "inc-42"
    # La firma cubre los bytes exactos enviados y verifica en el receptor.
    sig = headers["X-LucidFence-Signature"]
    assert sig.startswith("sha256=")
    assert SignedWebhookNotifier.verify("s3cr3t", body, sig) is True
    assert SignedWebhookNotifier.verify("otra-clave", body, sig) is False
    assert SignedWebhookNotifier.verify("s3cr3t", body + b"x", sig) is False


def test_signed_webhook_without_secret_sends_no_signature() -> None:
    post = _FakePost()
    n = SignedWebhookNotifier("https://receptor.example/hook", http_post=post)
    assert n.notify("resolved", INCIDENT) is True
    _url, _body, headers = post.calls[0]
    assert "X-LucidFence-Signature" not in headers


def test_ntfy_notifier_sends_plain_text_with_priority_and_auth() -> None:
    post = _FakePost()
    n = NtfyNotifier("https://ntfy.sh/lucidfence-alertas", token="tk_abc", http_post=post)
    assert n.notify("open", INCIDENT) is True
    url, body, headers = post.calls[0]
    assert url == "https://ntfy.sh/lucidfence-alertas"
    assert isinstance(body, str) and "Tablet almacén" in body and "Geocerca: hq" in body
    assert headers["Priority"] == "4"  # high
    assert headers["Authorization"] == "Bearer tk_abc"
    assert "[HIGH]" in headers["Title"]


def test_ntfy_delivery_failure_returns_false_without_raising() -> None:
    n = NtfyNotifier("https://ntfy.sh/topic", http_post=_FakePost(ok=False))
    assert n.notify("open", INCIDENT) is False


def test_build_incident_notifiers_from_config_multi_channel() -> None:
    post = _FakePost()
    channels = build_incident_notifiers({
        "incident_webhook_url": "https://hooks.slack.com/services/T/B/X",
        "incident_webhooks": [
            {"type": "generic", "url": "https://receptor/hook", "secret": "s"},
            {"type": "ntfy", "url": "https://ntfy.sh/t"},
            {"type": "slack", "url": "https://hooks.slack.com/services/T/B/Y"},
            {"type": "paloma-mensajera", "url": "https://ignorado"},  # desconocido
            {"type": "generic", "url": "   "},                        # sin URL
            "no-soy-un-dict",
        ],
    }, http_post=post)
    kinds = [type(c).__name__ for c in channels]
    assert kinds == ["IncidentNotifier", "SignedWebhookNotifier", "NtfyNotifier", "IncidentNotifier"]

    # Fan-out: todos los canales reciben la transición aunque uno falle.
    fan = IncidentFanoutNotifier(channels)
    assert fan.notify("open", INCIDENT) is True
    assert len(post.calls) == 4


def test_build_incident_notifiers_empty_and_malformed_config() -> None:
    assert build_incident_notifiers({}) == []
    assert build_incident_notifiers({"incident_webhooks": "no-es-lista"}) == []


def test_legacy_slack_notifier_signature_unchanged() -> None:
    # El canal legacy sigue llamando http_post con 2 argumentos (compat con
    # fakes existentes) y su payload conserva el contrato Slack.
    calls = []
    def two_arg_post(url, payload):
        calls.append((url, payload))
        return {"ok": True, "status": 200}
    n = IncidentNotifier("https://hooks.slack.com/services/T/B/Z", http_post=two_arg_post)
    assert n.notify("open", INCIDENT) is True
    _url, payload = calls[0]
    assert payload["text"].startswith("[HIGH]") and payload["attachments"]
