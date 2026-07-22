from __future__ import annotations

import tempfile
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.autonomous_company import CompanyControlPlane


def test_company_goal_is_structured_persistent_and_measurable():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        company = CompanyControlPlane(root)
        goal = company.create_goal({
            "title": "Reducir salidas no autorizadas",
            "outcome": "Bajar eventos outside sin bloquear trabajo legítimo",
            "metrics": [{"name": "outside_events", "target": 2, "direction": "max"}],
            "constraints": ["No ejecutar wipe", "Todo cambio requiere evidencia"],
            "priority": "p0",
            "autonomy": "simulate",
        }, actor="owner-1")
        assert goal["id"].startswith("goal_")
        assert goal["status"] == "active" and goal["priority"] == "p0"
        assert goal["metrics"][0]["target"] == 2
        assert CompanyControlPlane(root).snapshot()["goals"][0]["id"] == goal["id"]
        assert (root / "autonomous_company.json").stat().st_mode & 0o777 == 0o600


def test_company_cycle_forms_geo_squad_and_ships_only_safe_simulations():
    with tempfile.TemporaryDirectory() as td:
        company = CompanyControlPlane(Path(td))
        goal = company.create_goal({
            "title": "Reducir exposición fuera de zona",
            "outcome": "Proponer una respuesta medible sin actuar sobre dispositivos",
            "metrics": [{"name": "outside_devices", "target": 0}],
            "priority": "p0", "autonomy": "simulate",
        }, actor="owner")
        result = company.run_cycle({
            "devices": 12, "outside": 3, "unknown": 2,
            "high_risk": 1, "critical_cve_apps": 4,
            "open_incidents": 2, "compliance_percent": 75,
        }, actor="operator")
        assert result["cycle"] == 1 and result["goal_id"] == goal["id"]
        assert {"mission-control", "geo-policy", "risk-compliance", "qa-sre"} <= set(result["squad"])
        assert len(result["created_tasks"]) >= 4
        safe = [task for task in result["created_tasks"] if task["action"] in {"analyze_location_quality", "simulate_geofence", "assess_compliance"}]
        assert safe and all(task["status"] == "executed" for task in safe)
        cve = next(task for task in result["created_tasks"] if task["action"] == "recommend_soar_playbook")
        assert cve["status"] == "proposed" and cve["requires_approvals"] == 1
        assert all(task.get("evidence") and task.get("acceptance") for task in result["created_tasks"])


def test_company_policy_blocks_destructive_autonomy_and_pause_is_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        company = CompanyControlPlane(Path(td))
        blocked = company.propose_task({
            "title": "Borrar dispositivo", "action": "wipe", "agent_id": "uem-operations",
            "goal_id": None, "evidence": [{"source": "operator", "value": "requested"}],
            "acceptance": ["device wiped"],
        }, actor="owner")
        assert blocked["risk"] == "forbidden" and blocked["status"] == "blocked"
        assert blocked["policy_reason"] == "destructive actions are never autonomous"
        company.pause("maintenance", actor="owner")
        try:
            company.run_cycle({"devices": 1}, actor="operator")
            raise AssertionError("paused company ran a cycle")
        except RuntimeError as exc:
            assert "paused" in str(exc)


def test_company_medium_risk_needs_distinct_human_approval_and_stays_handoff_only():
    with tempfile.TemporaryDirectory() as td:
        company = CompanyControlPlane(Path(td))
        task = company.propose_task({
            "title": "Solicitar bloqueo reversible", "action": "request_device_lock",
            "agent_id": "uem-operations", "goal_id": None,
            "evidence": [{"source": "risk", "value": 92}],
            "acceptance": ["Operador confirma dispositivo y rollback"],
        }, actor="operator")
        assert task["status"] == "proposed" and task["requires_approvals"] == 1
        approved = company.approve_task(task["id"], actor="owner", reason="Incidente validado")
        assert approved["status"] == "ready_for_handoff"
        assert approved["result"] == {"mode": "human_handoff", "side_effects": False, "verified": False}
        try:
            company.approve_task(task["id"], actor="owner", reason="duplicado")
            raise AssertionError("duplicate approval accepted")
        except ValueError as exc:
            assert "already approved" in str(exc)


def test_company_writes_are_serialized_across_control_plane_instances():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        def create(index: int):
            return CompanyControlPlane(root).create_goal({
                "title": f"Goal {index}", "outcome": "Preserve every concurrent write",
                "metrics": [{"name": "outside", "target": index}],
            }, actor=f"actor-{index}")
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(create, range(30)))
        state = CompanyControlPlane(root).snapshot()
        assert len(state["goals"]) == 30
        assert len({goal["id"] for goal in state["goals"]}) == 30


def test_company_closes_goal_only_when_live_metric_meets_target():
    with tempfile.TemporaryDirectory() as td:
        company = CompanyControlPlane(Path(td))
        goal = company.create_goal({
            "title": "Mantener outside bajo control", "outcome": "Máximo dos dispositivos fuera",
            "metrics": [{"name": "outside_devices", "target": 2, "direction": "max"}],
            "autonomy": "simulate",
        }, actor="owner")
        result = company.run_cycle({"devices": 10, "outside": 2, "compliance_percent": 100}, actor="operator")
        updated = next(item for item in company.snapshot()["goals"] if item["id"] == goal["id"])
        assert result["goal_status"] == "achieved"
        assert updated["status"] == "achieved"
        assert updated["metrics"][0]["current"] == 2
        assert updated["achieved_at"]
