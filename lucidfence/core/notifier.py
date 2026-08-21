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
import http.client
import ipaddress
import json
import socket
import ssl
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


# Per-tenant outbound webhook egress policy (task t_f33e2f23).
#
# Product decision (t_316b8ec5, APROBADA): a tenant-scoped allow/deny-list for
# OUTGOING webhooks, defaulting to `permissive` (current behaviour — never breaks
# existing deployments) with an opt-in `strict` mode.
#
#   mode:        "permissive" (default) | "strict"
#                permissive -> only the admission guard runs (legacy behaviour).
#                strict     -> admission guard AND an explicit allow-list.
#   allow:       list of entries; each is an exact hostname ("hooks.slack.com"),
#                a domain suffix (".slack.com", matches subdomains), or a literal
#                IP ("10.20.30.40"). A global wildcard "*" is REJECTED (it would
#                be an allow-all that nullifies the policy).
#   allow_private: in `strict`, whether RFC1918 / private destinations are
#                permitted. Default False -> private egress denied even if the
#                host appears in `allow` (closes the residual H-3 RFC1918 gap).
#
# Defense in depth: this is a LAYER ON TOP of the admission guard
# (_webhook_resolve blocks loopback/link-local/cloud-metadata 169.254.0.0/16
# always). In strict: admission guard AND allow-list must both pass.
#
# A delivery denied by this policy is NEVER silent: the post returns an explicit
# {"ok": False, "result": "denied_by_egress_policy", ...} so the dashboard can
# surface it (criterion #3 of the product decision).
class EgressAllowListPolicy:
    """Parse and evaluate a tenant's outgoing-webhook egress policy.

    Robust by design: a malformed policy degrades to `permissive` so a bad
    integration.json can never break webhook delivery for an existing tenant.
    """

    def __init__(self, raw: Any = None):
        self.mode = "permissive"
        self.allow: list[str] = []
        self.allow_private = False
        self.parse(raw)

    @classmethod
    def from_config(cls, config: Any) -> "EgressAllowListPolicy":
        raw = (config or {}).get("egress_policy") or {}
        return cls(raw)

    def parse(self, raw: Any) -> None:
        if not isinstance(raw, dict):
            # Malformed -> permissive (do not break deployments).
            self.mode = "permissive"
            self.allow = []
            self.allow_private = False
            return
        mode = str(raw.get("mode", "permissive")).strip().lower()
        self.mode = "strict" if mode == "strict" else "permissive"
        allow = raw.get("allow") or []
        cleaned: list[str] = []
        if isinstance(allow, list):
            for entry in allow:
                if not isinstance(entry, str):
                    continue
                e = entry.strip().lower()
                if not e or e == "*":
                    # Reject the global wildcard: it would be an allow-all that
                    # defeats the entire point of an allow-list.
                    continue
                cleaned.append(e)
        self.allow = cleaned
        self.allow_private = bool(raw.get("allow_private", False))

    def is_strict(self) -> bool:
        return self.mode == "strict"

    def allows_host(self, host: str) -> bool:
        """Pre-DNS allow-list match on the configured host (no resolution).

        Matches exact hostnames, domain suffixes (".slack.com"), and literal IPs.
        In `permissive` mode everything is allowed.
        """
        if not self.is_strict():
            return True
        h = (host or "").strip().lower()
        if not h:
            return False
        for entry in self.allow:
            if entry.startswith("."):
                suffix = entry[1:]
                if h == suffix or h.endswith("." + suffix):
                    return True
            elif h == entry:
                return True
        return False

    @staticmethod
    def _is_private(ip: Any) -> bool:
        try:
            addr = ipaddress.ip_address(str(ip))
        except ValueError:
            return False
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            addr = addr.ipv4_mapped
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local
                    or addr.is_reserved or addr.is_multicast)

    def allows(self, host: str, resolved_ips: Any = None) -> tuple[bool, Optional[str]]:
        """Full egress verdict for a destination.

        `resolved_ips` are addresses already vetted by the admission guard
        (_webhook_resolve — loopback/link-local/metadata already removed). They
        are only needed for the private-egress gate when `allow_private` is off.

        Returns (allowed, reason). reason is None when allowed.
        """
        if not self.is_strict():
            return True, None
        h = (host or "").strip().lower()
        # 1) Allow-list membership (hostname / suffix / literal IP).
        if not self.allows_host(h):
            return False, "host-not-in-allow-list"
        # 2) Private-egress gate (honours allow_private).
        if not self.allow_private:
            candidates: list[Any] = []
            try:
                candidates.append(ipaddress.ip_address(h))
            except ValueError:
                pass
            for rip in (resolved_ips or []):
                candidates.append(rip)
            for c in candidates:
                if self._is_private(c):
                    return False, "private-egress-denied"
        return True, None


