#!/usr/bin/env python3
"""SaaS HTTP server for LucidFence — 100% local, multi-tenant.

This server wraps the existing single-fleet engine and adds the SaaS layer:
- Authentication (login/signup/logout) with session cookies
- Multi-tenant organizations, each with its own isolated data dir + engine
- RBAC enforced per endpoint
- REST API for every product module (map, devices, fences, risk, policies,
  compliance, analytics, reports, billing, users, settings)
- Plan limits (mock billing) enforced on write paths

Nothing leaves the machine. Runs on 127.0.0.1.

Routes (auth):
  POST /api/auth/signup      body {email,name,password,org_name} -> {token,user,org}
  POST /api/auth/login       body {email,password} -> {token,user}
  POST /api/auth/logout
  GET  /api/auth/me          -> current user + orgs (requires session)

Routes (orgs, require session):
  POST /api/orgs/<id>/switch -> sets active org cookie
  GET  /api/org              -> active org profile + plan + limits

Routes (product, require session + capability + scoped to active org):
  GET  /api/status
  POST /api/run-once
  GET  /api/devices  (+ ?state=)
  GET  /api/devices/<id>
  GET  /api/fences           -> fence IDs only (geometry comes from /api/status.st.fences)
  GET  /api/risk
  GET  /api/incidents
  GET  /api/policies
  GET  /api/analytics
  GET  /api/compliance
  GET  /api/report
  GET  /api/plan             (billing mock)
  POST /api/plan/upgrade     (owner) switch plan
  GET  /api/users            (owner/admin) list org users
  POST /api/users            (owner/admin) invite user
  GET  /api/settings/status
  POST /api/settings         save credentials
  POST /api/settings/test

Static dashboard served at /.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import sys
import threading
import time
import http.client  # bypass del proxy de entorno (GET a 127.0.0.1 pasa, pero usamos esto por robustez)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Optional

# make sure sibling 'core' and 'saas' importable
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core"))

import config_loader
from saas.tenant import TenantStore, PLAN_LIMITS
from saas.auth import AuthStore, ROLE_LABELS, ROLE_CAPS
from core.engine import Engine
from core.product import build_product
from core import secrets as core_secrets
from core import ai_provider
from core import workflows as WF  # workflows module (templates + custom builder)
from core.actions import VALID_ACTIONS
from core.alerts import ALERT_TYPES, CHANNELS, ALERT_TYPE_LABELS
from core.app_paths import ensure_data_dir

STATIC = ROOT / "static"
TEMPLATE_DATA = ROOT / "data"
CONFIG_FILE = ROOT / os.environ.get("LUCIDFENCE_CONFIG_FILE", "config.json")
DATA_ROOT = ensure_data_dir()
COOKIE_SESSION = "gf_session"
COOKIE_ORG = "gf_org"

# Global stores for the local app. Runtime data never lives in Homebrew's
# Cellar nor in the source checkout unless LUCIDFENCE_DATA_DIR explicitly says so.
_tenants = TenantStore(DATA_ROOT)
_auth = AuthStore(DATA_ROOT)
# Seed de la cuenta demo para que la vitrina/CI puedan autenticarse sin
# configuracion manual (ciso@acme.test / demo1234). Idempotente: si el
# usuario ya existe, no hace nada. Si el tenant demo no existe, lo crea.
try:
    if _auth.get_by_email("ciso@acme.test") is None:
        _demo_org = None
        for o in _tenants.all():
            if o.slug == "acme-logistics":
                _demo_org = o
                break
        if _demo_org is None:
            _demo_org = _tenants.create("Acme Logistics (demo)", "usr_demo_seed", "free")
        _auth.create_user("ciso@acme.test", "CISCO Acme (demo)", "demo1234",
                          _demo_org.id, "owner")
except Exception:
    pass
_SIMULATION = False

# Per-org engine cache. Each org gets its own running engine.
_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()


def _apply_tenant_integration(cfg: dict, tdir: Path) -> dict:
    """Overlay tenant-local credentials/mode without leaking another org's key."""
    key = core_secrets.read_key(tdir)
    workspace_id = core_secrets.read_org_id(tdir)
    runtime = {}
    runtime_path = tdir / "integration.json"
    try:
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    except Exception:
        runtime = {}
    configured = bool(key and workspace_id)
    mode = runtime.get("mode")
    if mode not in ("live", "simulation"):
        mode = "live" if configured else "simulation"
    if mode == "live" and not configured:
        mode = "simulation"
    cfg["mode"] = mode
    cfg["dry_run"] = bool(runtime.get("dry_run", cfg.get("dry_run", True)))
    cfg["_applivery_api_key"] = key
    cfg.setdefault("applivery", {})["org_id"] = workspace_id
    cfg["incident_webhook_url"] = (runtime.get("incident_webhook_url") or "").strip()
    # Atomic Mail Agentic: real email for the SaaS (opt-in per tenant).
    am = runtime.get("atomicmail") or {}
    if isinstance(am, dict) and am:
        cfg["atomicmail"] = {k: v for k, v in am.items() if v not in (None, "")}
    # Whitelabel domain (DigitalPlat FreeDomain) used as the sender/branding
    # domain for sovereign email (paired with Atomic Mail's DKIM).
    wl = runtime.get("whitelabel") or {}
    if isinstance(wl, dict) and wl.get("domain"):
        cfg["whitelabel"] = {k: v for k, v in wl.items() if v not in (None, "")}
    return cfg


def _save_tenant_integration(tdir: Path, mode: str, dry_run: bool,
                             incident_webhook_url: str = "",
                             atomicmail: dict | None = None,
                             whitelabel: dict | None = None) -> None:
    path = tdir / "integration.json"
    runtime = {}
    try:
        runtime = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        runtime = {}
    runtime["mode"] = mode
    runtime["dry_run"] = bool(dry_run)
    if incident_webhook_url is not None:
        if incident_webhook_url:
            runtime["incident_webhook_url"] = incident_webhook_url.strip()
        else:
            runtime.pop("incident_webhook_url", None)
    if atomicmail is not None:
        # atomicmail carries the tenant's Atomic Mail config (username / api_key
        # / recipient). Strip empty values; the api_key is a secret and lives in
        # this tenant-local, chmod 0600 file only.
        cleaned = {k: v for k, v in (atomicmail or {}).items() if v not in (None, "")}
        if cleaned:
            runtime["atomicmail"] = cleaned
        else:
            runtime.pop("atomicmail", None)
    if whitelabel is not None:
        # whitelabel = tenant's FreeDomain domain + dkim selector, used as the
        # sender/branding domain for sovereign email. domain is not secret.
        cleaned = {k: v for k, v in (whitelabel or {}).items() if v not in (None, "")}
        if cleaned:
            runtime["whitelabel"] = cleaned
        else:
            runtime.pop("whitelabel", None)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)


def _tenant_runtime(tdir: Path) -> dict:
    try:
        data = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _masked_secret(secret: str) -> str:
    secret = secret or ""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return "*" * (len(secret) - 4) + secret[-4:]


def _header(headers, name: str) -> str:
    for key in (name, name.lower(), name.upper()):
        try:
            value = headers.get(key)
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return ""


def _verify_soar_webhook_hmac(raw_body: bytes, headers, secret: str,
                              now: float | None = None,
                              tolerance_seconds: int = 300) -> tuple[bool, str]:
    """Validate inbound SOAR webhook HMAC with timestamp anti-replay.

    Contract: X-LucidFence-Timestamp contains unix seconds and
    X-LucidFence-Signature (or X-Hub-Signature-256) contains the hex HMAC-SHA256
    of ``<timestamp>.<raw_body>`` using the tenant's SOAR webhook secret.
    Accepted signature wrappers: ``sha256=<hex>`` or ``v1=<hex>``.
    """
    if not secret:
        return False, "soar webhook secret not configured"
    ts = _header(headers, "X-LucidFence-Timestamp")
    if not ts:
        return False, "missing timestamp"
    try:
        ts_float = float(ts)
    except (TypeError, ValueError):
        return False, "invalid timestamp"
    now = time.time() if now is None else now
    if abs(now - ts_float) > tolerance_seconds:
        return False, "timestamp outside replay window"
    signature = _header(headers, "X-LucidFence-Signature") or _header(headers, "X-Hub-Signature-256")
    if not signature:
        return False, "missing signature"
    if "=" in signature:
        algo, _, signature = signature.partition("=")
        if algo not in ("sha256", "v1"):
            return False, "unsupported signature algorithm"
    signature = signature.strip().lower()
    if len(signature) != 64:
        return False, "invalid signature length"
    signed = ts.encode("utf-8") + b"." + (raw_body or b"")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "invalid signature"
    return True, "ok"


