"""Hardened OIDC Authorization Code + PKCE primitives.

The module deliberately keeps HTTP and persistence injectable so production uses
pinned-IP TLS while tests use a cryptographic fake IdP. Provider tokens are
validated and discarded; only ``(issuer, sub)`` is durable identity.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit

try:
    import jwt
except ImportError:  # OIDC is optional for password/local-only deployments.
    jwt = None  # type: ignore[assignment]


MAX_FLOW_TTL = 600
ALLOWED_RETURN_PATHS = frozenset({"/app", "/dashboard", "/settings"})
ASYMMETRIC_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")


def oidc_dependencies_available() -> bool:
    return jwt is not None


class OIDCError(ValueError):
    """A stable, non-secret error safe to map to an API response."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _b64_random(size: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(size)).rstrip(b"=").decode("ascii")


def validate_return_path(value: str) -> str:
    if value not in ALLOWED_RETURN_PATHS:
        raise OIDCError("invalid_return_path")
    return value


def validate_callback_params(query: str, *, max_length: int = 8192) -> dict[str, str]:
    if len(query.encode("utf-8", "ignore")) > max_length:
        raise OIDCError("invalid_callback")
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=8)
    except (ValueError, UnicodeError):
        raise OIDCError("invalid_callback") from None
    allowed = {"state", "code", "error", "iss"}
    result: dict[str, str] = {}
    for key, value in pairs:
        if key not in allowed or key in result or not value:
            raise OIDCError("invalid_callback")
        result[key] = value
    if "state" not in result or (("code" in result) == ("error" in result)):
        raise OIDCError("invalid_callback")
    return result


def _validate_loopback_redirect(uri: str, provider_name: str) -> None:
    try:
        parsed = urlsplit(uri)
        host = parsed.hostname
        ip = ipaddress.ip_address(host or "")
    except ValueError:
        raise OIDCError("invalid_redirect_uri") from None
    if parsed.scheme != "http" or ip not in (ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")):
        raise OIDCError("invalid_redirect_uri")
    expected_path = f"/api/auth/sso/{provider_name}/callback"
    if (parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.port is None or parsed.path != expected_path):
        raise OIDCError("invalid_redirect_uri")


@dataclass
class OIDCProvider:
    name: str
    label: str
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    jwks_uri: str = ""
    userinfo_endpoint: str = ""
    discovery_url: str = ""
    enabled: bool = False
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)
    provision_org_id: str = ""
    provision_role: str = "viewer"
    token_auth_method: str = "client_secret_basic"
    allow_client_secret_post: bool = False
    local_public_client: bool = False
    authorization_response_iss_parameter_supported: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", self.name):
            raise OIDCError("invalid_provider")
        if self.local_public_client:
            _validate_loopback_redirect(self.redirect_uri, self.name)
            if self.client_secret or self.token_auth_method != "none":
                raise OIDCError("invalid_client_auth")
        elif self.redirect_uri:
            p = urlsplit(self.redirect_uri)
            if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment:
                raise OIDCError("invalid_redirect_uri")
        if self.token_auth_method not in {"client_secret_basic", "client_secret_post", "none"}:
            raise OIDCError("invalid_client_auth")
        if self.token_auth_method == "client_secret_post" and not self.allow_client_secret_post:
            raise OIDCError("invalid_client_auth")
        if self.token_auth_method == "none" and not self.local_public_client:
            raise OIDCError("invalid_client_auth")
        self.allowed_domains = tuple(d.strip().lower().rstrip(".") for d in self.allowed_domains if d.strip())

    @classmethod
    def google(cls, *, client_id: str, client_secret: str, redirect_uri: str,
               allowed_domains: tuple[str, ...] = (), provision_org_id: str = "") -> "OIDCProvider":
        enabled = bool(client_id and client_secret and redirect_uri)
        return cls(name="google", label="Google", issuer="https://accounts.google.com",
                   client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri,
                   authorization_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
                   token_endpoint="https://oauth2.googleapis.com/token",
                   jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
                   userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
                   discovery_url="https://accounts.google.com/.well-known/openid-configuration",
                   enabled=enabled, allowed_domains=allowed_domains, provision_org_id=provision_org_id,
                   authorization_response_iss_parameter_supported=False)

    def public_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "enabled": bool(self.enabled)}