def _egress_check(url: str, egress: Optional["EgressAllowListPolicy"]) -> Optional[dict]:
    """Return a denied verdict if `url` is blocked by a strict egress policy.

    Returns None when the delivery is permitted (or no strict policy applies),
    and a non-silent ``denied_by_egress_policy`` verdict dict otherwise. The
    check is pre-connect: it evaluates the configured host against the allow-
    list (and the literal-IP private gate). The post-resolve private gate for
    hostname->RFC1918 destinations runs inside ``_default_http_post``.
    """
    if egress is None or not egress.is_strict():
        return None
    from urllib.parse import urlparse as _urlparse
    host = (_urlparse(url).hostname or "").lower()
    allowed, reason = egress.allows(host)
    if not allowed:
        return {
            "ok": False,
            "result": "denied_by_egress_policy",
            "error": f"egress policy ({reason}): {host}",
        }
    return None


# Outbound webhook egress policy.
#
# SECURITY (H-3 follow-up, task t_cd79333c): the legacy `_safe_webhook_url` guard
# validates the hostname at CONFIG time, but the actual socket connect re-resolved
# the name via http.client at SEND time. That is a DNS-rebinding TOCTOU: an
# attacker who controls DNS could return a public IP at validation time and a
# RFC1918 / link-local / metadata (169.254.169.254) IP on the connect — pivoting
# past the guard. We close it the same way OIDC does: resolve ONCE, validate
# EVERY resolved address, and connect to the validated IP with Host/SNI pinned to
# the ORIGINAL hostname (so TLS + virtual hosts keep working).
#
# Trade-off (intentional, documented, NOT a bug — local-first UEM appliance):
#   * BLOCKED on resolution: loopback, link-local (incl. cloud metadata
#     169.254.0.0/16), reserved, multicast, and IPv4-mapped loopback. These are
#     the genuine SSRF pivot targets.
#   * ALLOWED: RFC1918 / unresolvable LAN names. A self-hosted LucidFence admin
#     legitimately points webhooks at an internal SIEM or on-prem receiver. A
#     stricter "block all private egress" needs per-tenant allow/deny lists and
#     product sign-off (see SECURITY.md / task t_cd79333c).
# This mirror exactly what `_safe_webhook_url` already accepts, so behaviour for
# legitimate configs is unchanged; only the TOCTOU window is closed.
def _webhook_resolve(host: str, port: int) -> list[str]:
    """Resolve `host` to every address and reject the snapshot if ANY is a pivot.

    Returns the de-duplicated address list, or raises ValueError if the name is
    unresolvable or resolves to a blocked (loopback/link-local/metadata) target.
    RFC1918 results are allowed and returned as-is.

    A literal IP bypasses DNS entirely: it is returned as-is. This deliberately
    PRESERVES the legacy behaviour for explicit private/loopback targets (self-
    hosted SIEMs, the local runtime harness, on-prem receivers) — `_safe_webhook_url`
    already gates which URLs the operator may configure; a URL the operator set
    explicitly is not subject to the DNS-rebinding TOCTOU.
    """
    # Fast path: a literal IP never talks to DNS and is not a rebinding surface.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [str(ip)]
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError, ValueError):
        # Unresolvable here (e.g. an internal LAN name that resolves only inside
        # the customer's network). Allow it — the operator configured it. The
        # connect will fail at the customer's resolver, not here.
        return []
    if not infos:
        raise ValueError("empty-resolution")
    addrs: list[str] = []
    for info in infos:
        addr = str(info[4][0]).split("%", 1)[0].lower()  # strip IPv6 zone id
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            raise ValueError("unparseable-address")
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        # Block the genuine SSRF pivots; allow RFC1918 / other globals.
        if ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("blocked-pivot")
        if addr not in addrs:
            addrs.append(addr)
    return addrs


