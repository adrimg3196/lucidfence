"""Product intelligence layer for the local LucidFence dashboard.

This module is deliberately read-only and fully local. It derives product-grade
risk, incidents, policies, analytics and an executive report from the existing
Engine.status() payload. It never reads .env, never imports credential helpers,
never performs network calls, and never exposes secrets.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import math
from statistics import median
from typing import Any


MAX_HISTORY_POINTS = 4096
MAX_TRAIL_POINTS = 20000
ALLOWED_CLOCK_SKEW_SECONDS = 300


def _safe_nonnegative_int(value: Any) -> tuple[int, bool]:
    """Return a non-negative integer and whether sanitization was required."""
    try:
        if isinstance(value, bool):
            raise ValueError
        parsed = int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0, True
    if parsed < 0:
        return 0, True
    return parsed, False


def _valid_coordinate(lat_value: Any, lng_value: Any) -> bool:
    try:
        if isinstance(lat_value, bool) or isinstance(lng_value, bool):
            return False
        lat, lng = float(lat_value), float(lng_value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180


def build_product(status: dict[str, Any], eng: Any = None) -> dict[str, Any]:
    """Build derived product intelligence from an Engine.status() dict.

    If `eng` (the live Engine) is provided, the authoritative risk score uses the
    Geospatial Risk & Policy Engine (composite signals: geofence + device health
    + external signals like shift/zone-risk). Otherwise it falls back to the
    local compute_risk heuristic.
    """
    devices = list(status.get("devices") or [])
    events = enrich_events(status.get("recent_events") or [])
    actions = enrich_actions(status.get("recent_actions") or [])
    fences = list(status.get("fences") or [])
    stats = dict(status.get("stats") or {})
    raw_history = status.get("stats_history") or []
    history = raw_history if isinstance(raw_history, list) else []
    raw_trails = status.get("trails") or []
    bounded_trails: deque[dict[str, Any]] = deque(maxlen=MAX_TRAIL_POINTS)
    if isinstance(raw_trails, dict):
        for device_id, rows in raw_trails.items():
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict):
                    bounded_trails.append({**row, "device_id": str(row.get("device_id") or device_id)})
    elif isinstance(raw_trails, list):
        bounded_trails.extend(row for row in raw_trails if isinstance(row, dict))
    trails = list(bounded_trails)

    if eng is not None and getattr(eng, "risk", None) is not None:
        risk = _risk_from_engine(eng, devices)
    else:
        risk = compute_risk(devices, events, actions, int(status.get("interval_seconds") or 900))
    incidents = derive_incidents(devices, events, actions, risk)
    if eng is not None and getattr(eng, "incidents", None) is not None:
        incidents = eng.incidents.merge(incidents)
    policies = derive_policies(fences, devices, status)
    analytics = build_analytics(
        devices, events, actions, history, trails=trails,
        expected_interval_seconds=status.get("interval_seconds") or 900,
    )
    insights = build_insights(devices, events, actions, incidents, risk, stats)
    report = build_report(status, devices, incidents, risk, insights, analytics)

    return {
        "generated_at": _now(),
        "summary": {
            "fleet_size": len(devices),
            "open_incidents": len([i for i in incidents if i.get("status") == "open"]),
            "critical_incidents": len([i for i in incidents if i.get("severity") == "critical"]),
            "high_risk_devices": len([r for r in risk if r.get("score", 0) >= 70]),
            "policies_enabled": len([p for p in policies if p.get("enabled")]),
            "automation_mode": "dry-run" if status.get("dry_run") else "live",
        },
        "risk": risk,
        "incidents": incidents,
        "policies": policies,
        "analytics": analytics,
        "insights": insights,
        "report": report,
        "events": events,
        "actions": actions,
    }


def _risk_from_engine(eng: Any, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use the Geospatial Risk & Policy Engine as the single source of truth for
    device risk. Each device is scored with composite signals; matched policies
    are attached so the dashboard shows WHY a device is risky."""
    ctx = {
        "hour": eng._ctx_hour(),
        "shift_zones": eng._ctx_shift_zones(),
        "zone_risk": eng._ctx_zone_risk(),
    }
    rows = []
    for d in devices:
        fence_state = d.get("fence_state", "unknown")
        try:
            r = eng.risk.evaluate(d, fence_state, ctx)
        except Exception:
            r = {"risk_score": 0.0, "severity": "low", "reasons": [], "signals": {}}
        fired = []
        try:
            fired = eng.risk.match_policies(eng.policies, r, d, fence_state)
        except Exception:
            fired = []
        rows.append({
            "device_id": str(d.get("device_id") or ""),
            "device_name": d.get("name") or str(d.get("device_id") or ""),
            "platform": d.get("platform") or "unknown",
            "score": r.get("risk_score", 0.0),
            "level": r.get("severity", "low"),
            "factors": [{"points": 0, "label": x, "severity": r.get("severity", "low")} for x in r.get("reasons", [])],
            "signals": r.get("signals", {}),
            "matched_policies": [f["policy_id"] for f in fired],
            "fence_state": fence_state,
            "inside_fence": d.get("inside_fence"),
            "compliant": d.get("compliant"),
            "last_seen": d.get("last_seen"),
            "dwell_seconds": int(d.get("dwell_seconds") or 0),
            "stale": False,
            "recent_actions": 0,
        })
    return sorted(rows, key=lambda r: (r["score"], r["device_name"]), reverse=True)


