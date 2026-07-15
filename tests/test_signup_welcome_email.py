"""Regression: signup welcome email via Atomic Mail stays local/on-prem.

No network: Atomic Mail is monkeypatched with a fake mailbox. The test validates
copy, delivery wiring and test-domain skip behaviour.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import saas_server  # noqa: E402
import core.atomicmail_client as atomicmail_client  # noqa: E402


class FakeTenantStore:
    def __init__(self, root: Path):
        self.root = root

    def data_dir(self, org_id: str) -> Path:
        path = self.root / org_id / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path


class FakeMailbox:
    sent = []

    def __init__(self, tenant_dir, username=None, api_key=None, inbox_domain=None):
        self.tenant_dir = tenant_dir
        self.username = username
        self.api_key = api_key
        self.inbox_domain = inbox_domain
        self.last_error = None
        self._inbox = f"{username}@{inbox_domain or 'atomicmail.ai'}"

    def send(self, *, to, subject, text, html=None):
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return True

    def status(self):
        return {"ready": True, "inbox": self._inbox, "last_error": self.last_error}

    def persist_api_key(self):
        return "ak_fake_signup_welcome"


def test_signup_welcome_email_delivers_three_activation_steps():
    org = SimpleNamespace(id="org_abcdef1234", slug="acme-logistics", name="Acme Logistics")
    saved = {}
    FakeMailbox.sent = []
    old_tenants = saas_server._tenants
    old_builder = atomicmail_client.build_tenant_mailbox
    old_save = saas_server._save_tenant_integration
    with tempfile.TemporaryDirectory() as td:
        try:
            saas_server._tenants = FakeTenantStore(Path(td))
            atomicmail_client.build_tenant_mailbox = lambda *a, **kw: FakeMailbox(*a, **kw)
            saas_server._save_tenant_integration = lambda *a, **kw: saved.update({"args": a, "kwargs": kw})
            result = saas_server._send_signup_welcome_email("owner@acme.com", "Ana", org)
        finally:
            saas_server._tenants = old_tenants
            atomicmail_client.build_tenant_mailbox = old_builder
            saas_server._save_tenant_integration = old_save

    assert result["attempted"] is True
    assert result["sent"] is True
    assert result["inbox"].endswith("@atomicmail.ai")
    assert len(FakeMailbox.sent) == 1
    message = FakeMailbox.sent[0]
    assert message["to"] == "owner@acme.com"
    assert "Bienvenido" in message["subject"]
    assert "brew install adrimg3196/lucidfence/lucidfence" in message["text"]
    assert "lucidfence serve" in message["text"]
    assert "Geocercas" in message["text"]
    assert "Incidencias" in message["text"]
    assert "no tienes que registrar nada en una nube de LucidFence" in message["text"]
    assert saved["kwargs"]["atomicmail"]["api_key"] == "ak_fake_signup_welcome"
    assert saved["kwargs"]["atomicmail"]["digest_email_to"] == "owner@acme.com"


def test_signup_welcome_email_skips_test_domains():
    org = SimpleNamespace(id="org_test", slug="test", name="Test")
    FakeMailbox.sent = []
    old_tenants = saas_server._tenants
    with tempfile.TemporaryDirectory() as td:
        try:
            saas_server._tenants = FakeTenantStore(Path(td))
            result = saas_server._send_signup_welcome_email("owner@acme.test", "Ana", org)
        finally:
            saas_server._tenants = old_tenants

    assert result == {"attempted": False, "sent": False, "reason": "destinatario_test"}
    assert FakeMailbox.sent == []


def test_atomicmail_username_for_org_respects_atomicmail_limits():
    org = SimpleNamespace(id="org_1234567890", slug="Very Long Client Name !!!", name="Client")
    username = saas_server._atomicmail_username_for_org(org)

    assert 5 <= len(username) <= 21
    assert username.startswith("lf")
    assert username.isalnum()