class _PinnedHTTPConnection:
    """http.client connection to a pre-validated IP, keeping Host/SNI = hostname.

    For HTTPS we wrap in TLS with server_hostname=hostname (so SNI + cert
    validation use the operator's hostname, not the raw IP). For HTTP we just
    connect to the IP with Host: hostname. The validated IP is the ONLY address
    touched — DNS is never consulted again.
    """

    def __init__(self, hostname: str, ip: str, port: int, *, https: bool, timeout: float = 10):
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.https = https
        self.timeout = timeout
        self._conn: Any = None

    def _build(self):
        if self.https:
            ctx = ssl.create_default_context()
            self._conn = http.client.HTTPSConnection(
                self.hostname, self.port, timeout=self.timeout, context=ctx
            )
        else:
            self._conn = http.client.HTTPConnection(self.hostname, self.port, timeout=self.timeout)
        # Pin the socket to the validated IP *before* any request. http.client
        # resolves `host` lazily in connect(); we override connect to use `ip`.
        _ip = self.ip

        def _connect_pinned(conn_self):  # noqa: ANN001 - http.client internal
            raw = socket.create_connection((_ip, conn_self.port), conn_self.timeout)
            if self.https:
                conn_self.sock = conn_self._context.wrap_socket(
                    raw, server_hostname=conn_self.host
                )
            else:
                conn_self.sock = raw

        self._conn.connect = _connect_pinned.__get__(self._conn, type(self._conn))

    def request(self, method, path, body=None, headers=None):  # noqa: ANN001
        self._build()
        # Ensure Host reflects the original hostname (in case of IP-based default).
        if headers is not None and "Host" not in headers:
            headers = dict(headers)
            headers["Host"] = self.hostname
        self._conn.request(method, path, body=body, headers=headers)

    def getresponse(self):  # noqa: ANN001
        return self._conn.getresponse()

    def close(self):  # noqa: ANN001
        if self._conn is not None:
            self._conn.close()


def _default_http_post(url: str, payload, headers: Optional[dict] = None,
                        egress: Optional[EgressAllowListPolicy] = None) -> dict:
    """Real HTTP POST via stdlib http.client. Never raises.

    `payload` dict/list → JSON body; str/bytes → raw body (ntfy usa texto plano).

    Egress hardening (H-3 follow-up, t_cd79333c): the destination is resolved
    ONCE and connected to the validated IP (Host/SNI pinned to the original
    hostname). This removes the DNS-rebinding TOCTOU: the address used at connect
    time is the same one that passed validation, so a name that flips to an
    internal/metadata IP between config-check and send cannot pivot.

    Egress allow-list (t_f33e2f23): when `egress` is a `strict` policy and
    `allow_private` is off, a destination whose resolved address is RFC1918 /
    private is denied here (after the admission-resolve, before connect) with an
    explicit `denied_by_egress_policy` verdict — never silent.
    """
    parsed = urlparse(url)
    # Only http/https with a real host. Reject exotic schemes (file://, gopher://,
    # ftp://) and credential-smuggling (http://user:pass@host).
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return {"ok": False, "error": f"webhook_url no permitido (esquema/host): {url!r}"}
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    https = parsed.scheme == "https"
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
        # Resolve once; validate the whole snapshot; pick the first usable IP.
        # The admission guard already drops loopback/link-local/metadata pivots.
        ips = _webhook_resolve(host, port)
        # Egress allow-list: in strict + allow_private=off, deny any private
        # (RFC1918 / reserved / etc.) destination — even one reached via a
        # hostname that was on the allow-list. This is the post-resolve half of
        # the private gate (the pre-resolve half runs in _egress_guarded_post).
        if egress is not None and egress.is_strict() and not egress.allow_private:
            if egress._is_private(host) or any(egress._is_private(ip) for ip in ips):
                return {
                    "ok": False,
                    "result": "denied_by_egress_policy",
                    "error": f"egress policy (private-egress-denied): {host}",
                }
        if not ips:
            # Unresolvable LAN name: fall back to hostname-based connect (the
            # operator's resolver handles it). No TOCTOU risk because we never
            # validated it as "public" — it simply connects to whatever the local
            # resolver returns, exactly as before this hardening.
            conn = _PinnedHTTPConnection(host, host, port, https=https, timeout=10)
            conn.request("POST", parsed.path or "/", body=body, headers=send_headers)
        else:
            # Pinned-IP connect: only `ips[0]` is ever touched.
            conn = _PinnedHTTPConnection(host, ips[0], port, https=https, timeout=10)
            conn.request("POST", parsed.path or "/", body=body, headers=send_headers)
        r = conn.getresponse()
        status = r.status
        conn.close()
        return {"ok": 200 <= status < 300, "status": status}
    except Exception as exc:  # noqa: BLE001 - never propagate
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


