"""Tests del sync de CVE desde NVD (offline-safe: NO toca red).

Valida la logica de mapeo NVD->feed y la carga en core.cve sin consultar la API.
La funcion query_nvd (que si usa red) se testa indirectamente via monkeypatch.
"""
from __future__ import annotations

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core import cve
from lucidfence.core.cve_feed_nvd import _nvd_to_feed_entry, _cvss_severity, load_nvd_feed_into_cve
from lucidfence.core.cve import classify_cve_severity


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


def test_classify_cve_severity_no_score_is_unknown():
    # A score-less entry (no verifiable CVSS, e.g. NVD keyword match without
    # CPE/version) must NOT be trusted to any critical/high bucket. This is the
    # root cause of CVE-2007-0045 (Acrobat 2007) being attributed to Chrome 120.
    check(classify_cve_severity("critical", 0.0) == "unknown", "score 0 critical -> unknown")
    check(classify_cve_severity("high", 0.0) == "unknown", "score 0 high -> unknown")
    check(classify_cve_severity("medium", 0.0) == "unknown", "score 0 medium -> unknown")
    check(classify_cve_severity(None, None) == "unknown", "None -> unknown")


def test_classify_cve_severity_real_score_derived():
    check(classify_cve_severity("medium", 9.8) == "critical", "score 9.8 -> critical (trust score, not string)")
    check(classify_cve_severity("low", 8.1) == "high", "score 8.1 -> high")
    check(classify_cve_severity("high", 6.1) == "medium", "score 6.1 -> medium")


def test_nvd_feed_entry_without_score_is_unknown():
    # keywordSearch hits (no CPE/version) carry no CVSS score -> severity unknown
    item = {
        "metrics": {},
        "cve": {"id": "CVE-2007-0045", "descriptions": [
            {"lang": "en", "value": "XSS in Adobe Acrobat Reader Plugin"}]},
    }
    e = _nvd_to_feed_entry(item)
    check(e["id"] == "CVE-2007-0045", "id preserved")
    check(e["severity"] == "unknown", "no-CVSS NVD entry -> unknown, never critical/high")
    check(e["score"] == 0.0, "score preserved as 0.0")


def test_load_feed_no_score_not_counted_critical_high():
    import tempfile
    from lucidfence.core import cve
    saved = cve.isolate_feed()
    feed = {"source": "NVD", "generated": "2026-08-24T00:00:00Z",
            "apps": {"testappxyz": [
                {"id": "CVE-2007-0045", "severity": "critical", "score": 0.0, "title": "t", "epss": 0.0},
                {"id": "CVE-2099-0001", "severity": "critical", "score": 9.9, "title": "r", "epss": 0.0},
            ]}}
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(feed).encode()); os.close(fd)
    try:
        n = load_nvd_feed_into_cve(path)
        check(n == 2, "loads 2 entries")
        apps = cve.enrich_apps([{"name": "testappxyz", "version": "1.0"}])
        a = apps[0]
        # The scored CVE-2099-0001 makes it critical; the unscored CVE-2007-0045
        # is normalized to unknown and must never bump the count on its own.
        check(a["max_cve_severity"] == "critical", "scored critical wins")
        summary = cve.device_cve_summary([a])
        check(summary["critical_cve_apps"] == 1, "critical count from real score only")
        check(summary["unknown_cve_apps"] == 0, "mixed app not double counted as unknown")
    finally:
        os.remove(path)
        cve.restore_feed(saved or {})


if __name__ == "__main__":
    for fn in (v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)):
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL CVE FEED TESTS PASS")
