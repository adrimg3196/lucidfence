"""Live CVE feed sync from NVD (network) — nutre la base de CVEs periodicamente.

El modulo core/cve.py es offline (CVE_DB curado + load_feed()). Este script
consulta la API publica de NVD (services.nvd.nist.gov) para REFRESCAR/EXTENDER
la base con CVEs reales y vigentes de las apps de la flota, y escribe un feed
JSON que core/cve.load_feed() consume al arrancar.

- Respeta "100% local" en el sentido de que el dashboard no depende de red en
  tiempo de ejecucion; el feed se precarga y se renueva por un cron local.
- Usa solo stdlib (urllib) + requests opcional. Sin dependencias nuevas.
- NUNCA hace raise: si la red falla, devuelve 0 y deja el feed anterior.

Uso:
    from core.cve_feed_nvd import sync_nvd_feed
    n = sync_nvd_feed()   # consulta NVD, escribe data/cve_feed_nvd.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Optional

# Permite ejecutar el script directamente (python3 core/cve_feed_nvd.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "data", "cve_feed_nvd.json")
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
# Apps a consultar (las del CVE_DB + las mas comunes de flota frontline).
DEFAULT_APPS = [
    "google chrome", "mozilla firefox", "whatsapp", "zoom", "microsoft teams",
    "slack", "microsoft outlook", "winrar", "openvpn", "adobe acrobat reader",
    "filezilla", "google android", "apple ios", "microsoft windows",
]


def _http_get_json(url: str, params: dict, timeout: int = 30) -> Optional[dict]:
    import urllib.parse
    import urllib.request
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "geofence-uem-cve-sync/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _cvss_severity(cve_item: dict) -> tuple[str, float]:
    """Extrae (severidad, score) del primer CVSSv3/v2 disponible."""
    conf = cve_item.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for m in conf.get(key, []):
            data = m.get("cvssData") or {}
            sev = (data.get("baseSeverity") or "").lower()
            score = data.get("baseScore") or 0.0
            if sev:
                return sev, float(score)
            if score:
                # derivar severidad de score
                if score >= 9.0:
                    return "critical", float(score)
                if score >= 7.0:
                    return "high", float(score)
                if score >= 4.0:
                    return "medium", float(score)
                return "low", float(score)
    return "medium", 0.0


def _nvd_to_feed_entry(cve_item: dict) -> dict:
    cve = cve_item.get("cve", {})
    cid = cve.get("id", "CVE-UNKNOWN")
    desc = ""
    for d in cve.get("descriptions", []):
        if d.get("lang") == "en":
            desc = d.get("value", "")
            break
    sev, score = _cvss_severity(cve_item)
    return {
        "id": cid,
        "severity": sev,
        "score": score,
        "title": desc[:140],
        "epss": 0.0,  # NVD no trae EPSS; el CVE_DB curado lo tiene cuando aplica
    }


def query_nvd(app: str, results_per_page: int = 5, timeout: int = 30) -> list[dict]:
    """Consulta NVD por keywordSearch=app y devuelve entradas de feed."""
    data = _http_get_json(NVD_URL, {
        "keywordSearch": app,
        "resultsPerPage": results_per_page,
    }, timeout=timeout)
    if not data:
        return []
    out = []
    seen = set()
    for item in data.get("vulnerabilities", []):
        entry = _nvd_to_feed_entry(item)
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        out.append(entry)
    return out


def sync_nvd_feed(apps: Optional[list[str]] = None, out_path: str = DEFAULT_OUT,
                  per_app: int = 5, timeout: int = 30, sleep_s: float = 0.4) -> int:
    """Consulta NVD para cada app, escribe un feed JSON y devuelve entradas totales.

    El feed se escribe aunque alguna app falle (best-effort). Si la red falla
    por completo, no sobrescribe un feed existente (deja el ultimo bueno).
    """
    apps = apps or DEFAULT_APPS
    feed: dict[str, list[dict]] = {}
    total = 0
    for app in apps:
        try:
            entries = query_nvd(app, results_per_page=per_app, timeout=timeout)
        except Exception:
            entries = []
        if entries:
            key = app.strip().lower()
            feed[key] = entries
            total += len(entries)
        time.sleep(sleep_s)  # cortesia con la API publica (rate limit)
    if total == 0:
        # Red caida o sin resultados: no machacar feed previo.
        if os.path.exists(out_path):
            return 0
    payload = {
        "source": "NVD",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "apps": feed,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, out_path)
    return total


def load_nvd_feed_into_cve(out_path: str = DEFAULT_OUT) -> int:
    """Carga el feed NVD en core.cve (mergea sobre CVE_DB). Devuelve entradas."""
    if not os.path.exists(out_path):
        return 0
    try:
        data = json.load(open(out_path, encoding="utf-8"))
    except Exception:
        return 0
    from core import cve
    added = 0
    for app, entries in (data.get("apps") or {}).items():
        for e in entries:
            # load_feed espera formato plano interno
            cve._FEED.setdefault(app, [])
            # evita duplicados por id
            if any(x.get("id") == e.get("id") for x in cve._FEED[app]):
                continue
            cve._FEED[app].append({
                "id": e.get("id"),
                "severity": e.get("severity", "medium"),
                "score": e.get("score", 0),
                "title": e.get("title", ""),
                "epss": e.get("epss", 0.0),
            })
            added += 1
    return added


if __name__ == "__main__":
    n = sync_nvd_feed()
    print(f"NVD sync: {n} entries written to {DEFAULT_OUT}")
    m = load_nvd_feed_into_cve()
    print(f"Loaded into core.cve._FEED: {m} new entries")
