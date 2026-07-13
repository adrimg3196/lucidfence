"""LucidFence <-> Atomic Mail Agentic integration (email for the whole SaaS).

Atomic Mail gives every LucidFence tenant/agent a real programmable inbox over
JMAP (RFC 8620/8621) with a proof-of-work (scrypt) signup -- no SMTP server,
no API keys to buy, no CAPTCHA. This module is the single facade LucidFence
uses for ALL outbound email of the SaaS:

  * incident lifecycle alerts (geofence exit, compliance, risk)
  * threshold alerts (alerts.py channel "atomicmail")
  * daily/weekly risk + fleet digest
  * support mailbox auto-replies and triage
  * any future "email the human" surface

The underlying client (core/atomicmail/*) is the MIT-licensed Atomic Mail
Python SDK, vendored read-only. This file never edits that code; it only calls
its public API (register / login_with_api_key / get_capability_token /
get_primary_mail_account_id / get_jmap_post_url) and issues the JMAP
Email/set + EmailSubmission/set calls following the upstream docs exactly.

Security model (matches LucidFence CISO baseline):
  * credentials per tenant under data/tenants/<org>/atomicmail/ (mode 0600)
  * apiKey is a secret: never logged, never returned in any API response
  * never raises to the caller: a failed send is recorded and returns False so
    the engine/alert cycle can never 500 because email is down
  * inbound mail is untrusted: this module only SENDS; reading is opt-in and
    sandboxed in the support inbox helper

Requires: Python stdlib only (the vendored SDK uses urllib, not requests).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

# The vendored Atomic Mail SDK lives under core/atomicmail. Its shared assets
# (consts.json etc.) are vendored under core/atomicmail/vendor_shared and must
# be pointed at via ATOMIC_MAIL_SHARED_DIR before importing the SDK.
_HERE = Path(__file__).resolve().parent
_SHARED_DIR = str(_HERE / "atomicmail" / "vendor_shared")
os.environ.setdefault("ATOMIC_MAIL_SHARED_DIR", _SHARED_DIR)

from core.atomicmail.session import create_agent_session  # noqa: E402
from core.atomicmail.credentials import (  # noqa: E402
    Credentials,
    write_credentials,
    read_credentials,
    try_read_credentials,
    FilesystemCredentialStore,
)

DEFAULT_AUTH_URL = "https://auth.atomicmail.ai"
DEFAULT_API_URL = "https://api.atomicmail.ai"
DEFAULT_SCRYPT_SALT_HEX = (
    "0b980734412c292d6549110276b604ab1dea4883bd460d77d1b984adf8bca083"
)

JMAP_MAIL_URN = "urn:ietf:params:jmap:mail"
JMAP_SUBMISSION_URN = "urn:ietf:params:jmap:submission"


class AtomicMailError(RuntimeError):
    """Raised only internally; public methods swallow it and return False."""


def _cred_dir_for(tenant_dir: str | Path) -> str:
    d = Path(tenant_dir) / "atomicmail"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


class TenantMailbox:
    """One Atomic Mail inbox bound to one LucidFence tenant/org.

    Usage:
        mb = TenantMailbox(tenant_dir="/path/to/data/tenants/<org>")
        ok = mb.ensure_registered(username="acme-fence")
        ok = mb.send(to="soc@acme.com", subject="...", text="...")
    """

    def __init__(self, tenant_dir: str | Path, username: str | None = None,
                 api_key: str | None = None, inbox_domain: str | None = None):
        self.tenant_dir = str(tenant_dir)
        self.cred_dir = _cred_dir_for(tenant_dir)
        self.username = username
        self.api_key = api_key
        self.inbox_domain = inbox_domain or "atomicmail.ai"
        self._session = None
        self.last_error: Optional[str] = None
        # in-memory credential cache (avoids re-reading disk each send)
        self._api_key: Optional[str] = api_key
        self._inbox_id: Optional[str] = None

    # ---- registration / login -------------------------------------------
    def ensure_registered(self, *, forced: bool = False) -> bool:
        """Register a fresh inbox (or recover from saved credentials).

        Returns True if the mailbox is ready to send. Never raises.
        """
        try:
            # If an api_key was supplied (e.g. recovered from secret store),
            # log in with it; otherwise register a new PoW account.
            if self._api_key:
                session = create_agent_session(
                    credentials_dir=self.cred_dir,
                    provider_api_key=self._api_key,
                )
                res = session.login_with_api_key(self._api_key)
            else:
                session = create_agent_session(credentials_dir=self.cred_dir)
                if not self.username:
                    raise AtomicMailError("username requerido para registro")
                res = session.register(self.username, forced=forced)
            self._session = session
            self._api_key = res.apiKey or self._api_key
            self._inbox_id = res.inbox
            self.last_error = None
            return True
        except Exception as exc:  # noqa: BLE001 - never propagate
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    # ---- send ------------------------------------------------------------
    def send(self, *, to: str, subject: str, text: str,
             html: Optional[str] = None) -> bool:
        """Send one email via JMAP. Returns True if accepted by the server."""
        if self._session is None:
            if not self.ensure_registered():
                return False
        try:
            session = self._session
            if session is None:
                return False
            cap = session.get_capability_token()
            account_id = session.get_primary_mail_account_id()
            jmap_url = session.get_jmap_post_url()
            domain = self.inbox_domain or "atomicmail.ai"
            if self._inbox_id and "@" in self._inbox_id:
                sender = self._inbox_id
            else:
                local = self._inbox_id or self.username or "lucidfence"
                sender = f"{local}@{domain}"

            sender = (
                self._inbox_id
                if self._inbox_id and "@" in self._inbox_id
                else f"{(self._inbox_id or self.username or 'lucidfence')}@{domain}"
            )

            # Resolve the real inbox mailbox id (JMAP requires a valid mailbox
            # id in Email/set, even though we deliver via EmailSubmission/set).
            inbox_mailbox_id = self._inbox_mailbox_id(session, account_id, jmap_url, cap)
            if not inbox_mailbox_id:
                inbox_mailbox_id = account_id  # last-resort fallback

            text_body = [{"partId": "body", "type": "text/plain"}]
            body_values = {"body": {"value": text}}
            if html:
                text_body.append({"partId": "html", "type": "text/html"})
                body_values["html"] = {"value": html, "charset": "utf-8"}

            create = {
                "draft1": {
                    "mailboxIds": {inbox_mailbox_id: True},
                    "from": [{"email": sender}],
                    "to": [{"email": to}],
                    "subject": subject,
                    "textBody": text_body,
                    "bodyValues": body_values,
                    "keywords": {"$draft": True},
                }
            }
            method_calls = [
                ["Email/set", {"accountId": account_id, "create": create}, "s0"],
                ["EmailSubmission/set", {
                    "accountId": account_id,
                    "create": {
                        "sub1": {
                            "emailId": "#draft1",
                            "envelope": {
                                "mailFrom": {"email": sender},
                                "rcptTo": [{"email": to}],
                            },
                        }
                    },
                }, "s1"],
            ]
            envelope = {
                "using": [JMAP_MAIL_URN, JMAP_SUBMISSION_URN],
                "methodCalls": method_calls,
            }
            import urllib.request
            from urllib.error import HTTPError
            req = urllib.request.Request(
                jmap_url,
                data=json.dumps(envelope).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {cap}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    status = r.getcode()
                    body_text = r.read().decode("utf-8", errors="replace")
            except HTTPError as err:
                status = err.code
                body_text = err.read().decode("utf-8", errors="replace")
            if not (200 <= status < 300):
                self.last_error = f"JMAP HTTP {status}: {body_text[:300]}"
                return False
            # Best-effort: detect a method-level error in the response.
            try:
                parsed = json.loads(body_text)
                for name, payload, _cid in parsed.get("methodResponses", []):
                    if name.endswith("/set") and isinstance(payload, dict):
                        if payload.get("notCreated") or payload.get("notSet"):
                            self.last_error = f"JMAP {name} rechazado: {payload}"
                            return False
            except Exception:
                pass
            self.last_error = None
            return True
        except Exception as exc:  # noqa: BLE001 - never propagate
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def _inbox_mailbox_id(self, session, account_id, jmap_url, cap) -> Optional[str]:
        """Resolve the inbox mailbox id via Mailbox/query (JMAP requires a real id)."""
        try:
            import urllib.request
            from urllib.error import HTTPError
            envelope = {
                "using": [JMAP_MAIL_URN],
                "methodCalls": [
                    ["Mailbox/query", {"accountId": account_id, "filter": {"role": "inbox"}}, "mq0"]
                ],
            }
            req = urllib.request.Request(
                jmap_url,
                data=json.dumps(envelope).encode("utf-8"),
                headers={"Authorization": f"Bearer {cap}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                text = r.read().decode("utf-8", errors="replace")
            parsed = json.loads(text)
            for name, payload, _cid in parsed.get("methodResponses", []):
                if name == "Mailbox/query" and isinstance(payload, dict):
                    ids = payload.get("ids")
                    if isinstance(ids, list) and ids and isinstance(ids[0], str):
                        return ids[0]
        except Exception:
            return None
        return None

    # ---- status ----------------------------------------------------------
    def status(self) -> dict:
        return {
            "ready": self._session is not None and bool(self._inbox_id),
            "inbox": self._inbox_id,
            "last_error": self.last_error,
        }

    def persist_api_key(self) -> Optional[str]:
        """Return the apiKey so the caller can store it in the secret store.

        The apiKey is the long-lived credential; never expose it in logs/API.
        """
        if self._api_key:
            return self._api_key
        creds = try_read_credentials(Path(self.cred_dir) / "credentials.json")
        if creds:
            self._api_key = creds.apiKey
        return self._api_key


def build_tenant_mailbox(tenant_dir: str | Path, *,
                         username: str | None = None,
                         api_key: str | None = None,
                         inbox_domain: str | None = None) -> TenantMailbox:
    """Factory used by the SaaS layer. Credentials are stored per tenant."""
    return TenantMailbox(tenant_dir, username=username, api_key=api_key,
                         inbox_domain=inbox_domain)