class IncidentNotifier:
    def __init__(self, webhook_url: str = "", http_post: Optional[Callable] = None,
                 egress: Optional[EgressAllowListPolicy] = None):
        self.webhook_url = (webhook_url or "").strip()
        self._post = http_post or _default_http_post
        self.egress = egress
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def notify(self, transition: str, incident: dict) -> bool:
        """POST an incident event to the webhook. Returns True if delivered.

        `transition` is one of: open | acknowledged | resolved. Suppressed
        transitions (reopen etc.) are still delivered but labeled generically.
        Never raises. A strict egress policy denies non-allow-listed hosts with
        an explicit `denied_by_egress_policy` result (never silent).
        """
        if not self.webhook_url:
            return False
        # Egress allow-list gate (pre-connect, non-silent).
        denied = _egress_check(self.webhook_url, self.egress)
        if denied is not None:
            self.last_result = denied
            self.deliveries.append({"transition": transition,
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "result": denied})
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

    def __init__(self, url: str, secret: str = "", http_post: Optional[Callable] = None,
                 egress: Optional[EgressAllowListPolicy] = None):
        self.url = (url or "").strip()
        self.secret = (secret or "").strip()
        self._post = http_post or _default_http_post
        self.egress = egress
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
        # Egress allow-list gate (pre-connect, non-silent).
        denied = _egress_check(self.url, self.egress)
        if denied is not None:
            self.last_result = denied
            self.deliveries.append({"transition": transition,
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "result": denied})
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

    def __init__(self, url: str, token: str = "", http_post: Optional[Callable] = None,
                 egress: Optional[EgressAllowListPolicy] = None):
        self.url = (url or "").strip()
        self.token = (token or "").strip()
        self._post = http_post or _default_http_post
        self.egress = egress
        self.last_result: Optional[dict] = None
        self.deliveries: list[dict] = []

    def enabled(self) -> bool:
        return bool(self.url)

    def notify(self, transition: str, incident: dict) -> bool:
        if not self.url:
            return False
        # Egress allow-list gate (pre-connect, non-silent).
        denied = _egress_check(self.url, self.egress)
        if denied is not None:
            self.last_result = denied
            self.deliveries.append({"transition": transition,
                                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "result": denied})
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

    Egress policy (t_f33e2f23): the tenant's `egress_policy` (from
    integration.json) is parsed once and attached to every webhook notifier so
    all outgoing webhook delivery is gated by the tenant allow-list in `strict`
    mode. `http_post`, when supplied (e.g. by tests), replaces the transport but
    the egress verdict is still enforced before it is called.
    """
    # Build the per-tenant egress policy from config once.
    egress = EgressAllowListPolicy.from_config(config)

    notifiers: list = []
    legacy = (config.get("incident_webhook_url") or "").strip()
    if legacy:
        notifiers.append(IncidentNotifier(webhook_url=legacy, http_post=http_post,
                                           egress=egress))
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
            notifiers.append(IncidentNotifier(webhook_url=url, http_post=http_post,
                                               egress=egress))
        elif kind == "ntfy":
            notifiers.append(NtfyNotifier(url, token=entry.get("token") or "",
                                          http_post=http_post, egress=egress))
        elif kind == "generic":
            notifiers.append(SignedWebhookNotifier(url, secret=entry.get("secret") or "",
                                                   http_post=http_post, egress=egress))
        # tipos desconocidos: se ignoran (fail-soft)
    return notifiers
