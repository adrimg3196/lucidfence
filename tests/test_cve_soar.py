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

from lucidfence.core.cve import enrich_apps, app_cve_risk_score, CVE_DB  # noqa: E402
from lucidfence.core.soar import evaluate_soar, SOARPlaybook, DEFAULT_PLAYBOOKS  # noqa: E402
from lucidfence.core.engine import Engine  # noqa: E402
from lucidfence.core.location_source import LocationReport  # noqa: E402
from helpers import make_temp_engine  # noqa: E402


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
    """A matched SOAR playbook drives live execution AND human-gating.

    Non-destructive actions (notify/locate) are executed live against the UEM.
    Destructive actions (lock) are NOT auto-executed: per the reviewed design
    (diseño §5 / REQ §5) they are emitted as a `soar_handoff` event that waits
    for manual approval in the console — never executed autonomously.
    """
    import tempfile, types
    from lucidfence.core.engine import Engine
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
    from lucidfence.core.location_source import LocationReport
    rep = LocationReport(
        device_id="d1", name="Riesgo1", platform="android",
        lat=40.0, lng=-3.0, status="active", compliant=False,
        apps=[{"name": "Acroread", "version": "1.2.3", "max_cve_severity": "critical",
               "cves": [{"id": "CVE-X", "severity": "critical"}], "cve_risk": 90}],
        location_source="simulation",
    )
    eng.source = type("S", (), {"fetch": lambda self: [rep]})()
    eng.run_once()
    # Non-destructive SOAR actions still execute live (soar-cve-critical notify,
    # soar-cve-outside locate/notify, soar-rooted-outside notify).
    actions = [e["action"] for e in executed]
    assert "notify" in actions, f"esperado notify por SOAR, ejecutadas={actions}"
    assert "locate" in actions, f"esperado locate por SOAR, ejecutadas={actions}"
    # Destructive action (lock) is human-gated: it must NOT be auto-executed, but
    # logged as a soar_handoff event awaiting manual approval.
    assert "lock" not in actions, f"lock NO debe auto-ejecutarse (human-gate), ejecutadas={actions}"
    handoffs = [e for e in eng.store.recent_events() if e.get("kind") == "soar_handoff"]
    assert handoffs, "ningún soar_handoff registrado para la acción destructiva"
    assert any(h.get("action") == "lock" and h.get("human_gate") for h in handoffs), \
        "el lock destructivo debe quedar como handoff human-gate"
    # the matching logic still tags actions as SOAR-originated in the engine log
    soar_actions = [a for a in eng._cycle_actions if a.get("soar")]
    assert soar_actions, "ninguna acción marcada como SOAR"

    # CONTRATO human-gate (issue #208): el handoff destructivo debe ser su
    # PROPIA entrada en la superficie por ciclo del SOC, con la acción REAL
    # pendiente, y NO mutar la acción previa (locate/notify) poniéndole
    # soar_handoff. Un handoff NO cuenta como ejecutado (executed/ok=False).
    lock_handoff_records = [
        a for a in eng._cycle_actions
        if a.get("action") == "lock" and a.get("soar_handoff")
    ]
    assert lock_handoff_records, \
        "el lock destructivo debe aparecer como su propio registro en _cycle_actions"
    for r in lock_handoff_records:
        assert r.get("executed") is False, f"handoff no debe contar como ejecutado: {r}"
        assert r.get("ok") is False, f"handoff no debe contar como ok: {r}"
        assert r.get("human_gate") is True, f"handoff debe llevar human_gate: {r}"
    # Ninguna acción NO destructiva debe quedar etiquetada como el handoff.
    mislabeled = [
        a.get("action") for a in eng._cycle_actions
        if a.get("soar_handoff") and a.get("action") not in eng.DESTRUCTIVE_ACTIONS
    ]
    assert not mislabeled, \
        f"acciones no destructivas etiquetadas como handoff (bug #208): {mislabeled}"


def test_soar_destructive_handoff_as_first_cycle_action():
    """Regresión (issue #208, segundo defecto): si la acción destructiva es la
    PRIMERA (y única) del ciclo — el caso más grave: CVE crítico + fuera de
    perímetro sin notify/locate previo — el human-gate NO debe perderse en
    silencio. Antes del fix, la guarda `if self._cycle_actions:` descartaba el
    marcado cuando _cycle_actions estaba vacío, dejando cero rastro del handoff
    en la superficie por ciclo del SOC.
    """
    import types
    eng = make_temp_engine()
    eng.adapter = types.SimpleNamespace(
        execute=lambda dev, action, params, dry_run=False: {
            "ok": True, "action": action, "dry_run": dry_run,
        }
    )
    eng.routes = []

    # Playbook que dispara DIRECTO a lock, sin acciones no destructivas previas.
    lock_only_pb = SOARPlaybook(
        id="soar-lock-only", name="lock-only",
        condition={"field": "compliant", "op": "eq", "value": False},
        actions=[{"action": "lock", "params": {"reason": "noncompliant"}}],
    )

    class _LockOnlyStore:
        def all_playbooks(self):
            return [lock_only_pb]

    eng.soar_store = _LockOnlyStore()
    rep = LocationReport(
        device_id="d2", name="R2", platform="android",
        lat=40.0, lng=-3.0, status="active", compliant=False,
        apps=[], location_source="simulation",
    )
    eng.source = type("S", (), {"fetch": lambda self: [rep]})()
    eng.run_once()

    # El handoff debe aparecer como entrada propia en _cycle_actions, aunque sea
    # la única acción del ciclo (antes del fix quedaba _cycle_actions vacío).
    assert eng._cycle_actions, "el handoff destructivo no debe perderse del ciclo"
    lock_handoff = [
        a for a in eng._cycle_actions
        if a.get("action") == "lock" and a.get("soar_handoff")
    ]
    assert lock_handoff, \
        "lock (primera acción del ciclo) debe registrarse como handoff propio"
    assert lock_handoff[0].get("executed") is False, "handoff no ejecutado"
    assert lock_handoff[0].get("human_gate") is True, "handoff lleva human_gate"
    # Y el evento de auditoría también está presente (no se pierde el trail).
    audit = [e for e in eng.store.recent_events() if e.get("kind") == "soar_handoff"]
    assert audit and audit[0].get("action") == "lock", \
        "el evento soar_handoff de auditoría debe existir para el lock"