class PublicEgressPolicy:
    """Resolve a fresh complete DNS snapshot and reject it unless every IP is public."""

    def __init__(self, resolver: Callable[[str, int], list[str] | tuple[str, ...]] | None = None):
        self._resolver = resolver or self._system_resolve

    @staticmethod
    def _system_resolve(host: str, port: int) -> list[str]:
        return sorted({row[4][0] for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})

    @staticmethod
    def _public(address: str) -> bool:
        try:
            ip = ipaddress.ip_address(address)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            return bool(ip.is_global and not ip.is_multicast and not ip.is_unspecified)
        except ValueError:
            return False

    def resolve_public(self, host: str, port: int) -> tuple[str, ...]:
        try:
            addresses = tuple(dict.fromkeys(self._resolver(host, port)))
        except Exception:
            raise OIDCError("unsafe_endpoint") from None
        if not addresses or any(not self._public(address) for address in addresses):
            raise OIDCError("unsafe_endpoint")
        return addresses


class OIDCMetadataValidator:
    def __init__(self, egress_policy: PublicEgressPolicy, allowed_ports: tuple[int, ...] = (443,)):
        self.egress_policy = egress_policy
        self.allowed_ports = allowed_ports

    def validate_endpoint(self, url: str, *, issuer: bool = False) -> str:
        if not isinstance(url, str) or "\\" in url or any(ord(ch) < 0x20 for ch in url):
            raise OIDCError("unsafe_endpoint")
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            port = parsed.port or 443
        except ValueError:
            raise OIDCError("unsafe_endpoint") from None
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise OIDCError("unsafe_endpoint")
        if port not in self.allowed_ports or "%" in host:
            raise OIDCError("unsafe_endpoint")
        # Reject alternative numeric IPv4 forms before DNS can normalize them.
        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9.]+)", host, re.I):
            try:
                ip = ipaddress.ip_address(host)
            except ValueError:
                raise OIDCError("unsafe_endpoint") from None
            if str(ip) != host:
                raise OIDCError("unsafe_endpoint")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", host, re.I):
                raise OIDCError("unsafe_endpoint") from None
            self.egress_policy.resolve_public(host, port)
        else:
            if not self.egress_policy._public(str(literal)):
                raise OIDCError("unsafe_endpoint")
        return url

    def validate_metadata(self, configured_issuer: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_endpoint(configured_issuer, issuer=True)
        if metadata.get("issuer") != configured_issuer:
            raise OIDCError("issuer_mismatch")
        out = dict(metadata)
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            if not isinstance(out.get(name), str):
                raise OIDCError("invalid_metadata")
            self.validate_endpoint(out[name])
        if out.get("userinfo_endpoint"):
            self.validate_endpoint(out["userinfo_endpoint"])
        return out


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS connection to one validated IP, retaining hostname for SNI/cert/Host."""

    def __init__(self, hostname: str, ip: str, port: int, timeout: float):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = ip

    def connect(self) -> None:
        raw = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        peer = self.sock.getpeername()[0]
        if ipaddress.ip_address(peer) != ipaddress.ip_address(self._pinned_ip):
            self.close()
            raise OIDCError("unsafe_endpoint")


class PinnedHTTPSTransport:
    def __init__(self, policy: PublicEgressPolicy | None = None):
        self.policy = policy or PublicEgressPolicy()
        self.validator = OIDCMetadataValidator(self.policy)

    def json_request(self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
                     form: Mapping[str, str] | None = None, max_bytes: int = 65536,
                     timeout: float = 5) -> dict[str, Any]:
        self.validator.validate_endpoint(url)
        parsed = urlsplit(url)
        host, port = parsed.hostname or "", parsed.port or 443
        ips = self.policy.resolve_public(host, port)  # fresh on every request/retry
        body = None
        req_headers = {"Accept": "application/json", "Host": host}
        req_headers.update(headers or {})
        if form is not None:
            body = urlencode(form).encode("ascii")
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        conn = _PinnedHTTPSConnection(host, ips[0], port, timeout)
        try:
            conn.request(method, parsed.path or "/", body=body, headers=req_headers)
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise OIDCError("redirect_forbidden")
            if response.status < 200 or response.status >= 300:
                raise OIDCError("provider_failure")
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise OIDCError("provider_response_too_large")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise OIDCError("provider_failure")
            return value
        except OIDCError:
            raise
        except Exception:
            raise OIDCError("provider_failure") from None
        finally:
            conn.close()


class OIDCFlowStore:
    """Capacity-bounded, atomic JSON flow store; explicitly single-process."""

    def __init__(self, path: Path, *, ttl_seconds: int = 300, capacity: int = 1024,
                 clock: Callable[[], float] = time.time, lock: threading.RLock | None = None):
        if ttl_seconds <= 0 or ttl_seconds > MAX_FLOW_TTL:
            raise ValueError("ttl_seconds must be within 1..600")
        self.path, self.ttl_seconds, self.capacity = Path(path), ttl_seconds, capacity
        self._clock, self._lock = clock, lock or threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save({})

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, separators=(",", ":"))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp_name, self.path); os.chmod(self.path, 0o600)
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        finally:
            try: os.unlink(tmp_name)
            except FileNotFoundError: pass

    def _purge(self, flows: dict[str, dict[str, Any]], now: float) -> None:
        for state in [s for s, f in flows.items() if float(f.get("expires_at", 0)) <= now]:
            flows.pop(state, None)

    def create(self, provider: OIDCProvider, browser_binding: str, return_path: str,
               purpose: str = "login") -> tuple[str, str, str]:
        if purpose not in {"login", "link", "owner-bootstrap"} or not browser_binding:
            raise OIDCError("invalid_flow")
        now = self._clock(); state, nonce, verifier = _b64_random(), _b64_random(), _b64_random()
        with self._lock:
            flows = self._load(); self._purge(flows, now)
            if len(flows) >= self.capacity:
                raise OIDCError("flow_capacity")
            flows[state] = {"provider": provider.name, "issuer": provider.issuer,
                            "client_id": provider.client_id, "redirect_uri": provider.redirect_uri,
                            "authorization_endpoint": provider.authorization_endpoint,
                            "token_endpoint": provider.token_endpoint,
                            "browser_binding_hash": hashlib.sha256(browser_binding.encode()).hexdigest(),
                            "nonce": nonce, "verifier": verifier, "return_path": validate_return_path(return_path),
                            "purpose": purpose, "created_at": now, "expires_at": now + self.ttl_seconds}
            self._save(flows)
        return state, nonce, verifier

    def peek(self, state: str) -> dict[str, Any] | None:
        with self._lock:
            flow = self._load().get(state)
            return dict(flow) if flow else None

    def consume(self, state: str, browser_binding: str, route_provider: str) -> dict[str, Any]:
        with self._lock:
            flows = self._load(); now = self._clock(); self._purge(flows, now)
            flow = flows.get(state)
            if not flow:
                self._save(flows); raise OIDCError("invalid_state")
            expected = flow.get("browser_binding_hash", "")
            actual = hashlib.sha256(browser_binding.encode()).hexdigest()
            if not hmac.compare_digest(expected, actual):
                raise OIDCError("browser_binding")
            flows.pop(state, None); self._save(flows)
            if not hmac.compare_digest(str(flow.get("provider", "")), route_provider):
                raise OIDCError("provider_mixup")
            return flow


@dataclass(frozen=True)
class OIDCStart:
    authorization_url: str
    state: str = field(repr=False)


@dataclass(frozen=True)
class OIDCResult:
    claims: dict[str, Any]
    return_path: str
    purpose: str
    provider: str


class IDTokenValidator:
    def __init__(self, provider: OIDCProvider, transport: Any, *, leeway: int = 60):
        self.provider, self.transport, self.leeway = provider, transport, leeway
        self._keys: dict[str, Any] = {}

    def _refresh(self) -> None:
        if jwt is None:
            raise OIDCError("oidc_dependencies_unavailable")
        jwks = self.transport.json_request("GET", self.provider.jwks_uri, max_bytes=65536, timeout=5)
        keys = jwks.get("keys")
        if not isinstance(keys, list) or len(keys) > 32:
            raise OIDCError("invalid_id_token")
        parsed = {}
        for item in keys:
            if not isinstance(item, dict):
                continue
            key_ops = item.get("key_ops")
            signing_use = item.get("use") in (None, "sig")
            verifies = key_ops is None or (isinstance(key_ops, list) and "verify" in key_ops)
            if (signing_use and verifies and item.get("kid")
                    and item.get("kty") in {"RSA", "EC"}
                    and item.get("alg") in ASYMMETRIC_ALGORITHMS):
                try: parsed[item["kid"]] = jwt.PyJWK.from_dict(item)
                except Exception: continue
        self._keys = parsed

    def validate(self, token: str, expected_nonce: str) -> dict[str, Any]:
        if jwt is None:
            raise OIDCError("oidc_dependencies_unavailable")
        try:
            header = jwt.get_unverified_header(token)
            alg, kid = header.get("alg"), header.get("kid")
            if alg not in ASYMMETRIC_ALGORITHMS or not isinstance(kid, str):
                raise OIDCError("invalid_id_token")
            if kid not in self._keys: self._refresh()
            if kid not in self._keys: self._refresh()  # exactly one bounded refresh for rotation
            key = self._keys.get(kid)
            if key is None or key.algorithm_name != alg:
                raise OIDCError("invalid_id_token")
            claims = jwt.decode(token, key.key, algorithms=[alg], audience=self.provider.client_id,
                                issuer=self.provider.issuer, leeway=self.leeway,
                                options={"require": ["iss", "sub", "aud", "exp", "iat", "nonce"]})
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or not hmac.compare_digest(nonce, expected_nonce):
                raise OIDCError("invalid_id_token")
            aud = claims.get("aud")
            if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != self.provider.client_id:
                raise OIDCError("invalid_id_token")
            if claims.get("azp") is not None and claims.get("azp") != self.provider.client_id:
                raise OIDCError("invalid_id_token")
            return claims
        except OIDCError:
            raise
        except Exception:
            raise OIDCError("invalid_id_token") from None


class OIDCClient:
    def __init__(self, providers: Mapping[str, OIDCProvider], flows: OIDCFlowStore, transport: Any):
        self.providers, self.flows, self.transport = dict(providers), flows, transport

    def start(self, provider_name: str, browser_binding: str, return_path: str = "/app",
              purpose: str = "login") -> OIDCStart:
        provider = self.providers.get(provider_name)
        if not provider or not provider.enabled:
            raise OIDCError("provider_unavailable")
        validator = getattr(self.transport, "validator", None)
        if validator is not None:
            validator.validate_endpoint(provider.authorization_endpoint)
        state, nonce, verifier = self.flows.create(provider, browser_binding, return_path, purpose)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        query = urlencode({"response_type": "code", "client_id": provider.client_id,
                           "redirect_uri": provider.redirect_uri, "scope": "openid email profile",
                           "state": state, "nonce": nonce, "code_challenge": challenge,
                           "code_challenge_method": "S256"})
        return OIDCStart(provider.authorization_endpoint + "?" + query, state)

    def callback_return_path(self, route_provider: str, query: str, browser_binding: str) -> str:
        """Recover only the allowlisted destination without trusting callback data."""
        try:
            states = [value for key, value in parse_qsl(query, keep_blank_values=False)
                      if key == "state"]
            if len(states) != 1:
                return "/app"
            flow = self.flows.peek(states[0])
            if not flow or flow.get("provider") != route_provider:
                return "/app"
            expected = str(flow.get("browser_binding_hash", ""))
            actual = hashlib.sha256(browser_binding.encode()).hexdigest()
            if not hmac.compare_digest(expected, actual):
                return "/app"
            return validate_return_path(str(flow.get("return_path", "")))
        except (OIDCError, ValueError, UnicodeError):
            return "/app"

    def callback(self, route_provider: str, query: str, browser_binding: str) -> OIDCResult:
        try:
            params = validate_callback_params(query)
        except OIDCError:
            # Burn a uniquely identifiable, browser-bound flow even on malformed
            # provider callbacks so an error can never leave reusable state.
            try:
                states = [value for key, value in parse_qsl(query, keep_blank_values=False)
                          if key == "state"]
                if len(states) == 1:
                    self.flows.consume(states[0], browser_binding, route_provider)
            except (OIDCError, ValueError, UnicodeError):
                pass
            raise
        flow = self.flows.consume(params["state"], browser_binding, route_provider)
        provider = self.providers.get(flow["provider"])
        bindings = ("issuer", "client_id", "redirect_uri", "authorization_endpoint", "token_endpoint")
        if not provider or any(flow.get(name) != getattr(provider, name) for name in bindings):
            raise OIDCError("provider_mixup")
        response_issuer = params.get("iss")
        if response_issuer is not None and response_issuer != provider.issuer:
            raise OIDCError("provider_mixup")
        if provider.authorization_response_iss_parameter_supported and response_issuer is None:
            raise OIDCError("provider_mixup")
        if "error" in params:
            raise OIDCError("authorization_denied")
        form = {"grant_type": "authorization_code", "code": params["code"],
                "redirect_uri": flow["redirect_uri"], "client_id": provider.client_id,
                "code_verifier": flow["verifier"]}
        headers: dict[str, str] = {}
        if provider.token_auth_method == "client_secret_basic":
            raw = f"{provider.client_id}:{provider.client_secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
        elif provider.token_auth_method == "client_secret_post":
            form["client_secret"] = provider.client_secret
        token_data = self.transport.json_request("POST", provider.token_endpoint, headers=headers,
                                                 form=form, max_bytes=65536, timeout=5)
        id_token = token_data.get("id_token")
        if not isinstance(id_token, str) or len(id_token) > 32768:
            raise OIDCError("invalid_id_token")
        claims = IDTokenValidator(provider, self.transport).validate(id_token, flow["nonce"])
        access_token = token_data.get("access_token")
        if provider.userinfo_endpoint and isinstance(access_token, str):
            info = self.transport.json_request("GET", provider.userinfo_endpoint,
                                               headers={"Authorization": "Bearer " + access_token},
                                               max_bytes=65536, timeout=5)
            if info.get("sub") != claims.get("sub"):
                raise OIDCError("userinfo_mismatch")
            for name in ("email", "email_verified", "name"):
                if name in info: claims[name] = info[name]
        return OIDCResult(dict(claims), flow["return_path"], flow["purpose"], provider.name)