def enrich_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_enrich_event(e) for e in events]


def enrich_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_enrich_action(a) for a in actions]


def compute_risk(
    devices: list[dict[str, Any]],
    events: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    interval_seconds: int = 900,
) -> list[dict[str, Any]]:
    exits = Counter(e.get("device_id") for e in events if e.get("kind") == "exit")
    failed_actions = Counter(a.get("device_id") for a in actions if a.get("ok") is False)
    actions_by_device: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in actions:
        if action.get("device_id"):
            actions_by_device[str(action.get("device_id"))].append(action)

    rows = []
    for d in devices:
        did = str(d.get("device_id") or "")
        score = 0
        factors: list[dict[str, Any]] = []

        def add(points: int, label: str, severity: str) -> None:
            nonlocal score
            score += points
            factors.append({"points": points, "label": label, "severity": severity})

        if d.get("compliant") is False:
            add(35, "No conforme con política UEM", "high")
        if d.get("fence_state") == "outside":
            add(30, "Fuera de geovalla", "critical")
        elif d.get("fence_state") == "unknown":
            add(15, "Estado de geovalla desconocido", "medium")

        ex = exits.get(did, 0)
        if ex:
            add(min(20, ex * 8), f"{ex} salida(s) reciente(s)", "high")

        fa = failed_actions.get(did, 0)
        if fa:
            add(min(25, fa * 15), f"{fa} acción(es) UEM fallida(s)", "medium")

        acc = _num(d.get("accuracy_m"))
        if acc is not None and acc > 100:
            add(10, "Precisión de ubicación baja", "medium")

        last_seen = _parse_dt(d.get("last_seen"))
        stale = False
        if last_seen:
            age = (datetime.now(timezone.utc) - last_seen).total_seconds()
            if age > max(1800, interval_seconds * 2):
                stale = True
                add(10, "Última señal obsoleta", "medium")

        dwell = int(d.get("dwell_seconds") or 0)
        if d.get("fence_state") == "outside" and dwell > interval_seconds:
            add(10, "Tiempo fuera de perímetro persistente", "high")

        score = max(0, min(100, score))
        level = _risk_level(score)
        rows.append({
            "device_id": did,
            "device_name": d.get("name") or did,
            "platform": d.get("platform") or "unknown",
            "score": score,
            "level": level,
            "factors": factors or [{"points": 0, "label": "Sin señales de riesgo relevantes", "severity": "low"}],
            "fence_state": d.get("fence_state"),
            "inside_fence": d.get("inside_fence"),
            "compliant": d.get("compliant"),
            "last_seen": d.get("last_seen"),
            "dwell_seconds": dwell,
            "stale": stale,
            "recent_actions": len(actions_by_device.get(did, [])),
        })
    return sorted(rows, key=lambda r: (r["score"], r["device_name"]), reverse=True)