# ---------------------------------------------------------------------------
# MoA bridge: llamadas directas a 127.0.0.1:8085 vía http.client (bypasea el
# proxy de entorno que intercepta POST a localhost). No lanza nunca.
# ---------------------------------------------------------------------------
def _ai_get(url: str):
    try:
        p = urlparse(url)
        c = http.client.HTTPConnection(p.hostname, p.port, timeout=5)
        c.request("GET", p.path)
        r = c.getresponse()
        data = r.read().decode("utf-8", "replace")
        c.close()
        if r.status == 200:
            return json.loads(data)
    except Exception:
        return None
    return None


def _ai_post(url: str, payload: dict):
    try:
        p = urlparse(url)
        body = json.dumps(payload).encode("utf-8")
        c = http.client.HTTPConnection(p.hostname, p.port, timeout=120)
        c.request("POST", p.path, body=body,
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        data = r.read().decode("utf-8", "replace")
        c.close()
        if r.status == 200:
            return json.loads(data)
    except Exception:
        return None
    return None


_REQUIRED_TENANT_SEEDS = ("routes.json", "policies.json", "fleet_seed.json", "fences.json")
_OPTIONAL_TENANT_SEEDS = ("device_overrides.json",)


def _seed_tenant_defaults(tdir: Path) -> None:
    """Copy immutable packaged templates into a new tenant data directory."""
    tdir.mkdir(parents=True, exist_ok=True)
    for name in (*_REQUIRED_TENANT_SEEDS, *_OPTIONAL_TENANT_SEEDS):
        src = TEMPLATE_DATA / name
        dst = tdir / name
        if dst.exists():
            continue
        if not src.is_file():
            if name in _REQUIRED_TENANT_SEEDS:
                raise FileNotFoundError(f"LucidFence package is missing required seed: {src}")
            continue
        raw = src.read_text(encoding="utf-8")
        json.loads(raw)
        temp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
        try:
            temp.write_text(raw, encoding="utf-8")
            os.chmod(temp, 0o600)
            os.replace(temp, dst)
        finally:
            temp.unlink(missing_ok=True)


def engine_for(org_id: str) -> Engine:
    with _engines_lock:
        if org_id in _engines:
            return _engines[org_id]
        cfg = config_loader.load(CONFIG_FILE)
        # point data dir at the tenant's isolated directory
        tdir = _tenants.data_dir(org_id)
        cfg["data_dir"] = str(tdir)
        # seed per-tenant defaults once so each org starts with the demo data
        # but remains isolated afterwards (this is what makes it a real SaaS)
        _seed_tenant_defaults(tdir)
        cfg["fences_path"] = str(tdir / "fences.json")
        cfg["routes_path"] = str(tdir / "routes.json")
        cfg["policies_path"] = str(tdir / "policies.json")
        cfg["sim_seed_path"] = str(tdir / "fleet_seed.json")
        cfg = _apply_tenant_integration(cfg, tdir)
        eng = Engine(cfg)
        eng.tenant_id = org_id
        if cfg.get("autostart", True):
            eng.start()
        _engines[org_id] = eng
        return eng


def reload_engine(org_id: str) -> Engine:
    """Rebuild the cached engine for an org from the current config/.env.

    Used after the operator saves new Applivery credentials or flips the mode
    in Settings, so the live integration takes effect without a full restart.
    """
    with _engines_lock:
        old = _engines.pop(org_id, None)
        if old is not None:
            try:
                old.stop()
            except Exception:
                pass
        cfg = config_loader.load(CONFIG_FILE)
        tdir = _tenants.data_dir(org_id)
        cfg["data_dir"] = str(tdir)
        _seed_tenant_defaults(tdir)
        cfg["fences_path"] = str(tdir / "fences.json")
        cfg["routes_path"] = str(tdir / "routes.json")
        cfg["policies_path"] = str(tdir / "policies.json")
        cfg["sim_seed_path"] = str(tdir / "fleet_seed.json")
        cfg = _apply_tenant_integration(cfg, tdir)
        eng = Engine(cfg)
        eng.tenant_id = org_id
        if cfg.get("autostart", True):
            eng.start()
        _engines[org_id] = eng
        return eng


def user_from_request(handler) -> Optional[dict]:
    token = _cookie(handler, COOKIE_SESSION)
    if token:
        sess = _auth.get_session(token)
        if sess:
            u = _auth.get(sess["user_id"])
            if u and u.active:
                return u.to_public()
    # No anonymous fallback. La dashboard local obtiene una sesión real con
    # RBAC vía /api/auth/login; toda llamada API requiere esa cookie de sesión.
    # (No hay endpoint demo: un request no autenticado nunca se trata como
    # owner del demo — vé test_frontend_contract seguridad.)
    return None


def active_org(handler, user) -> Optional[str]:
    org = _cookie(handler, COOKIE_ORG)
    if org:
        # Strict: only honor an explicit org cookie if it belongs to the user.
        # Fall back to the first org only when no cookie is set, never when the
        # cookie names an org the user is not a member of (prevents cross-org
        # escalation via a forged gf_org cookie).
        if org in user["org_roles"]:
            return org
        return None
    # fall back to first org
    if user["org_roles"]:
        return next(iter(user["org_roles"]))
    return None


def require(handler, cap: Optional[str] = None):
    """Return (user, org) or send 401/403 and return None."""
    user = user_from_request(handler)
    if not user:
        _send_json(handler, {"error": "no autenticado"}, 401)
        return None
    org = active_org(handler, user)
    if not org:
        _send_json(handler, {"error": "sin organización activa"}, 403)
        return None
    if cap:
        role = user["org_roles"].get(org)
        if not AuthStore.can(role, cap):
            _send_json(handler, {"error": "sin permiso", "capability": cap}, 403)
            return None
    return user, org


def _cookie(handler, name: str) -> Optional[str]:
    for c in handler.headers.get_all("Cookie") or []:
        for part in c.split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
    return None


def _host_allowed(handler) -> bool:
    """Reject requests whose Host header points elsewhere (DNS-rebinding /
    CSRF against a non-loopback bind). Allow loopback + configured host."""
    import os
    host = (handler.headers.get("Host") or "").split(":")[0].strip().lower()
    if not host:
        return True  # let non-HTTP/1.1 or missing header through (server decides)
    allowed = {"127.0.0.1", "localhost", "::1",
               (os.environ.get("LUCIDFENCE_HOST") or "").lower()}
    allowed.discard("")
    if host in allowed:
        return True
    # allow a configured public host (e.g. behind a reverse proxy)
    cfg_host = ""
    try:
        cfg_host = (handler.server and getattr(handler.server, "lucidfence_host", "")) or ""
    except Exception:
        cfg_host = ""
    return host == cfg_host.lower()


def _bound_host(handler) -> str:
    address = getattr(getattr(handler, "server", None), "server_address", None)
    if isinstance(address, tuple) and address:
        return str(address[0]).strip().lower()
    return ""


def _gateway_allowed(handler) -> bool:
    """Allow anonymous OpenAI-compatible traffic only on a loopback bind."""
    loopback = {"127.0.0.1", "localhost", "::1"}
    bound = _bound_host(handler)
    client = (handler.client_address[0] if handler.client_address else "").lower()
    if bound in loopback and client in loopback:
        return True
    expected = os.environ.get("LUCIDFENCE_GATEWAY_TOKEN", "")
    supplied = handler.headers.get("Authorization", "")
    return len(expected) >= 16 and hmac.compare_digest(supplied, "Bearer " + expected)


def _gateway_tenant(handler):
    """Resolve an explicit org, otherwise the first org with AI configured."""
    requested = (handler.headers.get("X-LucidFence-Org", "") or "").strip()
    if requested and _tenants.get(requested):
        return requested
    for item in _tenants.all():
        if ai_provider.status(_tenants.data_dir(item.id)).get("configured"):
            return item.id
    return None


def _set_cookie(handler, name: str, value: str, max_age: int = 60 * 60 * 24 * 7):
    # Accumulate; emitted inside _send_json AFTER send_response (Python 3.9
    # flush-order quirk: send_header before send_response leaks the header first)
    lst = getattr(handler, "_set_cookies", None)
    if lst is None:
        lst = handler._set_cookies = []
    secure = ""
    try:
        proto = (handler.headers.get("X-Forwarded-Proto") or "").lower()
        if proto == "https" or os.environ.get("LUCIDFENCE_TLS") == "1":
            secure = "Secure; "
    except Exception:
        secure = ""
    lst.append(f"{name}={value}; Path=/; HttpOnly; {secure}SameSite=Strict; Max-Age={max_age}")


def _clear_cookie(handler, name: str):
    lst = getattr(handler, "_set_cookies", None)
    if lst is None:
        lst = handler._set_cookies = []
    lst.append(f"{name}=; Path=/; HttpOnly; Max-Age=0")


def _safe_webhook_url(url: str):
    """SSRF guard: only https, never private/link-local/loopback targets.
    Returns the normalized URL or '' if unsafe/unusable."""
    from urllib.parse import urlparse
    if not url:
        return ""
    try:
        p = urlparse(url)
    except Exception:
        return ""
    if p.scheme != "https":
        return ""
    host = (p.hostname or "").lower()
    if not host:
        return ""
    import ipaddress
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return ""
    except ValueError:
        # hostname (not IP): block obvious internal suffixes
        if host.endswith((".local", ".internal", ".lan", ".home")) or host == "localhost":
            return ""
    return url


def _send_json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Cache-Control", "no-store")
    # CSP: only same-origin resources; blocks injected third-party scripts (XSS)
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
    )
    for c in getattr(handler, "_set_cookies", []) or []:
        handler.send_header("Set-Cookie", c)
    handler._set_cookies = []
    handler.end_headers()
    handler.wfile.write(body)


