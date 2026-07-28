"""Tenant-scoped autonomous company control plane for LucidFence.

This is a clean-room implementation inspired by the *operating pattern* of
continuous agent loops. It does not execute third-party code or copy prompts.
All persisted state is structured, bounded, atomic and local to one tenant.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = "lucidfence-autonomous-company/v1"
AUTONOMY_LEVELS = {"observe", "recommend", "simulate", "execute_safe"}
PRIORITIES = {"p0", "p1", "p2"}
SAFE_ACTIONS = {"simulate_geofence", "analyze_location_quality", "assess_compliance", "analyze_incidents", "optimize_routes"}
MEDIUM_ACTIONS = {"recommend_soar_playbook", "notify_owner", "request_device_lock"}
FORBIDDEN_ACTIONS = {"wipe", "factory_reset", "delete_device", "delete_tenant", "disable_audit"}
_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}

AGENTS = [
    {"id": "mission-control", "name": "Mission Control", "mission": "Priorizar objetivos y resolver bloqueos"},
    {"id": "field-intelligence", "name": "Field Intelligence", "mission": "Analizar movilidad, contexto y calidad de señal"},
    {"id": "geo-policy", "name": "Geo Policy", "mission": "Diseñar geovallas y rutas sin dañar operaciones"},
    {"id": "uem-operations", "name": "UEM Operations", "mission": "Traducir decisiones en acciones MDM reversibles"},
    {"id": "risk-compliance", "name": "Risk & Compliance", "mission": "Correlacionar riesgo, CVE y controles"},
    {"id": "product-value", "name": "Product Value", "mission": "Optimizar activación y valor para administradores"},
    {"id": "roi-finance", "name": "ROI & Finance", "mission": "Medir ahorro con supuestos explícitos"},
    {"id": "independent-critic", "name": "Independent Critic", "mission": "Pre-mortem y veto de decisiones peligrosas"},
    {"id": "qa-sre", "name": "QA & SRE", "mission": "Verificar evidencia, resiliencia y rollback"},
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _text(value: Any, field: str, limit: int) -> str:
    clean = " ".join(str(value or "").split()).strip()
    if not clean:
        raise ValueError(f"{field} is required")
    return clean[:limit]


class CompanyControlPlane:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.path = self.root / "autonomous_company.json"
        lock_key = str(self.path.resolve())
        with _LOCKS_GUARD:
            self._lock = _PATH_LOCKS.setdefault(lock_key, threading.RLock())
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _initial() -> dict:
        return {
            "schema": SCHEMA,
            "paused": False,
            "autonomy": "recommend",
            "cycle": 0,
            "agents": AGENTS,
            "goals": [],
            "tasks": [],
            "decisions": [],
            "metrics": {"active_goals": 0, "open_tasks": 0, "evidence_coverage": 100, "safety_blocks": 0},
            "updated_at": _now(),
        }

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("schema") == SCHEMA:
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return self._initial()

    def _save(self, state: dict) -> None:
        state["updated_at"] = _now()
        temp = self.path.with_suffix(f".tmp-{os.getpid()}-{threading.get_ident()}")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)
        os.chmod(self.path, 0o600)

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._load()))

    def create_goal(self, payload: dict, actor: str) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("goal must be an object")
        priority = str(payload.get("priority") or "p1").lower()
        autonomy = str(payload.get("autonomy") or "recommend").lower()
        if priority not in PRIORITIES:
            raise ValueError("invalid priority")
        if autonomy not in AUTONOMY_LEVELS:
            raise ValueError("invalid autonomy")
        metrics = payload.get("metrics") or []
        if not isinstance(metrics, list) or not metrics:
            raise ValueError("at least one measurable metric is required")
        normalized_metrics = []
        for metric in metrics[:10]:
            if not isinstance(metric, dict) or "target" not in metric:
                raise ValueError("each metric requires name and target")
            target = metric["target"]
            if not isinstance(target, (int, float)) or isinstance(target, bool):
                raise ValueError("metric target must be numeric")
            direction = str(metric.get("direction") or "max").lower()
            if direction not in {"max", "min", "equal"}:
                raise ValueError("metric direction must be max, min or equal")
            normalized_metrics.append({
                "name": _text(metric.get("name"), "metric.name", 80),
                "target": target,
                "direction": direction,
                "current": metric.get("current"),
            })
        goal = {
            "id": _id("goal"),
            "title": _text(payload.get("title"), "title", 160),
            "outcome": _text(payload.get("outcome"), "outcome", 500),
            "metrics": normalized_metrics,
            "constraints": [_text(item, "constraint", 240) for item in (payload.get("constraints") or [])[:20]],
            "priority": priority,
            "autonomy": autonomy,
            "status": "active",
            "created_by": _text(actor, "actor", 100),
            "created_at": _now(),
        }
        with self._lock:
            state = self._load()
            state["goals"].append(goal)
            state["metrics"]["active_goals"] = sum(1 for item in state["goals"] if item.get("status") == "active")
            self._save(state)
        return json.loads(json.dumps(goal))

    @staticmethod
    def _policy(action: str) -> tuple[str, int, str]:
        if action in FORBIDDEN_ACTIONS:
            return "forbidden", 999, "destructive actions are never autonomous"
        if action in SAFE_ACTIONS:
            return "low", 0, "read-only or simulation action"
        if action in MEDIUM_ACTIONS:
            return "medium", 1, "operational recommendation requires human approval"
        return "high", 2, "unknown or side-effecting action requires dual approval"

    def _build_task(self, payload: dict, actor: str, autonomy: str) -> dict:
        action = _text(payload.get("action"), "action", 80).lower().replace(" ", "_")
        risk, approvals, reason = self._policy(action)
        evidence = payload.get("evidence") or []
        acceptance = payload.get("acceptance") or []
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("task evidence is required")
        if not isinstance(acceptance, list) or not acceptance:
            raise ValueError("task acceptance criteria are required")
        status = "blocked" if risk == "forbidden" else "proposed"
        if risk == "low" and autonomy in {"simulate", "execute_safe"}:
            status = "executed"
        return {
            "id": _id("task"), "goal_id": payload.get("goal_id"),
            "title": _text(payload.get("title"), "title", 200),
            "agent_id": _text(payload.get("agent_id"), "agent_id", 80),
            "action": action, "risk": risk, "status": status,
            "requires_approvals": approvals, "approvals": [], "policy_reason": reason,
            "evidence": evidence[:20],
            "acceptance": [_text(item, "acceptance", 240) for item in acceptance[:20]],
            "result": {"mode": "simulation", "side_effects": False, "verified": True} if status == "executed" else None,
            "created_by": _text(actor, "actor", 100), "created_at": _now(),
        }

    def _refresh_metrics(self, state: dict) -> None:
        tasks = state.get("tasks", [])
        state["metrics"] = {
            "active_goals": sum(1 for item in state.get("goals", []) if item.get("status") == "active"),
            "open_tasks": sum(1 for item in tasks if item.get("status") in {"proposed", "approved"}),
            "executed_tasks": sum(1 for item in tasks if item.get("status") == "executed"),
            "evidence_coverage": round(100 * sum(1 for item in tasks if item.get("evidence")) / len(tasks)) if tasks else 100,
            "safety_blocks": sum(1 for item in tasks if item.get("status") == "blocked"),
        }

    @staticmethod
    def _measure_goal(goal: dict, context: dict) -> str:
        aliases = {
            "outside": "outside", "outside_devices": "outside",
            "unknown": "unknown", "unknown_devices": "unknown",
            "high_risk": "high_risk", "high_risk_devices": "high_risk",
            "critical_cve_apps": "critical_cve_apps", "open_incidents": "open_incidents",
            "compliance": "compliance_percent", "compliance_percent": "compliance_percent",
            "devices": "devices",
        }
        measured = []
        for metric in goal.get("metrics", []):
            key = aliases.get(str(metric.get("name") or "").lower())
            value = context.get(key) if key else None
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                measured.append(False); continue
            metric["current"] = value; metric["measured_at"] = _now()
            target = metric.get("target")
            direction = metric.get("direction")
            measured.append(value <= target if direction == "max" else value >= target if direction == "min" else value == target)
        if measured and all(measured):
            goal["status"] = "achieved"; goal["achieved_at"] = _now()
        return str(goal.get("status") or "active")

    def propose_task(self, payload: dict, actor: str) -> dict:
        with self._lock:
            state = self._load()
            task = self._build_task(payload, actor, state.get("autonomy", "recommend"))
            state["tasks"].append(task)
            state["tasks"] = state["tasks"][-500:]
            self._refresh_metrics(state); self._save(state)
            return json.loads(json.dumps(task))

    def pause(self, reason: str, actor: str) -> dict:
        with self._lock:
            state = self._load(); state["paused"] = True
            state["pause"] = {"reason": _text(reason, "reason", 240), "actor": _text(actor, "actor", 100), "ts": _now()}
            self._save(state); return {"paused": True, **state["pause"]}

    def resume(self, actor: str) -> dict:
        with self._lock:
            state = self._load(); state["paused"] = False
            state["resume"] = {"actor": _text(actor, "actor", 100), "ts": _now()}
            self._save(state); return {"paused": False, **state["resume"]}

    def approve_task(self, task_id: str, actor: str, reason: str) -> dict:
        with self._lock:
            state = self._load()
            task = next((item for item in state.get("tasks", []) if item.get("id") == task_id), None)
            if task is None:
                raise KeyError("task not found")
            if task.get("risk") == "forbidden" or task.get("status") == "blocked":
                raise ValueError("blocked task cannot be approved")
            if task.get("status") in {"executed", "rejected", "ready_for_handoff"}:
                if any(item.get("actor") == actor for item in task.get("approvals", [])):
                    raise ValueError("actor already approved this task")
                raise ValueError("task is not awaiting approval")
            if any(item.get("actor") == actor for item in task.get("approvals", [])):
                raise ValueError("actor already approved this task")
            task.setdefault("approvals", []).append({"actor": _text(actor, "actor", 100),
                                                      "reason": _text(reason, "reason", 240), "ts": _now()})
            if len(task["approvals"]) >= int(task.get("requires_approvals") or 0):
                task["status"] = "ready_for_handoff"
                task["result"] = {"mode": "human_handoff", "side_effects": False, "verified": False}
            self._refresh_metrics(state); self._save(state)
            return json.loads(json.dumps(task))

    def reject_task(self, task_id: str, actor: str, reason: str) -> dict:
        with self._lock:
            state = self._load()
            task = next((item for item in state.get("tasks", []) if item.get("id") == task_id), None)
            if task is None:
                raise KeyError("task not found")
            if task.get("status") in {"executed", "rejected"}:
                raise ValueError("task cannot be rejected")
            task["status"] = "rejected"
            task["rejection"] = {"actor": _text(actor, "actor", 100), "reason": _text(reason, "reason", 240), "ts": _now()}
            self._refresh_metrics(state); self._save(state)
            return json.loads(json.dumps(task))

    def run_cycle(self, context: dict, actor: str) -> dict:
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        with self._lock:
            state = self._load()
            if state.get("paused"):
                raise RuntimeError("autonomous company is paused")
            goals = [item for item in state.get("goals", []) if item.get("status") == "active"]
            if not goals:
                raise RuntimeError("an active measurable goal is required")
            order = {"p0": 0, "p1": 1, "p2": 2}
            goal = sorted(goals, key=lambda item: (order.get(item.get("priority"), 9), item.get("created_at", "")))[0]
            state["cycle"] = int(state.get("cycle", 0)) + 1
            squad = ["mission-control", "qa-sre"]
            specs: list[dict] = []
            def add(agent: str, title: str, action: str, source: str, value: Any, acceptance: str):
                if agent not in squad: squad.append(agent)
                specs.append({"goal_id": goal["id"], "agent_id": agent, "title": title, "action": action,
                              "evidence": [{"source": source, "value": value, "observed_at": _now()}],
                              "acceptance": [acceptance]})
            if int(context.get("outside") or 0) > 0:
                add("geo-policy", "Simular ajuste de geovalla para dispositivos outside", "simulate_geofence", "fleet.outside", int(context["outside"]), "Reducir outside proyectado sin aumentar falsos positivos")
            if int(context.get("unknown") or 0) > 0:
                add("field-intelligence", "Analizar dispositivos sin ubicación fiable", "analyze_location_quality", "fleet.unknown", int(context["unknown"]), "Explicar cobertura y causa de cada señal desconocida")
            if int(context.get("critical_cve_apps") or 0) > 0:
                add("risk-compliance", "Recomendar playbook SOAR para CVE críticas", "recommend_soar_playbook", "cve.critical_apps", int(context["critical_cve_apps"]), "Propuesta reversible con dispositivos afectados y rollback")
            compliance_value = context.get("compliance_percent")
            compliance = float(compliance_value) if isinstance(compliance_value, (int, float, str)) and str(compliance_value).strip() else 100.0
            if compliance < 90:
                add("risk-compliance", "Evaluar brecha de compliance geográfico", "assess_compliance", "compliance.percent", context.get("compliance_percent"), "Mapear brecha a evidencia CIS/ISO sin afirmar certificación")
            if int(context.get("open_incidents") or 0) > 0:
                add("uem-operations", "Analizar incidentes geográficos abiertos", "analyze_incidents", "incidents.open", int(context["open_incidents"]), "Priorizar incidentes por riesgo y reversibilidad")
            if not specs:
                add("product-value", "Buscar optimización segura de rutas", "optimize_routes", "fleet.devices", int(context.get("devices") or 0), "Producir una mejora medible o registrar no-op con evidencia")
            existing = {(item.get("goal_id"), item.get("action")) for item in state.get("tasks", []) if item.get("status") in {"proposed", "approved"}}
            created = []
            for spec in specs:
                if (spec["goal_id"], spec["action"]) in existing:
                    continue
                task = self._build_task(spec, actor, goal.get("autonomy", "recommend"))
                state["tasks"].append(task); created.append(task)
            goal_status = self._measure_goal(goal, context)
            decision = {"id": _id("decision"), "cycle": state["cycle"], "goal_id": goal["id"],
                        "squad": squad, "summary": f"Created {len(created)} evidence-backed tasks",
                        "context": {key: context.get(key) for key in ("devices", "outside", "unknown", "high_risk", "critical_cve_apps", "open_incidents", "compliance_percent")},
                        "actor": _text(actor, "actor", 100), "ts": _now()}
            state["decisions"].append(decision); state["decisions"] = state["decisions"][-200:]
            state["tasks"] = state["tasks"][-500:]
            self._refresh_metrics(state); self._save(state)
            return {"cycle": state["cycle"], "goal_id": goal["id"], "squad": squad,
                    "created_tasks": json.loads(json.dumps(created)), "decision": decision,
                    "metrics": state["metrics"], "goal_status": goal_status}
