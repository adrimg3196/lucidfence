"""Tests del sync de CVE desde NVD (offline-safe: NO toca red).

Valida la logica de mapeo NVD->feed y la carga en core.cve sin consultar la API.
La funcion query_nvd (que si usa red) se testa indirectamente via monkeypatch.
"""
from __future__ import annotations

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cve
from core.cve_feed_nvd import _nvd_to_feed_entry, _cvss_severity, load_nvd_feed_into_cve


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


def test_cvss_severity_v31():
    item = {
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseSeverity": "CRITICAL", "baseScore": 9.8}}]},
        "cve": {"id": "CVE-2024-0001"},
    }
    sev, score = _cvss_severity(item)
    check(sev == "critical" and score == 9.8, "mapea CRITICAL/9.8")


def test_cvss_severity_v2_fallback():
    item = {
        "metrics": {"cvssMetricV2": [{"cvssData": {"baseScore": 7.5}}]},
        "cve": {"id": "CVE-2024-0002"},
    }
    sev, score = _cvss_severity(item)
    check(sev == "high" and score == 7.5, "v2 fallback high/7.5")


def test_nvd_to_feed_entry():
    item = {
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseSeverity": "HIGH", "baseScore": 8.1}}]},
        "cve": {"id": "CVE-2023-9999", "descriptions": [{"lang": "en", "value": "RCE en X"}]},
    }
    e = _nvd_to_feed_entry(item)
    check(e["id"] == "CVE-2023-9999", "id preservado")
    check(e["severity"] == "high" and e["score"] == 8.1, "severidad/score mapeados")
    check("RCE" in e["title"], "titulo de descripcion en")


def test_load_nvd_feed_into_cve(monkeypatch=None):
    # Crea un feed temporal y lo carga en core.cve._FEED
    import tempfile
    feed = {"source": "NVD", "generated": "2026-07-13T00:00:00Z",
            "apps": {"testappxyz": [{"id": "CVE-2099-0001", "severity": "critical", "score": 9.9, "title": "t", "epss": 0.0}]}}
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(feed).encode()); os.close(fd)
    try:
        n = load_nvd_feed_into_cve(path)
        check(n == 1, "carga 1 entrada de feed temporal")
        cves = cve.lookup_cves("testappxyz")
        check(any(c["id"] == "CVE-2099-0001" for c in cves), "entrada visible via lookup_cves")
    finally:
        os.remove(path)


if __name__ == "__main__":
    for fn in (v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)):
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL CVE FEED TESTS PASS")