def _send_file(handler, path: Path, content_type: str):
    try:
        body = path.read_bytes()
    except FileNotFoundError:
        handler.send_error(404)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_csv(handler, filename: str, csv_text: str):
    body = csv_text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_pdf(handler, filename: str, pdf_bytes: bytes):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(pdf_bytes)))
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(pdf_bytes)


def _send_html(handler, html_text: str):
    body = html_text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _summary(devices: list[dict]) -> dict:
    total = len(devices)
    compliant = sum(1 for d in devices if d.get("compliant") is True)
    noncompliant = sum(1 for d in devices if d.get("compliant") is False)
    outside = sum(1 for d in devices if d.get("fence_state") == "outside")
    high_risk = sum(1 for d in devices if (float(d.get("risk_score") or 0)) >= 70)
    return {
        "total": total, "compliant": compliant, "noncompliant": noncompliant,
        "outside": outside, "high_risk": high_risk,
    }


def _atomicmail_username_for_org(org) -> str:
    """Return a stable Atomic Mail username candidate for one local org."""
    raw = "".join(ch for ch in (getattr(org, "slug", "") or "lucidfence") if ch.isalnum())
    raw = (raw or "lucidfence").lower()
    suffix = (getattr(org, "id", "") or "local")[-4:].lower()
    username = f"lf{raw[:15]}{suffix}"
    if len(username) < 5:
        username = (username + "local")[:5]
    return username[:21]


def _welcome_email_text(name: str, org) -> str:
    who = (name or "equipo").strip()
    org_name = getattr(org, "name", "tu organización")
    return "\n".join([
        f"Hola {who},",
        "",
        f"Bienvenido a LucidFence para {org_name}.",
        "LucidFence corre 100% local/on-prem: no tienes que registrar nada en una nube de LucidFence.",
        "",
        "3 pasos para activar valor hoy:",
        "1) Arrancar: instala/actualiza y levanta el panel local con `brew install adrimg3196/lucidfence/lucidfence` y `lucidfence serve`.",
        "2) Geocercas: crea tu primera geocerca crítica (almacén, tienda, ruta o zona de riesgo) y asigna dispositivos piloto.",
        "3) Incidencias: abre Riesgo/Incidencias, fuerza un ciclo y revisa evidencias, severidad y acciones sugeridas antes de pasar a live.",
        "",
        "Tip: empieza con el tier gratis y un piloto de 5 dispositivos; cuando veas señal, conecta Applivery/UEM en Ajustes.",
        "",
        "Descarga gratis y docs: https://github.com/adrimg3196/lucidfence",
        "",
        "— LucidFence",
    ])


def _test_or_placeholder_email(email: str) -> bool:
    domain = (email.rsplit("@", 1)[-1] if "@" in email else "").lower()
    return domain.endswith(".test") or domain.endswith(".local") or domain in {"example.com", "example.org", "example.net"}


def _send_signup_welcome_email(email: str, name: str, org) -> dict:
    """Best-effort Atomic Mail welcome for a newly-created local tenant.

    The product remains sovereign/local: this sends from the customer's own
    local instance via Atomic Mail and never requires a LucidFence cloud signup.
    It is deliberately non-fatal: signup must succeed even if mail/network is
    unavailable. Test/placeholder domains are skipped to keep CI hermetic.
    """
    email = (email or "").strip()
    if not email or "@" not in email:
        return {"attempted": False, "sent": False, "reason": "email_invalido"}
    if _test_or_placeholder_email(email):
        return {"attempted": False, "sent": False, "reason": "destinatario_test"}
    try:
        from core.atomicmail_client import build_tenant_mailbox
        tdir = _tenants.data_dir(org.id)
        runtime = _tenant_runtime(tdir)
        am = runtime.get("atomicmail") or {}
        username = (am.get("username") or os.environ.get("LUCIDFENCE_WELCOME_ATOMICMAIL_USERNAME")
                    or _atomicmail_username_for_org(org)).strip()
        api_key = (am.get("api_key") or os.environ.get("LUCIDFENCE_WELCOME_ATOMICMAIL_API_KEY") or "").strip()
        wl = runtime.get("whitelabel") or {}
        inbox_domain = (wl.get("domain") or "").strip() or None
        mb = build_tenant_mailbox(tdir, username=username or None, api_key=api_key or None,
                                  inbox_domain=inbox_domain)
        subject = "[LucidFence] Bienvenido: 3 pasos para activar valor hoy"
        ok = mb.send(to=email, subject=subject, text=_welcome_email_text(name, org))
        status = {"attempted": True, "sent": bool(ok), "inbox": mb.status().get("inbox")}
        if ok:
            saved_key = mb.persist_api_key()
            if saved_key:
                new_am = dict(am)
                new_am.update({"username": username, "api_key": saved_key,
                               "digest_email_to": am.get("digest_email_to") or email})
                _save_tenant_integration(
                    tdir,
                    runtime.get("mode", "simulation"),
                    bool(runtime.get("dry_run", True)),
                    incident_webhook_url=runtime.get("incident_webhook_url", ""),
                    atomicmail=new_am,
                    whitelabel=wl if wl else None,
                )
        else:
            status["last_error"] = mb.status().get("last_error")
        return status
    except Exception as exc:  # noqa: BLE001 - welcome email must never break signup
        return {"attempted": True, "sent": False, "reason": f"{type(exc).__name__}: {exc}"}


def _read_body(handler) -> dict:
    raw = getattr(handler, "_preread_body", None)
    if raw is None:
        try:
            length = int(handler.headers.get("Content-Length", 0) or 0)
        except (ValueError, TypeError):
            return {}
        if not length:
            return {}
        if length > 1_048_576:  # 1 MiB hard cap
            return {}
        raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8", "replace") or "{}")
    except Exception:
        return {}
    # Contract: request bodies are JSON objects. Arrays/strings/numbers would
    # otherwise crash handlers that call body.get(...) with an AttributeError
    # and leak a 500 stack trace.
    return data if isinstance(data, dict) else {}



