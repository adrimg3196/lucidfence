"""Simulador what-if de políticas — el "terraform plan" del geofencing.

Antes de activar una policy (sobre todo si dispara acciones destructivas:
lock/wipe/clear_passcode), el operador necesita saber qué habría hecho contra
el histórico real de su flota: "esta regla habría disparado 14 locks la semana
pasada, 3 de ellos sobre reports que hoy sabemos que eran jitter".

replay_policy() reconstruye cada punto del trail persistido (trails.jsonl),
lo re-evalúa con el Risk Engine y comprueba si la policy CANDIDATA habría
disparado. Todo local, solo lectura: jamás ejecuta acciones.

Límite honesto del modelo: el trail guarda posición + fence_state por punto;
las señales no espaciales (compliance, apps/CVE, postura) se toman del estado
ACTUAL del dispositivo — "la postura de hoy sobre la posición de ayer". Para
políticas puramente geoespaciales el replay es exacto; para las que mezclan
posture es una aproximación y el resultado lo declara (`approximation`).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from lucidfence.core.geo import Point
from lucidfence.core.policies import Policy, RiskEngine

# Acciones que justifican el simulador: las que no se pueden deshacer.
DESTRUCTIVE_ACTIONS = {"wipe", "lock", "clear_passcode", "reboot", "retire"}

MAX_POINTS = 20_000  # techo duro de puntos por replay (protege al server local)
MAX_SAMPLE = 50      # disparos de ejemplo devueltos con detalle


def load_trail_points(trails_path: str | Path, limit: int = 5000) -> list[dict]:
    """Últimos `limit` puntos del trail global, en orden cronológico de archivo.

    Fail-soft: líneas corruptas se saltan; archivo ausente → lista vacía.
    """
    path = Path(trails_path)
    if not path.exists():
        return []
    points: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("device_id") and d.get("lat") is not None and d.get("lng") is not None:
            points.append(d)
    return points[-min(limit, MAX_POINTS):]


def _hour_of(ts: str) -> Optional[int]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
    except Exception:
        return None


def replay_policy(
    policy: dict,
    trail_points: list[dict],
    *,
    fences: Optional[list] = None,
    device_states: Optional[dict[str, dict]] = None,
    risk_engine: Optional[RiskEngine] = None,
    risk_ctx: Optional[dict] = None,
) -> dict:
    """Evalúa una policy candidata contra el histórico de trails.

    - `policy`: dict con el mismo esquema que policies.json (id/name/when/actions/...).
    - `trail_points`: salida de load_trail_points().
    - `fences`: si se pasa, el fence_state se RECALCULA contra las geocercas
      actuales (what-if de policy + geocercas nuevas a la vez); si no, se usa
      el fence_state grabado en el trail (fidelidad histórica).
    - `device_states`: dict device_id -> estado actual (para señales no
      espaciales); opcional.

    Devuelve un resumen serializable con el detalle de los disparos. Nunca
    ejecuta acciones: esto es un plan, no un apply.
    """
    candidate = Policy(
        id=str(policy.get("id") or "candidata"),
        name=str(policy.get("name") or "policy candidata"),
        description=str(policy.get("description") or ""),
        when=list(policy.get("when") or []),
        actions=list(policy.get("actions") or []),
        enabled=True,  # el replay evalúa siempre, aunque llegue disabled
        severity=str(policy.get("severity") or "medium"),
    )
    engine = risk_engine or RiskEngine()
    states = device_states or {}
    ctx_base = dict(risk_ctx or {})

    recompute = fences is not None
    fires: list[dict] = []
    fires_by_device: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    evaluated = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None

    for point in trail_points[:MAX_POINTS]:
        device_id = point["device_id"]
        ts = point.get("ts") or ""
        first_ts = first_ts or ts
        last_ts = ts or last_ts

        if recompute:
            fence_state, fence_id = "outside", None
            try:
                loc = Point(float(point["lat"]), float(point["lng"]))
                for f in fences:
                    if f.contains(loc):
                        fence_state, fence_id = "inside", f.id
                        break
            except Exception:
                fence_state, fence_id = "unknown", None
        else:
            fence_state = point.get("fence_state") or "unknown"
            fence_id = point.get("fence_id")

        device = dict(states.get(device_id) or {})
        device.update({
            "device_id": device_id,
            "lat": point.get("lat"), "lng": point.get("lng"),
            "fence_state": fence_state,
            "fence_id": fence_id if fence_id is not None else device.get("fence_id"),
        })
        ctx = dict(ctx_base)
        hour = _hour_of(ts)
        if hour is not None:
            ctx["hour"] = hour

        risk = engine.evaluate(device, fence_state, ctx)
        evaluated += 1
        matched = engine.match_policies([candidate], risk, device, fence_state)
        if not matched:
            continue
        fires_by_device[device_id] = fires_by_device.get(device_id, 0) + 1
        for act in candidate.actions:
            name = act.get("action") or "?"
            action_counts[name] = action_counts.get(name, 0) + 1
        if len(fires) < MAX_SAMPLE:
            fires.append({
                "device_id": device_id,
                "ts": ts,
                "fence_state": fence_state,
                "risk_score": risk["risk_score"],
                "severity": risk["severity"],
                "reasons": risk["reasons"],
            })

    destructive = sorted(a for a in action_counts if a in DESTRUCTIVE_ACTIONS)
    # Señales no espaciales presentes en el `when` → el replay es aproximado
    # (usa el estado actual del dispositivo, no el histórico).
    non_spatial = [c.get("field") for c in candidate.when
                   if c.get("field") and not str(c.get("field")).startswith(
                       ("fence_state", "risk_score", "severity"))]
    return {
        "policy_id": candidate.id,
        "policy_name": candidate.name,
        "points_evaluated": evaluated,
        "period": {"from": first_ts, "to": last_ts},
        "fence_state_source": "recomputed" if recompute else "recorded",
        "fires_total": sum(fires_by_device.values()),
        "devices_affected": len(fires_by_device),
        "fires_by_device": fires_by_device,
        "actions_that_would_run": action_counts,
        "destructive_actions": destructive,
        "approximation": {
            "exact": not non_spatial,
            "non_spatial_conditions": non_spatial,
            "note": ("Replay exacto: la policy solo usa señales espaciales." if not non_spatial else
                     "Aproximación: las condiciones no espaciales usan el estado ACTUAL "
                     "del dispositivo sobre posiciones históricas."),
        },
        "sample_fires": fires,
        "dry_run": True,  # siempre: el replay jamás ejecuta acciones
    }
