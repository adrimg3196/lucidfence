"""DigitalPlat FreeDomain helper for LucidFence whitelabel / sovereign email.

DigitalPlat FreeDomain (https://github.com/DigitalPlatDev/FreeDomain) gives every
LucidFence tenant a FREE domain (e.g. ``acme-fence.dpdns.org``, ``.us.kg``,
``.qzz.io`` …). Paired with Atomic Mail (the email channel we already integrated)
this closes the loop for a 100% sovereign SaaS communications stack:

  * LucidFence sends alerts/incidents/digest FROM ``<tenant>.<domain>`` instead
    of a generic ``@atomicmail.ai`` address, with SPF/DKIM aligned to that
    domain for real deliverability.
  * The dashboard can be served under the tenant's own domain for demos/pilots.
  * Whitelabel: each tenant presents its own domain, not a LucidFence subdomain.

FreeDomain itself has NO programmatic API in its repo (registration is via the
web dashboard ``dash.domain.digitalplat.org``); this module is therefore a
CONFIGURATIVE helper, not a code dependency:

  1. ``suggest_dns_records(domain, atomicmail_inbox, selector)`` -> the exact
     DNS records (TXT SPF, DKIM CNAME/TXT, MX, dashboard CNAME) the operator
     should paste into Cloudflare / their DNS provider.
  2. ``validate(domain)`` -> live DNS checks (via DNS-over-HTTPS, stdlib only,
     no external dep) that the delegation, SPF and DKIM records are present and
     reference the expected targets. Never raises; returns a structured report.

Security: all network I/O is best-effort and time-boxed; a failed lookup never
crashes the caller. We only READ public DNS; we never write to any provider.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Optional

_DOH_ENDPOINT = "https://dns.google/resolve"
# DigitalPlat name servers (delegation target shown in their panel). Operators
# may instead use Cloudflare's NS after transferring management there.
_DIGITALPLAT_NS = [
    "ns1.digitalplat.org",
    "ns2.digitalplat.org",
]
# Atomic Mail's DKIM public key is published per-inbox; the operator copies the
# exact TXT value from their Atomic Mail dashboard. We only template the shape.
_ATOMICMAIL_SPF = "v=spf1 include:_spf.atomicmail.ai ~all"


def suggest_dns_records(
    domain: str,
    *,
    atomicmail_inbox: str = "",
    dkim_selector: str = "atomicmail",
    dashboard_target: str = "",
    receive_mail: bool = True,
) -> dict:
    """Return the DNS records a tenant should create for sovereign email.

    ``domain`` is the FreeDomain domain (e.g. ``acme-fence.dpdns.org``).
    ``atomicmail_inbox`` is the tenant's ``@atomicmail.ai`` address (used only
    to show the operator where the DKIM key lives; not required for the shape).
    ``dashboard_target`` is the IP/CNAME where the LucidFence dashboard is
    reachable (optional; for serving the UI under the tenant domain).
    """
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain:
        raise ValueError("domain requerido")
    records = []

    # 1) SPF — authorize Atomic Mail to send on behalf of this domain.
    records.append({
        "type": "TXT",
        "name": domain,
        "value": _ATOMICMAIL_SPF,
        "ttl": 3600,
        "purpose": "SPF: autoriza a Atomic Mail a enviar correo por este dominio.",
    })

    # 2) DKIM — CNAME al selector de Atomic Mail (operador pega la clave real
    #    desde el dashboard de Atomic Mail en el campo de destino).
    records.append({
        "type": "CNAME",
        "name": f"{dkim_selector}._domainkey.{domain}",
        "value": f"{dkim_selector}._domainkey.atomicmail.ai",
        "ttl": 3600,
        "purpose": "DKIM: firma saliente. El destino resuelve a la clave publica de Atomic Mail.",
    })

    # 3) DMARC — recomendado para deliverability/anti-spoofing.
    records.append({
        "type": "TXT",
        "name": f"_dmarc.{domain}",
        "value": "v=DMARC1; p=quarantine; rua=mailto:dmarc@" + domain,
        "ttl": 3600,
        "purpose": "DMARC: politica anti-spoofing y reportes.",
    })

    # 4) MX — solo si el tenant quiere RECIBIR respuestas en este dominio.
    if receive_mail:
        records.append({
            "type": "MX",
            "name": domain,
            "value": "10 in1.atomicmail.ai",
            "ttl": 3600,
            "purpose": "MX: recibe respuestas en este dominio via Atomic Mail (opcional).",
        })

    # 5) Dashboard (opcional) — sirve el Command Center bajo el dominio propio.
    if dashboard_target:
        records.append({
            "type": "CNAME" if not _looks_like_ip(dashboard_target) else "A",
            "name": domain,
            "value": dashboard_target,
            "ttl": 3600,
            "purpose": "Dashboard: sirve LucidFence Command Center bajo tu dominio.",
        })

    return {
        "domain": domain,
        "nameservers_note": (
            "Delega el dominio en Cloudflare (recomendado) o usa los NS de "
            "DigitalPlat: " + ", ".join(_DIGITALPLAT_NS) + ". Luego crea los "
            "registros de abajo en tu panel DNS."
        ),
        "atomicmail_inbox": atomicmail_inbox,
        "records": records,
    }


def _looks_like_ip(v: str) -> bool:
    return bool(v) and all(p.isdigit() or p == "." for p in v) and v.count(".") == 3


def _doh_query(name: str, rtype: str, timeout: float = 8.0) -> list[str]:
    """DNS-over-HTTPS lookup via Google's public resolver (stdlib only).

    Returns the list of string values (TXT chunks joined, or target strings)
    for the record, or [] on any failure. Never raises.
    """
    url = f"{_DOH_ENDPOINT}?name={urllib.parse.quote(name)}&type={rtype}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        out: list[str] = []
        for ans in data.get("Answer", []) or []:
            out.append(str(ans.get("data", "")).strip('"'))
        return out
    except Exception:
        return []


def validate(domain: str, *, dkim_selector: str = "atomicmail",
             timeout: float = 8.0) -> dict:
    """Live-check the DNS setup for sovereign email on ``domain``.

    Returns a structured report:
      { domain, checked_at, ns_delegated, spf, dkim, dmarc, overall }
    ``overall`` is "ok" | "partial" | "missing". Never raises.
    """
    domain = (domain or "").strip().lower().rstrip(".")
    report = {
        "domain": domain,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ns_delegated": None,
        "spf": None,
        "dkim": None,
        "dmarc": None,
        "overall": "missing",
        "notes": [],
    }
    if not domain:
        report["notes"].append("dominio vacio")
        return report

    # NS delegation: the domain should have NS records (delegated somewhere).
    ns = _doh_query(domain, "NS", timeout)
    report["ns_delegated"] = bool(ns)
    if not ns:
        report["notes"].append("sin registros NS visibles (dominio no delegado?)")

    # SPF
    spf = _doh_query(domain, "TXT", timeout)
    spf_hit = [v for v in spf if v.startswith("v=spf1")]
    report["spf"] = bool(spf_hit)
    if spf_hit:
        report["notes"].append("SPF: " + spf_hit[0][:80])

    # DKIM (CNAME should resolve to atomicmail selector)
    dkim_name = f"{dkim_selector}._domainkey.{domain}"
    dkim = _doh_query(dkim_name, "CNAME", timeout)
    report["dkim"] = bool(dkim)
    if dkim:
        report["notes"].append("DKIM CNAME -> " + dkim[0][:80])

    # DMARC
    dmarc = _doh_query(f"_dmarc.{domain}", "TXT", timeout)
    dmarc_hit = [v for v in dmarc if v.startswith("v=DMARC1")]
    report["dmarc"] = bool(dmarc_hit)

    passed = sum(1 for k in ("ns_delegated", "spf", "dkim", "dmarc") if report[k])
    report["overall"] = "ok" if passed == 4 else ("partial" if passed >= 1 else "missing")
    return report


def is_freedomain_suffix(domain: str) -> bool:
    """True if the domain uses a known DigitalPlat FreeDomain extension."""
    d = (domain or "").strip().lower().rstrip(".")
    return any(d.endswith(s) for s in (
        ".dpdns.org", ".us.kg", ".xx.kg", ".qzz.io", ".qd.je",
    ))
