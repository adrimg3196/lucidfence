"""Egress allow/deny-list por tenant para webhooks salientes (t_f33e2f23).

Cubre los criterios de aceptación del producto (t_316b8ec5):
  1. Default `permissive` (comportamiento actual); `strict` opt-in vía config.
  2. strict permite hooks.slack.com, deniega otro host; strict deniega RFC1918
     salvo allow_private:true.
  3. Entrega denegada produce resultado explícito `denied_by_egress_policy`
     (nunca silencioso).

Sin red real: se inyecta un http_post falso que registra las llamadas.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.notifier import (
    EgressAllowListPolicy,
    IncidentFanoutNotifier,
    IncidentNotifier,
    NtfyNotifier,
    SignedWebhookNotifier,
    _egress_check,
    build_incident_notifiers,
)

INCIDENT = {
    "id": "inc-42", "title": "Salida de geocerca", "severity": "high",
    "device_id": "dev-7", "device_name": "Tablet almacén", "fence_id": "hq",
}


class _FakePost:
    def __init__(self, ok: bool = True):
        self.calls = []
        self.ok = ok

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload, headers or {}))
        return {"ok": self.ok, "status": 200 if self.ok else 500}


# ---- Criterio 1: default permissive, strict opt-in -------------------------

def test_default_policy_is_permissive():
    p = EgressAllowListPolicy.from_config({})
    assert p.is_strict() is False
    # permissive never blocks
    assert _egress_check("https://anything.example/x", p) is None
    # also when egress_policy key is absent entirely
    assert _egress_check("https://evil.example/x", EgressAllowListPolicy()) is None


def test_malformed_policy_degrades_to_permissive():
    # A malformed policy must never break existing deployments.
    assert EgressAllowListPolicy.from_config({"egress_policy": "garbage"}).is_strict() is False
    assert EgressAllowListPolicy.from_config({"egress_policy": {}}).is_strict() is False


def test_strict_opt_in_requires_explicit_mode():
    p = EgressAllowListPolicy.from_config({"egress_policy": {"mode": "strict"}})
    assert p.is_strict() is True


# ---- Criterio 2: allow-list matching ----------------------------------------

def test_strict_allows_listed_host_and_denies_other():
    cfg = {"egress_policy": {"mode": "strict",
                             "allow": ["hooks.slack.com", ".slack.com", "10.20.30.40"]}}
    p = EgressAllowListPolicy.from_config(cfg)
    # allow-list membership
    assert p.allows_host("hooks.slack.com") is True          # exact
    assert p.allows_host("sub.hooks.slack.com") is True       # suffix .slack.com
    assert p.allows_host("10.20.30.40") is True               # literal IP
    assert p.allows_host("evil.example.com") is False         # not listed
    # pre-connect verdict
    assert _egress_check("https://hooks.slack.com/services/T/B/X", p) is None
    denied = _egress_check("https://evil.example.com/x", p)
    assert denied is not None
    assert denied["result"] == "denied_by_egress_policy"
    assert "host-not-in-allow-list" in denied["error"]


def test_wildcard_is_rejected_from_allow_list():
    p = EgressAllowListPolicy.from_config(
        {"egress_policy": {"mode": "strict", "allow": ["*", "hooks.slack.com"]}}
    )
    # '*' must not survive into the allow list (would be allow-all)
    assert "*" not in p.allow
    assert "hooks.slack.com" in p.allow
    # and therefore a non-listed host is still denied
    assert _egress_check("https://evil.example.com/x", p) is not None


def test_strict_denies_rfc1918_unless_allow_private():
    cfg = {"egress_policy": {"mode": "strict",
                             "allow": ["hooks.slack.com", "10.20.30.40"]}}
    p = EgressAllowListPolicy.from_config(cfg)
    # RFC1918 literal, allow_private defaults False -> denied
    d = _egress_check("http://10.20.30.40/x", p)
    assert d is not None and d["result"] == "denied_by_egress_policy"
    assert "private-egress-denied" in d["error"]
    # with allow_private=True -> permitted
    p2 = EgressAllowListPolicy.from_config(
        {"egress_policy": {"mode": "strict",
                           "allow": ["10.20.30.40"], "allow_private": True}}
    )
    assert _egress_check("http://10.20.30.40/x", p2) is None


def test_strict_private_gate_on_resolved_rfc1918_hostname():
    cfg = {"egress_policy": {"mode": "strict", "allow": ["siem.internal"]}}
    p = EgressAllowListPolicy.from_config(cfg)
    # hostname on the allow-list but resolving to RFC1918, allow_private off
    allowed, reason = p.allows("siem.internal", resolved_ips=["10.9.8.7"])
    assert allowed is False and reason == "private-egress-denied"
    # with allow_private on, the same is allowed
    p2 = EgressAllowListPolicy.from_config(
        {"egress_policy": {"mode": "strict",
                           "allow": ["siem.internal"], "allow_private": True}}
    )
    assert p2.allows("siem.internal", resolved_ips=["10.9.8.7"])[0] is True


# ---- Criterio 3: explicit, non-silent denial via the notifier ----------------

def test_notifier_returns_explicit_denied_result_and_does_not_send():
    post = _FakePost()
    cfg = {"egress_policy": {"mode": "strict", "allow": ["hooks.slack.com"]}}
    n = SignedWebhookNotifier("https://evil.example.com/x", secret="s", http_post=post)
    n.egress = EgressAllowListPolicy.from_config(cfg)
    assert n.notify("open", INCIDENT) is False
    # nothing was actually sent
    assert post.calls == []
    # the denial is recorded explicitly (never silent)
    assert n.last_result is not None
    assert n.last_result["result"] == "denied_by_egress_policy"
    assert n.deliveries[-1]["result"] == n.last_result


def test_fanout_surfaces_denial_per_channel():
    slack = _FakePost()
    evil = _FakePost()
    cfg = {"egress_policy": {"mode": "strict", "allow": ["hooks.slack.com"]}}
    eg = EgressAllowListPolicy.from_config(cfg)
    fan = IncidentFanoutNotifier([
        SignedWebhookNotifier("https://hooks.slack.com/x", secret="s", http_post=slack, egress=eg),
        SignedWebhookNotifier("https://evil.example.com/x", secret="s", http_post=evil, egress=eg),
    ])
    ok = fan.notify("open", INCIDENT)
    # delivered == True because the slack channel succeeded; evil was denied
    assert ok is True
    assert slack.calls and evil.calls == []
    # the evil channel's denial is visible in the fan-out result
    chans = fan.last_result["results"]
    evil_res = next(c for c in chans if c["channel"] == "SignedWebhookNotifier" and not c["ok"])
    assert evil_res["last_result"]["result"] == "denied_by_egress_policy"


def test_build_incident_notifiers_wires_egress_from_config():
    post = _FakePost()
    cfg = {
        "egress_policy": {"mode": "strict", "allow": ["hooks.slack.com"]},
        "incident_webhooks": [
            {"type": "slack", "url": "https://hooks.slack.com/services/T/B/X"},
            {"type": "generic", "url": "https://evil.example.com/x", "secret": "s"},
        ],
    }
    channels = build_incident_notifiers(cfg, http_post=post)
    fan = IncidentFanoutNotifier(channels)
    fan.notify("open", INCIDENT)
    # only the slack channel reached the transport; evil was egress-denied
    urls_called = [c[0] for c in post.calls]
    assert any("hooks.slack.com" in u for u in urls_called)
    assert not any("evil.example.com" in u for u in urls_called)


def test_permissive_notifier_delivers_without_egress_check():
    post = _FakePost()
    # no egress_policy -> permissive -> legacy behaviour preserved
    n = SignedWebhookNotifier("https://evil.example.com/x", secret="s", http_post=post)
    assert n.notify("open", INCIDENT) is True
    assert len(post.calls) == 1
    assert n.last_result.get("ok") is True
