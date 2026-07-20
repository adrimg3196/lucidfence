#!/usr/bin/env python3
"""roadmap_tooling.py — Motor del roadmap anual de mejora tooling para LucidFence.

Fuente de verdad: roadmap.json (4 fases Q3-2026 -> Q2-2027, ~20 features de
mejora CLI/API/Dashboard/Engine/QA/loop). Cada feature tiene impacto, esfuerzo,
criterios y subtareas. El schema es la ley.

Uso:
  python3 roadmap_tooling.py --validate
  python3 roadmap_tooling.py [--phase Q3-2026] [--status in_progress]
  python3 roadmap_tooling.py --mark F1.1 status done
  python3 roadmap_tooling.py --export
Integracion:
  - saas_server.py: GET /api/roadmap (lee + anade progress computado)
  - loop_improve.py: lee roadmap para priorizar iteraciones
"""

import json
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROADMAP_JSON = _HERE / "roadmap.json"

_VALID_PHASES = {"Q3-2026", "Q4-2026", "Q1-2027", "Q2-2027"}
_VALID_IMPACTS = {"p0_must", "p1_should", "p2_nice"}
_VALID_EFFORTS = {"small", "medium", "large", "epic"}
_VALID_FSTATUS = {"proposed", "planned", "in_progress", "done", "deployed", "blocked"}
_VALID_PSTATUS = {"pending", "on_track", "at_risk", "complete"}
_VALID_CAPS = {"cli", "api", "dashboard", "engine", "config", "observability",
               "security", "docs", "devops", "plugin", "loop"}


