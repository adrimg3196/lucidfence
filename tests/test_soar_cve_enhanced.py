"""Regression: SOAR declarativo + CVE multi-feed/EPSS (mejoras inspiradas en
cloud-custodian / Fleet). Run via: python3 tests/run_tests.py
"""
import os
import sys
import json
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from core.soar import (
    DEFAULT_PLAYBOOKS, evaluate_soar, validate_playbooks,
    compile_condition, SOARPlaybook,
)
from core.cve import enrich_apps, load_feed, device_cve_summary, CVE_DB


def test_soar_declarative_and_or_not():
    # AND compuesto dispara solo cuando TODAS las condiciones cumplen
    d = {"apps": [{"max_cve_severity": "critical"}], "fence_state": "outside"}
    cond = {"all": [
        {"field": "apps[].max_cve_severity", "op": "eq", "value": "critical"},
        {"field": "fence_state", "op": "eq", "value": "outside"},
    ]}
    m, f = compile_condition(cond)(d)
    assert m, f"AND deberia matchear: {f}"
    # cambia fence_state -> no matchea
    d2 = dict(d); d2["fence_state"] = "inside"
    assert not compile_condition(cond)(d2)[0], "AND no debe matchear si una falla"
    # OR: basta una
    orc = {"any": [{"field": "fence_state", "op": "eq", "value": "nowhere"},
                   {"field": "fence_state", "op": "eq", "value": "inside"}]}
    assert compile_condition(orc)(d2)[0], "OR deberia matchear"
    # NOT
    notc = {"not": {"field": "fence_state", "op": "eq", "value": "outside"}}
    assert compile_condition(notc)(d2)[0] and not compile_condition(notc)(d)[0]
    print("  PASS test_soar_declarative_and_or_not")


def test_soar_operators():
    d = {"risk": 80, "name": "Movil*01", "tags": ["x", "vip"]}
    assert compile_condition({"field": "risk", "op": "gt", "value": 50})(d)[0]
    assert compile_condition({"field": "name", "op": "glob", "value": "Movil*" })(d)[0]
    assert compile_condition({"field": "tags", "op": "contains", "value": "vip"})(d)[0]
    assert compile_condition({"field": "risk", "op": "in", "value": [10, 80]})(d)[0]
    print("  PASS test_soar_operators")


def test_soar_validation_rejects_bad_playbook():
    bad = SOARPlaybook(id="", name="", condition={"field": "x", "op": "bogus", "value": 1}, actions=[])
    errs = bad.validate()
    assert errs, "playbook mal formado debe reportar errores"
    # los por defecto son validos
    assert validate_playbooks(DEFAULT_PLAYBOOKS) == [], "DEFAULT_PLAYBOOKS deben validar"
    print("  PASS test_soar_validation_rejects_bad_playbook")


def test_soar_epss_playbook_fires():
    apps = enrich_apps([{"name": "Outlook", "version": "16"}])  # EPSS 0.97
    dev = {"device_id": "d", "apps": apps}
    res = evaluate_soar(dev, DEFAULT_PLAYBOOKS, {"on_error": None})
    ids = {r["playbook_id"] for r in res}
    assert "soar-cve-epss-high" in ids, f"EPSS playbook debio disparar: {ids}"
    print("  PASS test_soar_epss_playbook_fires")


def test_cve_epss_weighted_risk():
    # mismo severity, distinto EPSS -> distinto riesgo
    low = {"name": "x", "cves": [{"id": "C1", "severity": "critical", "epss": 0.01}]}
    high = {"name": "x", "cves": [{"id": "C1", "severity": "critical", "epss": 0.97}]}
    from core.cve import app_cve_risk_score
    assert app_cve_risk_score(high) > app_cve_risk_score(low), "EPSS debe elevar riesgo"
    print("  PASS test_cve_epss_weighted_risk")


def test_cve_multifeed_load():
    feed = {"vulnerabilities": [
        {"app": "Signal", "id": "CVE-2025-1111", "severity": "high", "score": 8.0, "epss": 0.4,
         "title": "RCE en Signal"},
    ]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(feed, fh)
        path = fh.name
    try:
        n = load_feed(path)
        assert n == 1, f"feed deberia cargar 1: {n}"
        apps = enrich_apps([{"name": "Signal", "version": "6"}])
        assert apps[0]["cves"], "Signal debe tener CVE del feed"
        assert apps[0]["max_cve_severity"] == "high"
    finally:
        os.unlink(path)
    print("  PASS test_cve_multifeed_load")


if __name__ == "__main__":
    test_soar_declarative_and_or_not()
    test_soar_operators()
    test_soar_validation_rejects_bad_playbook()
    test_soar_epss_playbook_fires()
    test_cve_epss_weighted_risk()
    test_cve_multifeed_load()
    print("\nSOAR/CVE enhancement tests passed")
