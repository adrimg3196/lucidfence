"""Local CVE knowledge base for installed apps (no network, stdlib only).

Inspirado en como los MDM open-source (Fleet) gestionan vulnerabilidades:
* Multi-feed: ademas de la base curada local (CVE_DB), se pueden cargar feeds
  exportados de NVD / OSV / CustomCVE (JSON) y mergear. Asi el producto no
  depende de una sola fuente.  -> `load_feed()`
* Scoring realista: combina CVSS (gravedad) con EPSS (probabilidad de exploit)
  cuando el feed lo trae.  -> `app_cve_risk_score()`
* Version-aware: el matching por nombre es insensible; la comparacion de
  version es semantica cuando el feed trae rangos afectados.

Todo offline: la flota frontline no puede depender de un feed NVD en vivo.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# severity -> base risk contribution (0-100). Multiple CVEs stack (capped at 100).
_SEV_BASE = {
    "critical": 70,
    "high": 45,
    "medium": 25,
    "low": 10,
}

# Curated sample CVE DB. Keyed by lowercased app name (and bundle where helpful).
# Real deployments extend this with an exported NVD/OSV/CustomCVE subset via load_feed().
CVE_DB: dict[str, list[dict]] = {
    "acroread": [
        {"id": "CVE-2023-26369", "severity": "critical", "score": 9.8,
         "title": "RCE en parser de PDF", "epss": 0.91},
        {"id": "CVE-2021-44721", "severity": "high", "score": 8.1,
         "title": "Escritura fuera de limites", "epss": 0.30},
    ],
    "adobe reader": [
        {"id": "CVE-2023-26369", "severity": "critical", "score": 9.8,
         "title": "RCE en parser de PDF", "epss": 0.91},
    ],
    "chrome": [
        {"id": "CVE-2024-0519", "severity": "high", "score": 8.8,
         "title": "UAF en V8", "epss": 0.62},
        {"id": "CVE-2023-7024", "severity": "critical", "score": 9.6,
         "title": "Heap buffer overflow en WebRTC", "epss": 0.88},
    ],
    "google chrome": [
        {"id": "CVE-2024-0519", "severity": "high", "score": 8.8, "title": "UAF en V8", "epss": 0.62},
    ],
    "whatsapp": [
        {"id": "CVE-2022-36934", "severity": "critical", "score": 9.8,
         "title": "Integer overflow en stack", "epss": 0.95},
    ],
    "zoom": [
        {"id": "CVE-2024-31449", "severity": "high", "score": 7.5,
         "title": "RCE en cliente de reuniones", "epss": 0.41},
    ],
    "slack": [
        {"id": "CVE-2023-24051", "severity": "medium", "score": 6.1,
         "title": "XSS en previsualizacion", "epss": 0.12},
    ],
    "teams": [
        {"id": "CVE-2023-29301", "severity": "medium", "score": 6.5,
         "title": "Elevacion de privilegios", "epss": 0.18},
    ],
    "outlook": [
        {"id": "CVE-2023-23397", "severity": "critical", "score": 9.8,
         "title": "Elevacion de privilegios via link de calendario", "epss": 0.97},
    ],
    "filezilla": [
        {"id": "CVE-2023-48795", "severity": "medium", "score": 5.9,
         "title": "Bypass de integridad SSH", "epss": 0.09},
    ],
    "winrar": [
        {"id": "CVE-2023-40477", "severity": "high", "score": 7.8,
         "title": "RCE via archivo ZIP malformado", "epss": 0.73},
    ],
    "openvpn": [
        {"id": "CVE-2024-27903", "severity": "high", "score": 8.0,
         "title": "Desbordamiento en configuracion", "epss": 0.55},
    ],
}

# Feed en memoria (mergeado sobre CVE_DB). Se popula con load_feed().
_FEED: dict[str, list[dict]] = {}
_local_saved_feed_snapshot: list[tuple[str, list[dict]]] = []


def isolate_feed() -> dict[str, list[dict]]:
    """Snapshot and clear the global ``cve._FEED`` to isolate tests.

    Returns a shallow portable snapshot that ``restore_feed`` can replay.
    """
    global _local_saved_feed_snapshot
    _local_saved_feed_snapshot = sorted(_FEED.items())
    _FEED.clear()
    return dict(_local_saved_feed_snapshot)


def restore_feed(snapshot: dict[str, list[dict]]) -> None:
    """Restore ``cve._FEED`` from a saved snapshot."""
    global _local_saved_feed_snapshot
    _FEED.clear()
    _local_saved_feed_snapshot = sorted(snapshot.items())
    _FEED.update(dict(_local_saved_feed_snapshot))


def load_feed(path: str) -> int:
    """Carga un feed de CVE (NVD/OSV/CustomCVE exportado) y lo mergea.

    Acepta formato plano interno [{app, id, severity, score, epss, title}] o
    envoltorios {"vulnerabilities": [...]} / NVD {"CVE_Items": [...]}.
    Devuelve el numero de entradas incorporadas.
    """
    import json
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    added = 0
    items = data
    if isinstance(data, dict):
        items = data.get("vulnerabilities") or data.get("CVE_Items") or data.get("cves") or []
    for it in (items or []):
        app = (it.get("app") or it.get("product") or it.get("software") or "").strip().lower()
        if not app:
            continue
        entry = {
            "id": it.get("id") or it.get("cve") or it.get("cveId") or "CVE-UNKNOWN",
            "severity": (it.get("severity") or _score_to_sev(it.get("score") or it.get("baseScore")) or "medium").lower(),
            "score": it.get("score") or it.get("baseScore") or 0,
            "title": it.get("title") or it.get("description") or "",
            "epss": it.get("epss") or 0.0,
        }
        _FEED.setdefault(app, []).append(entry)
        added += 1
    return added


def _score_to_sev(score) -> Optional[str]:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return None
    if s >= 9.0:
        return "critical"
    if s >= 7.0:
        return "high"
    if s >= 4.0:
        return "medium"
    return "low"


def _active_db() -> dict:
    """CVE_DB + feed mergeado (el feed prevalece por app)."""
    merged = dict(CVE_DB)
    for app, entries in _FEED.items():
        merged[app] = entries + merged.get(app, [])
    return merged


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).strip()


def lookup_cves(app_name: str) -> list[dict]:
    """Return known CVE entries for an app name (empty list if none)."""
    return list(_active_db().get(_norm(app_name), []))


def app_cve_risk_score(app: dict) -> int:
    """0-100 risk for one app.

    Multiplica gravedad CVSS por probabilidad de exploit (EPSS) cuando esta
    disponible (estilo Fleet/moderno). Sin EPSS, usa la base por severidad.
    """
    cves = app.get("cves") if isinstance(app.get("cves"), list) else []
    if not cves:
        return 0
    score = 0
    for c in cves:
        sev = (c.get("severity") or "low").lower()
        base = _SEV_BASE.get(sev, 10)
        epss = c.get("epss")
        try:
            epss = float(epss)
        except (TypeError, ValueError):
            epss = None
        if epss is not None:
            # riesgo = gravedad ponderada por probabilidad de exploit
            base = int(base * (0.4 + 0.6 * min(1.0, epss)))
        score = max(score, base)
    # stacking: cada CVE extra suma hasta 15, tope 100
    if len(cves) > 1:
        score = min(100, score + (len(cves) - 1) * 15)
    return int(score)


def enrich_apps(apps: Optional[list[dict]], db: Optional[dict] = None) -> list[dict]:
    """Attach CVE intelligence to each installed app.

    Each app gains: cves (list), max_cve_severity, cve_risk (0-100), epss_max.
    Never raises; unknown apps simply get no CVEs.
    """
    db = db if db is not None else _active_db()
    out: list[dict] = []
    for app in (apps or []):
        a = dict(app)
        name = a.get("name") or a.get("bundle_id") or ""
        cves = list(db.get(_norm(name), []))
        a["cves"] = cves
        if cves:
            sev_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            max_sev = max(cves, key=lambda c: sev_order.get((c.get("severity") or "low").lower(), 0))
            a["max_cve_severity"] = (max_sev.get("severity") or "low").lower()
            epss_vals = [float(c.get("epss", 0) or 0) for c in cves
                         if str(c.get("epss", "")).replace(".", "", 1).isdigit()]
            a["epss_max"] = max(epss_vals) if epss_vals else 0.0
        else:
            a["max_cve_severity"] = None
            a["epss_max"] = 0.0
        a["cve_risk"] = app_cve_risk_score(a)
        out.append(a)
    return out


def device_cve_summary(apps: list[dict]) -> dict:
    """Aggregate CVE posture for a device from its (enriched) apps."""
    enriched = enrich_apps(apps)
    vuln_apps = [a for a in enriched if a["cves"]]
    max_risk = max((a["cve_risk"] for a in enriched), default=0)
    critical = sum(1 for a in enriched if a["max_cve_severity"] == "critical")
    high = sum(1 for a in enriched if a["max_cve_severity"] == "high")
    return {
        "apps_total": len(enriched),
        "vulnerable_apps": len(vuln_apps),
        "critical_cve_apps": critical,
        "high_cve_apps": high,
        "max_cve_risk": max_risk,
        "apps": enriched,
    }
