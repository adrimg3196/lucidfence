"""TDD: CVE enrichment for installed apps + SOAR playbook engine.

Two product capabilities for frontline UEM security operations:
  1. core/cve.py  -> local CVE knowledge base (no network) that enriches each
     installed app with known CVEs, max severity and a 0-100 risk score.
  2. core/soar.py -> rule-based playbooks (condition -> UEM actions) the engine
     evaluates per device each cycle, producing orchestrated response actions.

Both are pure/TDD-friendly and never raise on missing data.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cve import enrich_apps, app_cve_risk_score, CVE_DB  # noqa: E402
from core.soar import evaluate_soar, SOARPlaybook, DEFAULT_PLAYBOOKS  # noqa: E402


def test_cve_enrich_flags_vulnerable_app():
    apps = [
        {"name": "Acroread", "version": "1.2.3"},  # known CVE in DB
        {"name": "Notepad", "version": "9.9"},      # unknown -> no CVE
    ]
    out = enrich_apps(apps)
    assert len(out) == 2
    vuln = out[0]
    assert vuln["cves"], vuln
    assert vuln["max_cve_severity"] in ("critical", "high", "medium", "low")
    assert vuln["cve_risk"] > 0
    safe = out[1]
    assert safe["cves"] == []
    assert safe["cve_risk"] == 0


def test_cve_risk_score_scales_with_severity():
    low = app_cve_risk_score({"name": "x", "cves": [{"id": "CVE-1", "severity": "low"}]})
    crit = app_cve_risk_score({"name": "x", "cves": [{"id": "CVE-2", "severity": "critical"}]})
    assert crit > low > 0


def test_soar_fires_when_app_has_critical_cve():
    pb = SOARPlaybook(
        id="cve-crit",
        name="CVE crítico en app instalada",
        condition=lambda d, ctx: any(
            a.get("max_cve_severity") == "critical" for a in (d.get("apps") or [])
        ),
        actions=[{"action": "notify", "params": {"channel": "soc"}}],
    )
    dev = {"device_id": "d1", "apps": [{"name": "Acroread", "version": "1.2.3",
            "max_cve_severity": "critical", "cves": [{"id": "CVE-X"}], "cve_risk": 90}]}
    fired = evaluate_soar(dev, [pb], {})
    assert len(fired) == 1
    assert fired[0]["playbook_id"] == "cve-crit"
    assert fired[0]["actions"][0]["action"] == "notify"


def test_soar_does_not_fire_without_match():
    pb = SOARPlaybook(
        id="cve-crit",
        name="x",
        condition=lambda d, ctx: any(
            a.get("max_cve_severity") == "critical" for a in (d.get("apps") or [])
        ),
        actions=[{"action": "notify", "params": {}}],
    )
    dev = {"device_id": "d1", "apps": [{"name": "Safe", "max_cve_severity": "low", "cves": []}]}
    assert evaluate_soar(dev, [pb], {}) == []


def test_soar_executes_action_in_run_once():
    """A matched SOAR playbook must produce a real UEM action during the cycle."""
    import tempfile, types
    from core.engine import Engine
    from helpers import make_temp_engine
    eng = make_temp_engine()
    # capture executed actions
    executed = []
    eng.adapter = types.SimpleNamespace(
        execute=lambda dev, action, params, dry_run=False: (
            executed.append({"device_id": getattr(dev, "device_id", "?"), "action": action, "params": params}),
            {"ok": True, "action": action, "dry_run": dry_run},
        )[-1]
    )
    eng.routes = []
    from core.location_source import LocationReport
    rep = LocationReport(
        device_id="d1", name="Riesgo1", platform="android",
        lat=40.0, lng=-3.0, status="active", compliant=False,
        apps=[{"name": "Acroread", "version": "1.2.3", "max_cve_severity": "critical",
               "cves": [{"id": "CVE-X", "severity": "critical"}], "cve_risk": 90}],
        location_source="simulation",
    )
    eng.source = type("S", (), {"fetch": lambda self: [rep]})()
    eng.run_once()
    # SOAR playbook soar-cve-critical should have flagged the app; and since the
    # device is also non-compliant+outside, soar-rooted-outside should LOCK it.
    actions = [e["action"] for e in executed]
    assert "lock" in actions, f"esperado lock por SOAR, ejecutadas={actions}"
    # the lock action must be tagged as SOAR-originated in the engine log
    soar_actions = [a for a in eng._cycle_actions if a.get("soar")]
    assert soar_actions, "ninguna acción marcada como SOAR"