def derive_incidents(
    devices: list[dict[str, Any]],
    events: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    risk: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []
    latest_event_ts: dict[str, str] = {}
    first_event_ts: dict[str, str] = {}
    exit_counts = Counter()
    for e in events:
        did = str(e.get("device_id") or "")
        if not did:
            continue
        ts = str(e.get("ts") or e.get("last_seen") or _now())
        first_event_ts.setdefault(did, ts)
        latest_event_ts[did] = ts
        if e.get("kind") == "exit":
            exit_counts[did] += 1

    risk_by_device = {r.get("device_id"): r for r in risk}
    for d in devices:
        did = str(d.get("device_id") or "")
        name = d.get("name") or did
        base_ts = str(d.get("last_seen") or latest_event_ts.get(did) or _now())

        if d.get("compliant") is False:
            incidents.append(_incident(
                f"inc-noncompliant-{did}", "device_non_compliant", "high",
                f"{name} no cumple la política UEM", did, name,
                "Revisar compliance, localizar el dispositivo y aplicar playbook de remediación.",
                first_event_ts.get(did, base_ts), base_ts,
                count=1,
            ))
        if d.get("fence_state") == "outside":
            severity = "critical" if d.get("compliant") is False else "high"
            incidents.append(_incident(
                f"inc-outside-{did}", "geofence_exit", severity,
                f"{name} está fuera de geovalla", did, name,
                "Validar ubicación reciente, contactar propietario y ejecutar acción UEM si procede.",
                first_event_ts.get(did, base_ts), base_ts,
                count=max(1, exit_counts.get(did, 0)),
            ))
        if d.get("fence_state") == "unknown":
            incidents.append(_incident(
                f"inc-unknown-{did}", "device_unknown_location", "medium",
                f"{name} tiene ubicación desconocida", did, name,
                "Forzar actualización de ubicación y revisar conectividad del agente.",
                base_ts, base_ts,
                count=1,
            ))
        rb = risk_by_device.get(did) or {}
        if rb.get("score", 0) >= 85:
            incidents.append(_incident(
                f"inc-critical-risk-{did}", "high_risk_device", "critical",
                f"{name} concentra riesgo crítico", did, name,
                "Priorizar revisión manual: combina señales de geovalla, compliance o automatización.",
                base_ts, base_ts,
                count=1,
            ))

    for a in actions:
        if a.get("ok") is False:
            did = str(a.get("device_id") or "unknown")
            name = a.get("device_name") or did
            act = a.get("action") or "UEM"
            ts = str(a.get("ts") or _now())
            incidents.append(_incident(
                f"inc-action-failed-{did}-{act}", "automation_failed", "medium",
                f"Falló la acción {act}", did, name,
                "Reintentar manualmente y revisar endpoint, permisos o credenciales UEM.",
                ts, ts,
                count=1,
            ))

    seen = set()
    unique = []
    for inc in incidents:
        if inc["id"] not in seen:
            seen.add(inc["id"])
            unique.append(inc)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return sorted(unique, key=lambda i: (order.get(i.get("severity"), 9), i.get("title", "")))


def derive_policies(fences: list[dict[str, Any]], devices: list[dict[str, Any]], status: dict[str, Any]) -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    total = max(1, len(devices))
    for f in fences:
        fid = f.get("id") or f.get("name") or "fence"
        scoped = [d for d in devices if d.get("inside_fence") == fid or d.get("fence_state") in ("outside", "unknown")]
        inside = len([d for d in devices if d.get("inside_fence") == fid and d.get("fence_state") == "inside"])
        outside = len([d for d in devices if d.get("fence_state") == "outside"])
        non_compliant = len([d for d in scoped if d.get("compliant") is False])
        score = round((inside / total) * 100)
        policies.append({
            "id": f"policy-fence-{fid}",
            "name": f"Perímetro: {f.get('name') or fid}",
            "enabled": True,
            "severity": "critical" if outside else ("high" if non_compliant else "medium"),
            "scope": f"{len(scoped) or len(devices)} dispositivo(s)",
            "mode": "dry-run" if status.get("dry_run") else "live",
            "description": "Detecta entradas/salidas y ejecuta playbooks UEM configurados para esta geovalla.",
            "compliance_percent": score,
            "inside": inside,
            "outside": outside,
            "non_compliant": non_compliant,
            "actions": list(f.get("actions") or []),
        })

    policies.extend([
        {
            "id": "policy-mdm-compliance",
            "name": "Cumplimiento UEM/MDM",
            "enabled": True,
            "severity": "high",
            "scope": "Toda la flota",
            "mode": "monitor",
            "description": "Eleva riesgo e incidentes cuando un dispositivo reporta non-compliant.",
            "compliance_percent": _compliance_percent(devices),
            "inside": len([d for d in devices if d.get("compliant") is not False]),
            "outside": len([d for d in devices if d.get("compliant") is False]),
            "non_compliant": len([d for d in devices if d.get("compliant") is False]),
            "actions": [],
        },
        {
            "id": "policy-local-audit",
            "name": "Auditoría local",
            "enabled": True,
            "severity": "medium",
            "scope": "Eventos, acciones y trails",
            "mode": "local-only",
            "description": "Registra actividad localmente para investigación y reporting sin publicar datos.",
            "compliance_percent": 100,
            "inside": len(devices),
            "outside": 0,
            "non_compliant": 0,
            "actions": [],
        },
        {
            "id": "policy-dry-run-guardrail",
            "name": "Guardrail dry-run",
            "enabled": bool(status.get("dry_run")),
            "severity": "info",
            "scope": "Acciones UEM",
            "mode": "safe" if status.get("dry_run") else "disabled",
            "description": "Permite validar playbooks sin contactar dispositivos reales.",
            "compliance_percent": 100 if status.get("dry_run") else 0,
            "inside": 1 if status.get("dry_run") else 0,
            "outside": 0 if status.get("dry_run") else 1,
            "non_compliant": 0,
            "actions": [],
        },
    ])
    return policies


def build_analytics(
    devices: list[dict[str, Any]],
    events: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    history: list[dict[str, Any]],
    *,
    trails: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    expected_interval_seconds: Any = 900,
) -> dict[str, Any]:
    platforms = Counter(str(d.get("platform") or "unknown") for d in devices)
    states = Counter(str(d.get("fence_state") or "unknown") for d in devices)
    kinds = Counter(str(e.get("kind") or "other") for e in events)
    action_names = Counter(str(a.get("action") or "unknown") for a in actions)
    compliance_series = []
    for i, h in enumerate(row for row in history[-60:] if isinstance(row, dict)):
        total, _ = _safe_nonnegative_int(h.get("devices_total"))
        non, _ = _safe_nonnegative_int(h.get("non_compliant"))
        non = min(total, non)
        inside, _ = _safe_nonnegative_int(h.get("inside"))
        outside, _ = _safe_nonnegative_int(h.get("outside"))
        unknown, _ = _safe_nonnegative_int(h.get("unknown"))
        compliance_series.append({
            "idx": i + 1,
            "ts": h.get("ts"),
            "compliance_percent": 100 if total == 0 else round(((total - non) / total) * 100),
            "inside": inside,
            "outside": outside,
            "unknown": unknown,
            "non_compliant": non,
        })
    return {
        "platform_distribution": dict(platforms),
        "state_distribution": dict(states),
        "event_distribution": dict(kinds),
        "action_distribution": dict(action_names),
        "compliance_series": compliance_series,
        "fleet_intelligence": _fleet_intelligence(
            history, trails or [], now=now,
            expected_interval_seconds=expected_interval_seconds,
        ),
    }


def _empty_fleet_intelligence(*, history_points=0, invalid_timestamp_count=0,
        duplicate_timestamp_count=0, clock_skew_detected=False,
        expected_interval_seconds=900, history_points_discarded=0):
    gap_threshold = max(1800, expected_interval_seconds * 2)
    return {
        "status": "insufficient_data", "history_points": history_points,
        "history_span_hours": 0, "median_interval_seconds": None,
        "p95_interval_seconds": None, "gap_threshold_seconds": gap_threshold,
        "gap_count": 0, "freshness_seconds": None, "compliance_delta_points": None,
        "outside_peak": 0, "geofence_transitions": 0, "top_transition_device": None,
        "signal_quality_score": 0, "invalid_timestamp_count": invalid_timestamp_count,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "clock_skew_detected": clock_skew_detected, "invalid_counter_count": 0,
        "quality_components": {"freshness_percent": 0, "continuity_percent": 0,
            "gps_coverage_percent": 0, "history_depth_percent": 0},
        "recommendations": ["Acumula al menos dos ciclos distintos para habilitar tendencias con evidencia."],
        "evidence": {"method": "observed-local-history", "prediction": False,
            "window_start": None, "window_end": None, "trail_window_start": None,
            "trail_window_end": None, "expected_interval_seconds": expected_interval_seconds,
            "history_points_discarded": history_points_discarded,
            "trail_points_analyzed": 0, "trail_points_discarded": 0,
            "quality_formula": "40% recencia + 30% continuidad + 20% cobertura GPS + 10% profundidad histórica"},
    }


def _fleet_intelligence(history, trails, *, now=None, expected_interval_seconds=900):
    """Derive bounded, explainable intelligence from observed local history."""
    observed_now = now or datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        observed_now = observed_now.replace(tzinfo=timezone.utc)
    observed_now = observed_now.astimezone(timezone.utc)
    expected, expected_invalid = _safe_nonnegative_int(expected_interval_seconds)
    expected = min(86400, max(1, expected or 900))
    gap_threshold = max(1800, expected * 2)

    source = history[-MAX_HISTORY_POINTS:]
    history_discarded = max(0, len(history) - len(source))
    invalid_timestamps, clock_skew, parsed = 0, False, []
    for row in source:
        dt = _parse_dt(row.get("ts")) if isinstance(row, dict) else None
        if dt is None:
            invalid_timestamps += 1; continue
        if (dt - observed_now).total_seconds() > ALLOWED_CLOCK_SKEW_SECONDS:
            invalid_timestamps += 1; clock_skew = True; continue
        parsed.append((dt, row))
    parsed.sort(key=lambda item: item[0])
    unique = {dt: row for dt, row in parsed}
    duplicates = len(parsed) - len(unique)
    timeline = sorted(unique.items())
    if len(timeline) < 2:
        result = _empty_fleet_intelligence(history_points=len(timeline),
            invalid_timestamp_count=invalid_timestamps, duplicate_timestamp_count=duplicates,
            clock_skew_detected=clock_skew, expected_interval_seconds=expected,
            history_points_discarded=history_discarded)
        if clock_skew:
            result["recommendations"].append("Revisa el reloj de origen: hay timestamps futuros descartados.")
        return result

    timestamps = [dt for dt, _ in timeline]
    intervals = [(b-a).total_seconds() for a,b in zip(timestamps,timestamps[1:])]
    ordered = sorted(intervals)
    median_interval = int(round(median(intervals)))
    p95_interval = int(round(ordered[max(0, math.ceil(len(ordered)*.95)-1)]))
    gap_count = sum(seconds > gap_threshold for seconds in intervals)
    continuity = round((1-gap_count/len(intervals))*100)
    freshness_seconds = max(0, round((observed_now-timestamps[-1]).total_seconds()))
    freshness = 100 if freshness_seconds <= gap_threshold else max(0,
        round(100-((freshness_seconds-gap_threshold)/gap_threshold)*50))

    invalid_counters = int(expected_invalid)
    def counter(row, key):
        nonlocal invalid_counters
        value, invalid = _safe_nonnegative_int(row.get(key)); invalid_counters += int(invalid)
        return value
    def compliance(row):
        nonlocal invalid_counters
        total, non = counter(row,"devices_total"), counter(row,"non_compliant")
        if non > total: non, invalid_counters = total, invalid_counters+1
        return 100 if total == 0 else round((total-non)/total*100)

    trail_source = trails[-MAX_TRAIL_POINTS:]
    trail_discarded = max(0, len(trails)-len(trail_source))
    trail_end = min(timestamps[-1], observed_now)
    trail_rows = []
    for row in trail_source:
        dt = _parse_dt(row.get("ts")) if isinstance(row,dict) else None
        if dt is None or dt < timestamps[0] or dt > trail_end:
            trail_discarded += 1; continue
        trail_rows.append((str(row.get("device_id") or ""),dt,row))
    trail_rows.sort(key=lambda item:(item[0],item[1]))
    transitions, previous, coordinates = Counter(), {}, 0
    for device_id, _, row in trail_rows:
        coordinates += int(_valid_coordinate(row.get("lat"),row.get("lng")))
        if not device_id: continue
        state = str(row.get("fence_state") or "unknown")
        if device_id in previous and state != previous[device_id]: transitions[device_id] += 1
        previous[device_id] = state

    gps = round(coordinates/len(trail_rows)*100) if trail_rows else 0
    span = max(0,(timestamps[-1]-timestamps[0]).total_seconds())
    depth = min(100,round(span/86400*100))
    quality = int(freshness*.4+continuity*.3+gps*.2+depth*.1)
    delta = max(-100,min(100,compliance(timeline[-1][1])-compliance(timeline[0][1])))
    outside_peak = max(counter(row,"outside") for _,row in timeline)
    recommendations=[]
    if clock_skew: recommendations.append("Revisa el reloj de origen: hay timestamps futuros descartados.")
    if freshness < 100: recommendations.append("Revisa la ingesta: el último ciclo está retrasado.")
    if gap_count:
        label="interrupción" if gap_count==1 else "interrupciones"
        recommendations.append(f"Investiga {gap_count} {label} superiores a {gap_threshold//60} minutos.")
    if delta < -2: recommendations.append("La conformidad observada empeoró; revisa dispositivos non-compliant.")
    if transitions: recommendations.append("Revisa los dispositivos con más transiciones de geovalla.")
    if not recommendations: recommendations.append("La señal histórica es estable; continúa monitorizando.")
    top=transitions.most_common(1)
    return {
        "status":"ready","history_points":len(timeline),"history_span_hours":round(span/3600,2),
        "median_interval_seconds":median_interval,"p95_interval_seconds":p95_interval,
        "gap_threshold_seconds":gap_threshold,"gap_count":gap_count,"freshness_seconds":freshness_seconds,
        "compliance_delta_points":delta,"outside_peak":outside_peak,
        "geofence_transitions":sum(transitions.values()),
        "top_transition_device":({"device_id":top[0][0],"transitions":top[0][1]} if top else None),
        "signal_quality_score":quality,"invalid_timestamp_count":invalid_timestamps,
        "duplicate_timestamp_count":duplicates,"clock_skew_detected":clock_skew,
        "invalid_counter_count":invalid_counters,
        "quality_components":{"freshness_percent":freshness,"continuity_percent":continuity,
            "gps_coverage_percent":gps,"history_depth_percent":depth},
        "recommendations":recommendations,
        "evidence":{"method":"observed-local-history","prediction":False,
            "window_start":timestamps[0].isoformat(),"window_end":timestamps[-1].isoformat(),
            "trail_window_start":timestamps[0].isoformat(),"trail_window_end":trail_end.isoformat(),
            "expected_interval_seconds":expected,"history_points_discarded":history_discarded,
            "trail_points_analyzed":len(trail_rows),"trail_points_discarded":trail_discarded,
            "quality_formula":"40% recencia + 30% continuidad + 20% cobertura GPS + 10% profundidad histórica"},
    }


def build_insights(
    devices: list[dict[str, Any]],
    events: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    risk: list[dict[str, Any]],
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    if any(d.get("compliant") is False for d in devices):
        insights.append({"kind": "risk", "severity": "high", "title": "Hay dispositivos non-compliant", "body": "Prioriza remediación antes de permitir acciones sensibles fuera de geovalla."})
    if any(r.get("score", 0) >= 70 for r in risk):
        insights.append({"kind": "priority", "severity": "high", "title": "Riesgo concentrado en pocos dispositivos", "body": "Abre Risk Center y revisa las razones por dispositivo antes de escalar."})
    if any(e.get("kind") == "exit" for e in events):
        insights.append({"kind": "movement", "severity": "medium", "title": "Se detectaron salidas de perímetro", "body": "Cruza geovalla, compliance y última ubicación para decidir si activar playbook."})
    if not actions:
        insights.append({"kind": "automation", "severity": "info", "title": "Sin acciones UEM recientes", "body": "El sistema está monitorizando; no se han ejecutado playbooks en la ventana reciente."})
    if not incidents and stats.get("non_compliant", 0) == 0 and stats.get("outside", 0) == 0:
        insights.append({"kind": "healthy", "severity": "low", "title": "Flota estable", "body": "No hay señales críticas en la última evaluación."})
    return insights[:6]


def build_report(
    status: dict[str, Any],
    devices: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    risk: list[dict[str, Any]],
    insights: list[dict[str, Any]],
    analytics: dict[str, Any],
) -> dict[str, Any]:
    critical = [i for i in incidents if i.get("severity") == "critical"]
    high = [i for i in incidents if i.get("severity") == "high"]
    top = risk[0] if risk else None
    posture = "critical" if critical else "elevated" if high else "stable"
    series = analytics.get("compliance_series") or []
    trend = "flat"
    if len(series) >= 2:
        delta = series[-1]["compliance_percent"] - series[0]["compliance_percent"]
        trend = "up" if delta > 2 else "down" if delta < -2 else "flat"
    return {
        "title": "Executive posture report",
        "generated_at": _now(),
        "posture": posture,
        "narrative": (
            "Postura crítica: existen salidas de geovalla o dispositivos de alto impacto."
            if posture == "critical" else
            "Postura elevada: hay señales de incumplimiento que requieren seguimiento."
            if posture == "elevated" else
            "Postura estable: la flota no muestra incidentes críticos activos."
        ),
        "metrics": {
            "devices": len(devices),
            "compliance_percent": _compliance_percent(devices),
            "incidents": len(incidents),
            "critical": len(critical),
            "high": len(high),
            "max_risk_score": top.get("score") if top else 0,
            "dry_run": bool(status.get("dry_run")),
            "trend": trend,
        },
        "top_risk_devices": risk[:5],
        "recommended_next_actions": [
            "Revisar incidentes críticos abiertos",
            "Validar dispositivos non-compliant",
            "Forzar ciclo manual y comparar evolución",
            "Exportar reporte ejecutivo para auditoría local",
        ],
        "insights": insights,
    }


def _enrich_event(e: dict[str, Any]) -> dict[str, Any]:
    out = dict(e)
    kind = str(out.get("kind") or _event_kind(out))
    out["kind"] = kind
    out["severity"] = "high" if kind == "exit" else "medium" if kind in ("state_change", "action") else "info"
    out["title"] = {
        "enter": "Entrada en geovalla",
        "exit": "Salida de geovalla",
        "action": "Acción UEM",
        "state_change": "Cambio de estado",
        "other": "Evento",
    }.get(kind, "Evento")
    return out


def _enrich_action(a: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    out["kind"] = "action"
    out["severity"] = "info" if out.get("ok", True) else "medium"
    out["title"] = f"Acción {out.get('action') or 'UEM'}"
    return out


def _event_kind(e: dict[str, Any]) -> str:
    if e.get("action"):
        return "action"
    to = str(e.get("to") or "")
    frm = str(e.get("from") or "")
    if ":inside" in to or to == "inside":
        return "enter"
    if ":outside" in to or to == "outside":
        return "exit"
    if "outside" in to and "inside" in frm:
        return "exit"
    if "inside" in to and "outside" in frm:
        return "enter"
    return "state_change" if to or frm else "other"


def _incident(
    incident_id: str,
    kind: str,
    severity: str,
    title: str,
    device_id: str,
    device_name: str,
    recommendation: str,
    first_seen: str,
    last_seen: str,
    count: int = 1,
) -> dict[str, Any]:
    return {
        "id": incident_id,
        "type": kind,
        "severity": severity,
        "status": "open",
        "title": title,
        "device_id": device_id,
        "device_name": device_name,
        "recommendation": recommendation,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "count": count,
    }


def _risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _compliance_percent(devices: list[dict[str, Any]]) -> int:
    if not devices:
        return 100
    ok = len([d for d in devices if d.get("compliant") is not False])
    return round((ok / len(devices)) * 100)


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