def load_roadmap():
    if not _ROADMAP_JSON.exists():
        return None
    with open(_ROADMAP_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_roadmap(d):
    with open(_ROADMAP_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")


def all_features(d):
    """Lista plana de todas las features (anade _phase_id a cada una)."""
    out = []
    for ph in d.get("plan", {}).get("phases", []):
        for feat in ph.get("features", []):
            feat["_phase_id"] = ph["id"]
            out.append(feat)
    return out


def validate_roadmap(d):
    """Retorna lista de errores. Vacía = valido."""
    errs = []
    if not d:
        return ["roadmap vacio o None"]
    meta = d.get("meta", {})
    plan = d.get("plan", {})
    if not meta.get("version"):
        errs.append("meta.version requerido")
    if not plan.get("phases"):
        return ["plan.phases vacio"]
    seen_ids = set()
    for ph in plan["phases"]:
        pid = ph.get("id", "")
        if pid not in _VALID_PHASES:
            errs.append(f"fase '{pid}' no valida; debe ser {sorted(_VALID_PHASES)}")
        if ph.get("status") not in _VALID_PSTATUS:
            errs.append(f"fase '{pid}' status '{ph.get('status')}' invalido")
        for feat in ph.get("features", []):
            fid = feat.get("id", "")
            if fid in seen_ids:
                errs.append(f"feature '{fid}' duplicada")
            seen_ids.add(fid)
            if feat.get("impact") not in _VALID_IMPACTS:
                errs.append(f"{fid}: impact '{feat.get('impact')}' invalido")
            if feat.get("effort") not in _VALID_EFFORTS:
                errs.append(f"{fid}: effort '{feat.get('effort')}' invalido")
            if feat.get("status") not in _VALID_FSTATUS:
                errs.append(f"{fid}: status '{feat.get('status')}' invalido")
            cap = feat.get("capability", "")
            if cap and cap not in _VALID_CAPS:
                errs.append(f"{fid}: capability '{cap}' invalida")
            if not feat.get("title"):
                errs.append(f"{fid}: title requerido")
    return errs


def update_feature(d, feature_id, field, value):
    """Actualiza un campo de una feature. Retorna (ok, msg)."""
    for feat in all_features(d):
        if feat["id"] == feature_id:
            if field == "status" and value not in _VALID_FSTATUS:
                return False, f"status '{value}' invalido; debe ser {sorted(_VALID_FSTATUS)}"
            if field == "impact" and value not in _VALID_IMPACTS:
                return False, f"impact '{value}' invalido"
            if field == "effort" and value not in _VALID_EFFORTS:
                return False, f"effort '{value}' invalido"
            feat[field] = value
            d.setdefault("meta", {})["updated"] = str(date.today())
            return True, f"{feature_id}.{field} -> {value}"
    return False, f"feature '{feature_id}' no encontrada"


def _compute_progress(d):
    feats = all_features(d)
    total = len(feats)
    if total == 0:
        return {"total": 0, "done": 0, "pct": 0}
    done = sum(1 for f in feats if f["status"] in ("done", "deployed"))
    return {"total": total, "done": done, "pct": int(round(100 * done / total))}


def _progress_bar(pct, width=10):
    filled = int(round(width * pct / 100))
    return "█" * filled + "░" * (width - filled)


def format_roadmap(d, phase=None, status_filter=None):
    prog = _compute_progress(d)
    bar = _progress_bar(prog["pct"])
    lines = [
        "📋 LucidFence ROADMAP · Mejora tooling · 12 meses · Q3-2026 → Q2-2027",
        f"   progreso global: [{bar}] {prog['pct']}%  ({prog['done']}/{prog['total']} features done)\n",
    ]
    icon_map = {"done": "✓", "deployed": "🚀", "in_progress": "▶",
                "blocked": "✗", "planned": "○", "proposed": "?"}
    for ph in d.get("plan", {}).get("phases", []):
        if phase and ph["id"] != phase:
            continue
        lines.append(f"◉ {ph['id']} ({ph['timeframe']}): {ph['title']}  [{ph['status']}]")
        for feat in ph.get("features", []):
            if status_filter and feat["status"] != status_filter:
                continue
            icon = icon_map.get(feat["status"], "?")
            pct = ""
            p = feat.get("progress", {}).get("pct")
            if isinstance(p, int):
                pct = f" ({p}%)"
            lines.append(f"  [{icon}] {feat['id']} {feat['title']}  · {feat['impact']}/{feat['effort']}{pct}")
    return "\n".join(lines)


def get_api_response(d):
    """Dict para GET /api/roadmap (incluye progress computado)."""
    return {"plan": d.get("plan"), "meta": d.get("meta"), "progress": _compute_progress(d)}


def patch_api(d, body):
    """Procesa PATCH /api/roadmap. Retorna (status_code, response_dict)."""
    feature_id = body.get("feature")
    field = body.get("field", "status")
    value = body.get("value", body.get("status"))
    if not feature_id or not value:
        return 400, {"error": "requiere feature + status"}
    ok, msg = update_feature(d, feature_id, field, value)
    if ok:
        save_roadmap(d)
        return 200, {"ok": True, "feature": feature_id, "status": value}
    return 404, {"error": msg}


if __name__ == "__main__":
    d = load_roadmap()
    if not d:
        print("roadmap.json no encontrado")
        sys.exit(1)
    if "--validate" in sys.argv:
        errs = validate_roadmap(d)
        if errs:
            for e in errs:
                print(f"  ✗ {e}")
            sys.exit(1)
        print(f"roadmap valido: OK (schema + {len(all_features(d))} features)")
    elif "--export" in sys.argv:
        print(json.dumps(d, indent=2, ensure_ascii=False))
    elif "--mark" in sys.argv:
        i = sys.argv.index("--mark")
        fid, field, val = sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3]
        ok, msg = update_feature(d, fid, field, val)
        if not ok:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        save_roadmap(d)
        print(f"roadmap: {fid}.{field} -> {val} (persistido)")
    else:
        # filtros opcionales
        phase = None
        status_filter = None
        if "--phase" in sys.argv:
            phase = sys.argv[sys.argv.index("--phase") + 1]
        if "--status" in sys.argv:
            status_filter = sys.argv[sys.argv.index("--status") + 1]
        print(format_roadmap(d, phase=phase, status_filter=status_filter))