def _product_bundle(eng: Engine) -> dict:
    st = eng.status()
    st["stats_history"] = eng.store.stats_history(120)
    return build_product(st, eng)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        return

    def do_GET(self):
        if not _host_allowed(self):
            self.send_error(400, "bad host")
            return
        try:
            self._route()
        except Exception as e:
            import traceback
            print("ROUTE ERROR:", traceback.format_exc())
            try:
                _send_json(self, {"error": "server_error", "detail": str(e)}, 500)
            except Exception:
                pass

    def do_POST(self):
        if not _host_allowed(self):
            self.send_error(400, "bad host")
            return
        try:
            # Pre-read the full body so the socket is left clean under HTTP/1.0
            # (otherwise the connection closes with unread bytes and the client
            # sees "HTTP/0.9 when not allowed"). _read_body() reuses it.
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length > 0:
                self._preread_body = self.rfile.read(length)
            else:
                self._preread_body = b""
            self._route()
        except Exception as e:
            import traceback
            print("ROUTE ERROR:", traceback.format_exc())
            try:
                _send_json(self, {"error": "server_error", "detail": str(e)}, 500)
            except Exception:
                pass

    def do_DELETE(self):
        try:
            self._route()
        except Exception as e:
            import traceback
            print("ROUTE ERROR:", traceback.format_exc())
            try:
                _send_json(self, {"error": "server_error", "detail": str(e)}, 500)
            except Exception:
                pass

    def _route(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)
        method = self.command

        # static
        if route in ("/", "/app", "/app/", "/dashboard", "/dashboard.html"):
            _send_file(self, STATIC / "dashboard.html", "text/html; charset=utf-8")
            return
        if route in ("/about", "/index.html", "/landing", "/landing.html"):
            _send_file(self, STATIC / "index.html", "text/html; charset=utf-8")
            return
        if route.startswith("/static/"):
            rel = route[len("/static/"):]
            p = (STATIC / rel).resolve()
            if p.is_relative_to(STATIC):
                ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
                if p.suffix == ".js":
                    ct = "application/javascript"
                _send_file(self, p, ct)
            else:
                self.send_error(404)
            return

        # ---- auth ----
        if route == "/api/auth/signup" and method == "POST":
            return self._signup()
        if route == "/api/auth/demo" and method == "POST":
            return self._demo_login()
        if route == "/api/auth/login" and method == "POST":
            return self._login()
        if route == "/api/auth/logout" and method == "POST":
            return self._logout()
        if route == "/api/auth/me" and method == "GET":
            user = user_from_request(self)
            if not user:
                return _send_json(self, {"error": "no autenticado"}, 401)
            return _send_json(self, {"user": user,
                                     "orgs": [o.to_dict() for o in _tenants.list_for_user(user["id"])]})

        # ---- Healthcheck sin auth (para monitoreo externo / start_all.sh) ----
        if route == "/api/health" and method == "GET":
            return _send_json(self, {"status": "ok", "service": "lucidfence",
                                     "desktop_nonce": os.environ.get("LUCIDFENCE_DESKTOP_NONCE", ""),
                                     "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

        # ---- Incoming SOAR webhook (headless automation, HMAC-authenticated) ----
        # External SOAR tools cannot hold a browser session cookie. This endpoint
        # is intentionally before `require(self)`, but every request must carry a
        # tenant-scoped HMAC signature over the exact raw body + timestamp.
        if route.startswith("/api/soar/webhook/") and method == "POST":
            org_id = route[len("/api/soar/webhook/"):].strip("/")
            if not org_id or _tenants.get(org_id) is None:
                return _send_json(self, {"ok": False, "error": "tenant no encontrado"}, 404)
            tdir = _tenants.data_dir(org_id)
            runtime = _tenant_runtime(tdir)
            secret = (runtime.get("soar_webhook_secret")
                      or os.environ.get("LUCIDFENCE_SOAR_WEBHOOK_SECRET") or "")
            raw = getattr(self, "_preread_body", b"") or b""
            ok, reason = _verify_soar_webhook_hmac(raw, self.headers, secret)
            if not ok:
                return _send_json(self, {"ok": False, "error": reason}, 401)
            body = _read_body(self)
            device_id = (body.get("device_id") or body.get("deviceId") or "").strip()
            action = (body.get("action") or "").strip().lower()
            params = body.get("params")
            if not isinstance(params, dict):
                params = {}
            if not device_id or not action:
                return _send_json(self, {"ok": False, "error": "device_id y action son obligatorios"}, 400)
            eng = engine_for(org_id)
            dev = eng.store.get(device_id)
            if dev is None:
                return _send_json(self, {"ok": False, "error": "dispositivo no encontrado"}, 404)
            result = eng.run_command(dev, action, params, operator="soar:webhook")
            result["soar_webhook"] = True
            return _send_json(self, {"ok": bool(result.get("ok") or result.get("delegated") or result.get("dry_run")),
                                     "result": result})

        # ---- Local OpenAI-compatible gateway (headless clients / MCP) ----
        if route == "/v1/chat/completions" and method == "POST":
            if not _gateway_allowed(self):
                return _send_json(self, {"error": {"message": "gateway bearer token requerido", "type": "authentication_error"}}, 401)
            org_id = _gateway_tenant(self)
            if not org_id:
                return _send_json(self, {"error": {"message": "no hay proveedor AI configurado", "type": "provider_not_configured"}}, 503)
            body = _read_body(self)
            messages = body.get("messages") if isinstance(body, dict) else None
            if not isinstance(messages, list) or not messages:
                return _send_json(self, {"error": {"message": "messages debe ser una lista no vacía", "type": "invalid_request_error"}}, 400)
            result = ai_provider.chat(_tenants.data_dir(org_id), messages, body)
            if not result.get("ok"):
                return _send_json(self, {"error": {"message": result.get("error", "provider error"), "type": "provider_error"}}, int(result.get("status") or 502))
            return _send_json(self, result["response"])

        # everything else needs a session
        guarded = require(self)
        if guarded is None:
            return
        user, org = guarded

        # engine is per-org; build/lookup it once for the whole request
        eng = engine_for(org)

        if route == "/api/fences" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "fence:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            return _send_json(self, {"fences": eng.status().get("fences", [])})
        if route == "/api/fences" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "fence:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            try:
                fence = eng.add_fence(_read_body(self))
            except ValueError as exc:
                return _send_json(self, {"error": str(exc)}, 400)
            rows = eng.status().get("fences", [])
            created = next((f for f in rows if f.get("id") == fence.id), None)
            return _send_json(self, {"ok": True, "fence": created, "fences": rows})
        if route.startswith("/api/fences/") and method == "DELETE":
            if not AuthStore.can(user["org_roles"].get(org), "fence:delete"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            fence_id = route[len("/api/fences/"):]
            if not eng.delete_fence(fence_id):
                return _send_json(self, {"error": "geovalla no encontrada"}, 404)
            return _send_json(self, {"ok": True, "fences": eng.status().get("fences", [])})

        # routes (route:read to list; route:write to create; route:delete to delete)
        if route == "/api/routes" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "route:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            return _send_json(self, {"routes": [r.to_dict() for r in eng.routes]})
        if route == "/api/routes" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "route:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            try:
                eng.add_route(body)
            except ValueError as e:
                return _send_json(self, {"error": str(e)}, 400)
            return _send_json(self, {"ok": True, "routes": [r.to_dict() for r in eng.routes]})
        if route.startswith("/api/routes/") and route.endswith("/delete") and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "route:delete"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            rid = route[len("/api/routes/"):-len("/delete")]
            eng.delete_route(rid)
            return _send_json(self, {"ok": True, "routes": [r.to_dict() for r in eng.routes]})

        # --- workflows (workflow:read to list; workflow:write to apply/create/delete) ---
        if route == "/api/workflows" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "workflow:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            return _send_json(self, {
                "templates": WF.TEMPLATES,
                "triggers": WF.trigger_options(),
                "actions": WF.action_options(),
                "active": eng.active_workflows(),
            })
        if route == "/api/workflows/apply" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "workflow:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            try:
                pol = WF.build_policy_from_template(
                    body.get("template_id"), body.get("device_ids"))
            except ValueError as e:
                return _send_json(self, {"error": str(e)}, 400)
            eng.add_policy(pol)
            return _send_json(self, {"ok": True, "policy": pol,
                                   "active": eng.active_workflows()})
        if route == "/api/workflows/custom" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "workflow:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            try:
                pol = WF.build_custom_policy(body)
            except ValueError as e:
                return _send_json(self, {"error": str(e)}, 400)
            eng.add_policy(pol)
            return _send_json(self, {"ok": True, "policy": pol,
                                   "active": eng.active_workflows()})
        if route.startswith("/api/workflows/") and route.endswith("/delete") and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "workflow:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            pid = route[len("/api/workflows/"):-len("/delete")]
            eng.delete_policy(pid)
            return _send_json(self, {"ok": True, "active": eng.active_workflows()})

        if route == "/api/devices" and method == "GET":
            states = list(eng.store.snapshot().values())
            st = qs.get("state", [None])[0]
            if st:
                states = [s for s in states if s.fence_state == st]
            return _send_json(self, [s.to_dict() for s in states])

        if route == "/api/org" and method == "GET":
            o = _tenants.get(org)
            return _send_json(self, {"org": o.to_dict(), "plan": PLAN_LIMITS.get(o.plan),
                                     "role": user["org_roles"].get(org)})

        if route.startswith("/api/orgs/") and route.endswith("/switch") and method == "POST":
            target = route[len("/api/orgs/"):-len("/switch")]
            if target not in user["org_roles"]:
                return _send_json(self, {"error": "no perteneces a esa org"}, 403)
            _set_cookie(self, COOKIE_ORG, target)
            return _send_json(self, {"ok": True, "org": target})

        if route == "/api/run-once" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:run"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            try:
                stats = eng.run_once()
            except Exception as exc:  # robustness: never 500 the UI on a flaky cycle
                return _send_json(self, {"ok": False, "error": f"cycle_error: {type(exc).__name__}: {exc}"})
            return _send_json(self, {"ok": True, "stats": stats})
        if route == "/api/status" and method == "GET":
            raw = eng.status()
            st = raw.get("stats", {}) or {}
            fences = raw.get("fences", [])
            # Derive live device counts from the actual state store so the
            # dashboard reflects devices even before the first auto-cycle.
            snap = list(eng.store.snapshot().values())
            device_count = len(snap)
            inside_count = sum(1 for s in snap if s.fence_state == "inside")
            outside_count = sum(1 for s in snap if s.fence_state == "outside")
            unknown_count = sum(1 for s in snap if s.fence_state == "unknown")
            noncompliant = sum(1 for s in snap if s.compliant is False)
            # Return the full engine status (devices, trails, events, actions,
            # stats_history, fences, routes) — the SPA consumes all of it.
            raw.update({
                "device_count": device_count or st.get("devices_total", 0),
                "inside_count": inside_count or st.get("inside", 0),
                "outside_count": outside_count or st.get("outside", 0),
                "unknown_count": unknown_count or st.get("unknown", 0),
                "noncompliant": noncompliant or st.get("non_compliant", 0),
                "events_this_cycle": st.get("events_this_cycle", 0),
                "actions_this_cycle": st.get("actions_this_cycle", 0),
                "integration_error": st.get("integration_error"),
                "last_cycle_at": st.get("ts") or eng.last_run,
                "cycle_period_s": eng.interval,
            })
            return _send_json(self, raw)
        if route.startswith("/api/devices/") and method == "GET":
            dev_id = route[len("/api/devices/"):]
            d = eng.store.get(dev_id)
            if not d:
                return _send_json(self, {"error": "not found"}, 404)
            return _send_json(self, {"device": d.to_dict(),
                                     "trail": eng.store.trail(dev_id, 200),
                                     "events": [e for e in eng.store.recent_events(200) if e.get("device_id") == dev_id][-20:],
                                     "actions": [a for a in eng.store.recent_actions(200) if a.get("device_id") == dev_id][-20:]})

        # --- on-demand remote command (MDM/UEM action) ---------------------
        if route.startswith("/api/devices/") and route.endswith("/command") and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "device:action"):
                return _send_json(self, {"error": "sin permiso para enviar comandos"}, 403)
            dev_id = route[len("/api/devices/"):-len("/command")]
            dev = eng.store.get(dev_id)
            if not dev:
                return _send_json(self, {"error": "dispositivo no encontrado"}, 404)
            body = _read_body(self)
            action = (body.get("action") or "").strip().lower()
            if action not in VALID_ACTIONS:
                return _send_json(self, {"error": "accion no valida",
                                         "valid": sorted(VALID_ACTIONS)}, 400)
            params = dict(body.get("params") or {})
            # operator-initiated command: respect destructive cooldown but never
            # silently drop a manual command. Record who/why for the audit log.
            operator = (user.get("email") or user.get("name") or "operator")
            result = eng.run_command(dev, action, params, operator=operator)
            return _send_json(self, result)

        # incident operations: persistent triage state over derived risk incidents
        if route.startswith("/api/incidents/") and route.endswith("/transition") and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "incident:write"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            incident_id = route[len("/api/incidents/"):-len("/transition")]
            # Materialize current derived incidents before applying the transition.
            _product_bundle(eng)
            body = _read_body(self)
            try:
                incident = eng.incidents.transition(
                    incident_id,
                    body.get("status", ""),
                    actor=user["id"],
                    assignee=body.get("assignee"),
                    note=body.get("note", ""),
                )
            except KeyError:
                return _send_json(self, {"error": "incidente no encontrado"}, 404)
            except ValueError as exc:
                return _send_json(self, {"error": str(exc)}, 400)
            return _send_json(self, {"ok": True, "incident": incident})

        # product intelligence
        if route in ("/api/risk", "/api/incidents", "/api/incidents/export", "/api/incidents/analytics",
                     "/api/policies", "/api/analytics",
                     "/api/compliance", "/api/report", "/api/cve", "/api/soar"):
            return self._product(route, eng, user, org, method, qs)

        # billing (mock)
        if route == "/api/plan" and method == "GET":
            o = _tenants.get(org)
            return _send_json(self, {"plan": o.plan, "limits": PLAN_LIMITS.get(o.plan),
                                     "plans": PLAN_LIMITS})
        if route == "/api/plan/upgrade" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "org:billing"):
                return _send_json(self, {"error": "sin permiso de facturación"}, 403)
            body = _read_body(self)
            new_plan = body.get("plan")
            if new_plan not in PLAN_LIMITS:
                return _send_json(self, {"error": "plan inválido"}, 400)
            o = _tenants.update_plan(org, new_plan)
            return _send_json(self, {"ok": True, "plan": o.plan, "limits": PLAN_LIMITS.get(o.plan)})

        # users
        if route == "/api/users" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "user:invite"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            members = [_auth.get(uid).to_public() for uid in
                        [u.id for u in _auth._users.values() if org in u.org_roles]]
            return _send_json(self, {"users": members})
        if route == "/api/users" and method == "POST":
            actor_role = user["org_roles"].get(org)
            if not AuthStore.can(actor_role, "user:invite"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            requested_role = body.get("role", "viewer")
            if requested_role not in ROLE_CAPS:
                return _send_json(self, {"error": "rol inválido"}, 400)
            # Privilege-escalation guard: only an owner may grant owner/admin.
            # Admins (who hold user:invite) can create operator/viewer only.
            if requested_role in ("owner", "admin") and actor_role != "owner":
                return _send_json(self, {"error": "solo el propietario puede asignar owner/admin"}, 403)
            pw = body.get("password") or ""
            temp = False
            if not pw or pw == "TempPass123":
                pw = os.urandom(6).hex()  # contraseña temporal aleatoria (no hardcodeada)
                temp = True
            try:
                u = _auth.create_user(body["email"], body.get("name", body["email"]),
                                      pw, org, requested_role)
                out = {"ok": True, "user": u.to_public()}
                if temp:
                    out["temp_password"] = pw
                return _send_json(self, out)
            except (ValueError, KeyError) as e:
                return _send_json(self, {"error": str(e)}, 400)


        # settings / credentials (strictly tenant-local)
        if route == "/api/settings/status" and method == "GET":
            tdir = _tenants.data_dir(org)
            st = core_secrets.status(tdir)
            st["mode"] = eng.config.get("mode")
            st["dry_run"] = eng.config.get("dry_run")
            st["masked_key"] = core_secrets.mask_key(tdir)
            runtime = _tenant_runtime(tdir)
            st["soar_webhook_hmac_configured"] = bool(runtime.get("soar_webhook_secret")
                                                      or os.environ.get("LUCIDFENCE_SOAR_WEBHOOK_SECRET"))
            st["soar_webhook_secret_masked"] = _masked_secret(runtime.get("soar_webhook_secret", ""))
            return _send_json(self, st)
        if route == "/api/settings" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            tdir = _tenants.data_dir(org)
            requested_key = body.get("api_key")
            if not (requested_key or "").strip() and core_secrets.read_key(tdir):
                requested_key = None
            res = core_secrets.save_credentials(tdir, requested_key, body.get("org_id"))
            if not res.get("ok"):
                return _send_json(self, {"ok": False, "error": res.get("error")}, 400)
            new_mode = body.get("mode") or ("live" if res.get("configured") else "simulation")
            if new_mode not in ("live", "simulation"):
                return _send_json(self, {"ok": False, "error": "modo inválido"}, 400)
            dry_run = bool(body.get("dry_run", eng.config.get("dry_run", True)))
            current_runtime = {}
            try:
                current_runtime = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
            except Exception:
                current_runtime = {}
            _save_tenant_integration(
                tdir, new_mode, dry_run,
                incident_webhook_url=current_runtime.get("incident_webhook_url", ""),
            )
            try:
                eng = reload_engine(org)
            except Exception as exc:
                return _send_json(self, {"ok": True, "mode": new_mode, "dry_run": dry_run,
                                        "configured": res.get("configured"),
                                        "warning": f"credenciales guardadas pero el engine no se recargó: {type(exc).__name__}: {exc}"})
            return _send_json(self, {"ok": True, "mode": eng.config.get("mode"),
                                     "dry_run": eng.config.get("dry_run"),
                                     "configured": res.get("configured")})
        if route == "/api/settings/test" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            tdir = _tenants.data_dir(org)
            key = (body.get("api_key") or "").strip() or core_secrets.read_key(tdir)
            if not key:
                return _send_json(self, {"ok": False, "error": "no hay token"}, 400)
            return _send_json(self, core_secrets.test_applivery_token(key))
        if route == "/api/settings/incident-webhook" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            url = (body.get("url") or "").strip()
            # SSRF guard: only https, and never internal/link-local targets.
            url = _safe_webhook_url(url)
            if (body.get("url") or "").strip() and not url:
                return _send_json(self, {"ok": False, "error": "URL no permitida (solo https, sin rangos privados)"}, 400)
            tdir = _tenants.data_dir(org)
            _save_tenant_integration(tdir, eng.config.get("mode", "simulation"),
                                     eng.config.get("dry_run", True),
                                     incident_webhook_url=url)
            # rebuild engine so the notifier picks up the new webhook
            try:
                reload_engine(org)
            except Exception:
                pass
            return _send_json(self, {"ok": True, "configured": bool(url)})
        if route == "/api/settings/soar-webhook-secret" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            secret = (body.get("secret") or "").strip()
            if secret and len(secret) < 16:
                return _send_json(self, {"ok": False, "error": "secret demasiado corto (mínimo 16 caracteres)"}, 400)
            tdir = _tenants.data_dir(org)
            runtime = _tenant_runtime(tdir)
            if secret:
                runtime["soar_webhook_secret"] = secret
            else:
                runtime.pop("soar_webhook_secret", None)
            tmp = tdir / "integration.json.tmp"
            tmp.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(tdir / "integration.json")
            os.chmod(tdir / "integration.json", 0o600)
            return _send_json(self, {"ok": True,
                                     "configured": bool(secret),
                                     "webhook_path": f"/api/soar/webhook/{org}",
                                     "signature": "HMAC-SHA256 over '<timestamp>.<raw_body>'"})

        # ---- Configurable threshold alerts (MDM/UEM alerting) -----------
        if route == "/api/alerts" and method == "GET":
            return _send_json(self, {
                "rules": eng.alerts.list_rules(),
                "firings": eng.alerts.recent_firings(100),
                "types": sorted(ALERT_TYPES),
                "labels": ALERT_TYPE_LABELS,
                "channels": sorted(CHANNELS),
            })
        if route == "/api/alerts" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            try:
                rule = eng.alerts.add_rule(body)
            except (ValueError, KeyError) as exc:
                return _send_json(self, {"error": f"regla invalida: {exc}"}, 400)
            return _send_json(self, {"ok": True, "rule": rule.to_dict()})
        if route.startswith("/api/alerts/") and route.endswith("/delete") and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            rid = route[len("/api/alerts/"):-len("/delete")]
            ok = eng.alerts.delete_rule(rid)
            return _send_json(self, {"ok": ok})
        if route == "/api/alerts/evaluate" and method == "POST":
            # on-demand evaluation of all rules against the live snapshot
            devs = [s.to_dict() for s in eng.store.snapshot().values()]
            fired = eng.alerts.evaluate(devs)
            return _send_json(self, {"ok": True, "firings": fired, "count": len(fired)})

        if route == "/api/atomicmail/status" and method == "GET":
            tdir = _tenants.data_dir(org)
            runtime = {}
            try:
                runtime = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
            except Exception:
                runtime = {}
            am = runtime.get("atomicmail") or {}
            # Never leak the api_key; only report configured + masked inbox.
            configured = bool(am.get("username") or am.get("api_key"))
            masked_key = ("*" * 8 + (am["api_key"][-4:] if am.get("api_key") else "")) if am.get("api_key") else ""
            out = {
                "configured": configured,
                "username": am.get("username", ""),
                "masked_api_key": masked_key,
                "incident_email_to": am.get("incident_email_to", ""),
                "digest_email_to": am.get("digest_email_to", ""),
                "ready": False,
                "inbox": None,
                "last_error": None,
            }
            mb = eng.mailbox
            if mb is not None:
                st = mb.status()
                out["ready"] = st.get("ready")
                out["inbox"] = st.get("inbox")
                out["last_error"] = st.get("last_error")
            return _send_json(self, out)
        if route == "/api/atomicmail/setup" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            tdir = _tenants.data_dir(org)
            am_cfg = {
                "username": (body.get("username") or "").strip(),
                "api_key": (body.get("api_key") or "").strip(),
                "incident_email_to": (body.get("incident_email_to") or "").strip(),
                "digest_email_to": (body.get("digest_email_to") or "").strip(),
            }
            if not (am_cfg["username"] or am_cfg["api_key"]):
                return _send_json(self, {"ok": False, "error": "requiere username o api_key"}, 400)
            _save_tenant_integration(
                tdir, eng.config.get("mode", "simulation"),
                eng.config.get("dry_run", True),
                incident_webhook_url=eng.config.get("incident_webhook_url", ""),
                atomicmail=am_cfg,
            )
            try:
                reload_engine(org)
            except Exception as exc:
                return _send_json(self, {"ok": True, "warning": f"config guardada pero engine no recargó: {exc}"})
            return _send_json(self, {"ok": True,
                                     "configured": bool(eng.mailbox is not None),
                                     "inbox": eng.mailbox.status().get("inbox") if eng.mailbox else None})
        if route == "/api/atomicmail/test" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            to = (body.get("to") or "").strip()
            mb = eng.mailbox
            if mb is None:
                return _send_json(self, {"ok": False, "error": "atomicmail no configurado"}, 400)
            if not to:
                return _send_json(self, {"ok": False, "error": "falta 'to'"}, 400)
            try:
                ok = mb.send(to=to, subject="[LucidFence] Test de Atomic Mail",
                             text="Este es un correo de prueba enviado por LucidFence vía Atomic Mail Agentic.")
                return _send_json(self, {"ok": ok, "inbox": mb._inbox_id,
                                         "last_error": mb.last_error})
            except Exception as exc:
                return _send_json(self, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        if route == "/api/atomicmail/digest" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self) or {}
            to = (body.get("to") or "").strip() or None
            ok = eng.send_digest(to=to)
            return _send_json(self, {"ok": ok})

        # ---- Whitelabel (DigitalPlat FreeDomain) -------------------------
        if route == "/api/whitelabel/suggest" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self) or {}
            domain = (body.get("domain") or "").strip()
            if not domain:
                return _send_json(self, {"ok": False, "error": "requiere domain"}, 400)
            from core.freedomain import suggest_dns_records
            try:
                sug = suggest_dns_records(
                    domain,
                    atomicmail_inbox=(eng.mailbox._inbox_id if eng.mailbox else "") or "",
                    dkim_selector=(body.get("dkim_selector") or "atomicmail"),
                    dashboard_target=(body.get("dashboard_target") or "").strip(),
                    receive_mail=bool(body.get("receive_mail", True)),
                )
                return _send_json(self, {"ok": True, "suggestion": sug})
            except ValueError as exc:
                return _send_json(self, {"ok": False, "error": str(exc)}, 400)
        if route == "/api/whitelabel/setup" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            domain = (body.get("domain") or "").strip()
            if not domain:
                return _send_json(self, {"ok": False, "error": "requiere domain"}, 400)
            tdir = _tenants.data_dir(org)
            wl_cfg = {
                "domain": domain,
                "dkim_selector": (body.get("dkim_selector") or "atomicmail").strip(),
                "dashboard_target": (body.get("dashboard_target") or "").strip(),
            }
            _save_tenant_integration(
                tdir, eng.config.get("mode", "simulation"),
                eng.config.get("dry_run", True),
                incident_webhook_url=eng.config.get("incident_webhook_url", ""),
                atomicmail=eng.config.get("atomicmail"),
                whitelabel=wl_cfg,
            )
            try:
                reload_engine(org)
            except Exception as exc:
                return _send_json(self, {"ok": True, "warning": f"config guardada pero engine no recargó: {exc}"})
            return _send_json(self, {"ok": True, "domain": domain,
                                     "sender": f"{eng.config.get('atomicmail', {}).get('username', '')}@{domain}"})
        if route == "/api/whitelabel/status" and method == "GET":
            tdir = _tenants.data_dir(org)
            runtime = {}
            try:
                runtime = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
            except Exception:
                runtime = {}
            wl = runtime.get("whitelabel") or {}
            out = {
                "configured": bool(wl.get("domain")),
                "domain": wl.get("domain", ""),
                "dkim_selector": wl.get("dkim_selector", "atomicmail"),
                "dashboard_target": wl.get("dashboard_target", ""),
                "last_validation": wl.get("last_validation"),
                "sender": (
                    f"{eng.config.get('atomicmail', {}).get('username', '')}@{wl['domain']}"
                    if wl.get("domain") else None
                ),
            }
            return _send_json(self, out)
        if route == "/api/whitelabel/validate" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self) or {}
            tdir = _tenants.data_dir(org)
            runtime = {}
            try:
                runtime = json.loads((tdir / "integration.json").read_text(encoding="utf-8"))
            except Exception:
                runtime = {}
            domain = (body.get("domain") or runtime.get("whitelabel", {}).get("domain") or "").strip()
            if not domain:
                return _send_json(self, {"ok": False, "error": "sin dominio configurado"}, 400)
            from core.freedomain import validate
            report = validate(domain, dkim_selector=(runtime.get("whitelabel", {}).get("dkim_selector") or "atomicmail"))
            # Persist last validation in the whitelabel config (non-secret).
            wl = runtime.get("whitelabel") or {}
            wl["last_validation"] = report
            runtime["whitelabel"] = wl
            try:
                tmp = tdir / "integration.json.tmp"
                tmp.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
                os.chmod(tmp, 0o600)
                tmp.replace(tdir / "integration.json")
                os.chmod(tdir / "integration.json", 0o600)
            except Exception:
                pass
            return _send_json(self, {"ok": True, "report": report})

        # ---- Bulk export / audit (CSV + print-ready HTML) ----------------
        if route == "/api/export" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "report:export"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            kind = (qs.get("kind", ["inventory"])[0]).lower()
            fmt = (qs.get("format", ["csv"])[0]).lower()
            from core import export as EXP
            if kind == "actions":
                actions = eng.store.recent_actions(5000)
                if fmt == "html":
                    return _send_html(self, EXP.export_inventory_html([], org,
                        {"total": len(actions)}))
                return _send_csv(self, "acciones_uem.csv", EXP.export_actions_csv(actions))
            if kind == "compliance":
                devs = [s.to_dict() for s in eng.store.snapshot().values()]
                if fmt == "pdf":
                    return _send_pdf(self, "reporte_conformidad.pdf",
                                     EXP.export_compliance_pdf(devs, org, _summary(devs)))
                if fmt == "html":
                    return _send_html(self, EXP.export_inventory_html(devs, org,
                        _summary(devs)))
                return _send_csv(self, "compliance.csv", EXP.export_compliance_csv(devs))
            # default: inventory
            devs = [s.to_dict() for s in eng.store.snapshot().values()]
            if fmt == "html":
                return _send_html(self, EXP.export_inventory_html(devs, org, _summary(devs)))
            return _send_csv(self, "inventario_uem.csv", EXP.export_inventory_csv(devs))

        # ---- Optional BYO AI provider (tenant-local, OpenAI-compatible) ----
        if route in ("/api/ai/providers", "/api/ai/settings") and method == "GET":
            ai_status = ai_provider.status(_tenants.data_dir(org))
            if route == "/api/ai/providers":
                provider_row = []
                if ai_status.get("configured"):
                    provider_row = [{"name": ai_status.get("provider"), "model": ai_status.get("model"), "available": True}]
                return _send_json(self, {"online": ai_status.get("configured", False),
                                         "providers": provider_row, "status": ai_status})
            return _send_json(self, ai_status)
        if route == "/api/ai/settings" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            result = ai_provider.save(_tenants.data_dir(org), _read_body(self))
            return _send_json(self, result, 200 if result.get("ok") else 400)
        if route == "/api/ai/test" and method == "POST":
            if not AuthStore.can(user["org_roles"].get(org), "engine:config"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            body = _read_body(self)
            # Test unsaved fields in a secure temporary directory; never mutate
            # tenant configuration until the operator presses Save.
            if any(k in body for k in ("base_url", "model", "api_key")):
                result = ai_provider.test_values(body)
            else:
                result = ai_provider.test_connection(_tenants.data_dir(org))
            return _send_json(self, result, 200 if result.get("ok") else 502)
        if route in ("/api/ai", "/api/ai/chat") and method == "POST":
            body = _read_body(self)
            messages = body.get("messages") if isinstance(body, dict) else None
            if not isinstance(messages, list) or not messages:
                return _send_json(self, {"ok": False, "error": "messages debe ser una lista no vacía"}, 400)
            result = ai_provider.chat(_tenants.data_dir(org), messages, body)
            if not result.get("ok"):
                return _send_json(self, result, int(result.get("status") or 502))
            cfg = ai_provider.status(_tenants.data_dir(org))
            return _send_json(self, {"ok": True, "text": result.get("text"),
                                     "provider": cfg.get("provider"), "model": cfg.get("model"),
                                     "response": result.get("response")})

        # ---- IA: borrador de respuesta de soporte (todo impulsado por IA) --
        if route == "/api/ai/support" and method == "POST":
            body = _read_body(self) or {}
            ticket = {
                "subject": (body.get("subject") or body.get("topic") or "").strip(),
                "body": (body.get("body") or body.get("message") or "").strip(),
            }
            if not ticket["subject"] and not ticket["body"]:
                return _send_json(self, {"ok": False, "error": "requiere subject/body"}, 400)
            try:
                from core import ai
                reply = ai.support_reply(ticket, dry=True)
            except Exception as exc:
                return _send_json(self, {"ok": False,
                    "error": f"motor IA no disponible: {exc}"}, 503)
            return _send_json(self, {
                "ok": True,
                "reply": reply,
                "moa_available": ai.available(),
            })

        self.send_error(404)

    # ---- auth handlers --------------------------------------------------
    def _signup(self):
        body = _read_body(self)
        email = (body.get("email") or "").strip()
        name = (body.get("name") or "").strip()
        password = body.get("password") or ""
        org_name = (body.get("org_name") or "").strip()
        if not email or not password or not org_name:
            return _send_json(self, {"error": "email, password y org_name son obligatorios"}, 400)
        if len(password) < 8:
            return _send_json(self, {"error": "la contraseña debe tener >= 8 caracteres"}, 400)
        if _auth.get_by_email(email):
            return _send_json(self, {"error": "el email ya está registrado"}, 400)
        # Signup ONLY creates a brand-new organisation (owner). Joining an
        # existing org by guessing its name is forbidden — membership in an
        # existing tenant must go through an authenticated invite
        # (POST /api/users), never through public signup. This closes the
        # "self-add as viewer to any org" escalation.
        from saas.tenant import slugify
        if _tenants.get_by_slug(slugify(org_name)):
            return _send_json(self, {"error": "el nombre de organización ya existe; pide una invitación al propietario"}, 409)
        plan = body.get("plan", "free")
        if plan not in PLAN_LIMITS:
            return _send_json(self, {"error": "plan inválido"}, 400)
        org = _tenants.create(org_name, owner_id="", plan=plan)
        role = "owner"
        user = _auth.create_user(email, name or email, password, org.id, role)
        org.owner_id = user.id
        _tenants._save()

        token = _auth.create_session(user.id)
        _set_cookie(self, COOKIE_SESSION, token)
        _set_cookie(self, COOKIE_ORG, org.id)
        welcome_email = _send_signup_welcome_email(email, name or email, org)
        _send_json(self, {"ok": True, "token": token, "user": user.to_public(),
                          "org": org.to_dict(), "plan": PLAN_LIMITS.get(org.plan),
                          "welcome_email": welcome_email})

    def _login(self):
        body = _read_body(self)
        user = _auth.authenticate(body.get("email", ""), body.get("password", ""))
        if not user:
            return _send_json(self, {"error": "credenciales inválidas"}, 401)
        token = _auth.create_session(user.id)
        _set_cookie(self, COOKIE_SESSION, token)
        first_org = next(iter(user.org_roles), None)
        if first_org:
            _set_cookie(self, COOKIE_ORG, first_org)
        _send_json(self, {"ok": True, "token": token, "user": user.to_public(),
                          "orgs": [o.to_dict() for o in _tenants.list_for_user(user.id)]})

    def _demo_login(self):
        """One-click onboarding, available only on a loopback-bound app."""
        bound_host = _bound_host(self)
        loopback_hosts = {"127.0.0.1", "localhost", "::1"}
        client_host = (self.client_address[0] if self.client_address else "").lower()
        if (bound_host not in loopback_hosts or client_host not in loopback_hosts):
            if os.environ.get("LUCIDFENCE_ALLOW_REMOTE_DEMO_LOGIN") != "1":
                return _send_json(self, {"error": "demo login solo disponible en loopback"}, 403)

        email = "ciso@acme.test"
        user = _auth.get_by_email(email)
        if user is None:
            demo_org = None
            for org in _tenants.all():
                if org.slug == "acme-logistics":
                    demo_org = org
                    break
            if demo_org is None:
                demo_org = _tenants.create("Acme Logistics (demo)", "usr_demo_seed", "free")
            user = _auth.create_user(email, "CISO Acme (demo)", "demo1234", demo_org.id, "owner")
            demo_org.owner_id = user.id
            _tenants._save()
        else:
            first_org = next(iter(user.org_roles), None)
            current_org = _tenants.get(first_org) if first_org else None
            if current_org is None:
                demo_org = _tenants.create("Acme Logistics (demo)", user.id, "free")
                _auth.add_org_role(user.id, demo_org.id, "owner")
                user = _auth.get(user.id) or user
            elif current_org.owner_id != user.id:
                current_org.owner_id = user.id
                _tenants._save()
        token = _auth.create_session(user.id)
        _set_cookie(self, COOKIE_SESSION, token)
        first_org = next(iter(user.org_roles), None)
        if first_org:
            _set_cookie(self, COOKIE_ORG, first_org)
        return _send_json(self, {"ok": True, "token": token, "user": user.to_public(),
                                 "orgs": [o.to_dict() for o in _tenants.list_for_user(user.id)],
                                 "message": "demo local lista"})

    def _logout(self):
        token = _cookie(self, COOKIE_SESSION)
        if token:
            _auth.destroy_session(token)
        _clear_cookie(self, COOKIE_SESSION)
        _clear_cookie(self, COOKIE_ORG)
        _send_json(self, {"ok": True})

    # ---- product intelligence ------------------------------------------
    def _product(self, route: str, eng: Engine, user: dict, org: str, method: str, qs: dict):
        product = _product_bundle(eng)
        if route == "/api/risk":
            return _send_json(self, {"risk": product.get("risk", []),
                                     "summary": product.get("summary", {})})
        if route == "/api/incidents":
            return _send_json(self, {"incidents": product.get("incidents", []),
                                     "summary": product.get("summary", {})})

        if route == "/api/incidents/export" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "incident:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            fmt = (qs.get("format", ["csv"])[0] or "csv").lower()
            rows = eng.incidents.list()
            if fmt == "csv":
                from core.incidents import to_csv
                csv_text = to_csv(rows)
                payload = csv_text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition",
                                 "attachment; filename=\"incidents.csv\"")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            return _send_json(self, {"incidents": rows, "summary": product.get("summary", {})})
        if route == "/api/incidents/analytics" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "incident:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            return _send_json(self, {"analytics": eng.incidents.analytics()})
        if route == "/api/cve" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "device:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            return _send_json(self, {"cve_summary": eng._cve_summary(),
                                     "devices": [
                                         {"device_id": s.device_id, "name": s.name,
                                          "apps": s.apps} for s in eng.store.snapshot().values()
                                     ]})
        if route == "/api/soar" and method == "GET":
            if not AuthStore.can(user["org_roles"].get(org), "device:read"):
                return _send_json(self, {"error": "sin permiso"}, 403)
            from core.soar import DEFAULT_PLAYBOOKS, evaluate_soar
            devs = list(eng.store.snapshot().values())
            soar_ctx = {"cycle": getattr(eng, "cycle_count", 0), "on_error": None}
            recent = []
            for d in devs:
                try:
                    execs = evaluate_soar(d.to_dict(), DEFAULT_PLAYBOOKS, soar_ctx)
                except Exception:
                    execs = []
                for ex in execs:
                    recent.append({
                        "playbook_id": ex.get("playbook_id"),
                        "name": ex.get("name"),
                        "device_id": d.device_id,
                        "device_name": d.name,
                        "severity": ex.get("severity"),
                        "actions": ex.get("actions"),
                    })
            return _send_json(self, {
                "playbooks": [{
                    "id": pb.id, "name": pb.name, "description": pb.description,
                    "enabled": pb.enabled, "severity_min": pb.severity_min,
                    "actions": pb.actions,
                } for pb in DEFAULT_PLAYBOOKS],
                "matched": recent,
                "devices_scanned": len(devs),
            })
        if route == "/api/policies":
            return _send_json(self, {"policies": product.get("policies", [])})
        if route == "/api/analytics":
            return _send_json(self, {"analytics": product.get("analytics", {}),
                                     "summary": product.get("summary", {})})
        if route == "/api/compliance":
            a = product.get("analytics", {})
            devs = list(eng.store.snapshot().values())
            non = sum(1 for s in devs if s.compliant is False)
            total = max(1, len(devs))
            return _send_json(self, {
                "compliance_percent": round((total - non) / total * 100),
                "series": a.get("compliance_series", []),
                "state_distribution": a.get("state_distribution", {}),
            })
        if route == "/api/report":
            return _send_json(self, {"report": product.get("report", {})})
        self.send_error(404)


def _start_parent_watchdog() -> None:
    """Exit a desktop backend if its launcher disappears abnormally."""
    raw = os.environ.get("LUCIDFENCE_PARENT_PID", "").strip()
    if not raw:
        return
    try:
        parent_pid = int(raw)
    except ValueError:
        raise RuntimeError("LUCIDFENCE_PARENT_PID must be numeric")
    if parent_pid <= 1:
        raise RuntimeError("LUCIDFENCE_PARENT_PID must identify a user process")

    def watch() -> None:
        while True:
            time.sleep(0.5)
            if os.getppid() != parent_pid:
                os._exit(0)
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                os._exit(0)
            except PermissionError:
                os._exit(0)

    threading.Thread(target=watch, name="desktop-parent-watchdog", daemon=True).start()


def main():
    _start_parent_watchdog()
    cfg = config_loader.load(CONFIG_FILE)
    global _SIMULATION
    _SIMULATION = (cfg.get("mode") == "simulation")
    host = os.environ.get("LUCIDFENCE_HOST") or cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(os.environ.get("LUCIDFENCE_PORT") or cfg.get("server", {}).get("port", 8765))
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] LucidFence local app running at http://{host}:{port}")
    print(f"  mode={cfg.get('mode')} dry_run={cfg.get('dry_run')}")
    print(f"  data={DATA_ROOT}")
    httpd = ThreadingHTTPServer((host, port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"[{ts}] Shutdown requested.")
        httpd.shutdown()


if __name__ == "__main__":
    main()
