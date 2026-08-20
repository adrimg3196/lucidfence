"""Políticas y geocercas como código — la lógica de `lucidfence apply`.

GitOps sin servidor (el flujo config-as-code de Fleet, sin necesitar su
server): la config candidata vive en git; `apply` la valida con los MISMOS
validadores que usa el engine, enseña el diff por id contra la config viva del
data dir y, antes de escribir nada, reproduce el cambio contra el histórico
local (policy_replay) para responder "¿qué habría hecho esta config la semana
pasada?". Solo escribe ficheros locales (tmp + os.replace); jamás toca un
dispositivo — el runtime (dry_run/enforce/wipe) sigue mandando en el engine.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from lucidfence.core.fences import Fence, load_fences, validate_fences
from lucidfence.core.policies import load_policies, validate_policies
from lucidfence.core.policy_replay import load_trail_points, replay_policy


def _fence_row(f: Fence) -> dict:
    """Forma canónica de una geocerca (la misma que persiste save_fences)."""
    return {
        "id": f.id,
        "name": f.name,
        "type": f.type,
        "center": ({"lat": f.center.lat, "lng": f.center.lng} if f.center else None),
        "radius_m": f.radius_m,
        "coordinates": [{"lat": p.lat, "lng": p.lng} for p in f.coordinates],
        "rules": f.rules,
        "actions": [
            {"action": a.action, "when": a.when, "params": a.params, "enabled": a.enabled}
            for a in f.actions
        ],
    }


def load_fences_candidate(path: str | Path) -> dict:
    """Carga y valida un fences.json candidato.

    Devuelve {"path", "text", "fences", "by_id", "count", "errors"}. Cada
    error lleva "fichero: id: motivo" (estilo Fleet: preciso y accionable);
    errors vacío == candidato válido.
    """
    path = Path(path)
    out: dict = {"path": str(path), "text": "", "fences": [], "by_id": {}, "count": 0, "errors": []}
    try:
        out["text"] = path.read_text(encoding="utf-8")
        data = json.loads(out["text"])
    except OSError as e:
        out["errors"].append(f"{path}: no se puede leer ({e})")
        return out
    except json.JSONDecodeError as e:
        out["errors"].append(f"{path}: JSON inválido (línea {e.lineno}: {e.msg})")
        return out
    raw_list = data.get("fences", data if isinstance(data, list) else [data])
    if not isinstance(raw_list, list):
        out["errors"].append(f"{path}: 'fences' debe ser una lista")
        return out
    fences: list[Fence] = []
    for i, raw in enumerate(raw_list):
        fid = raw.get("id") if isinstance(raw, dict) else None
        try:
            fences.append(Fence.from_raw(raw))
        except Exception as e:  # el motivo depende del campo roto (KeyError/ValueError/...)
            out["errors"].append(f"{path}: {fid or f'objeto #{i}'}: no parsea ({e})")
    for problem in validate_fences(fences):
        out["errors"].append(f"{path}: {problem}")
    out["fences"] = fences
    out["by_id"] = {f.id: _fence_row(f) for f in fences}
    out["count"] = len(fences)
    return out


def load_policies_candidate(path: str | Path) -> dict:
    """Carga y valida un policies.json candidato (mismo contrato que fences)."""
    path = Path(path)
    out: dict = {"path": str(path), "text": "", "raw": [], "by_id": {}, "count": 0, "errors": []}
    try:
        out["text"] = path.read_text(encoding="utf-8")
        data = json.loads(out["text"])
    except OSError as e:
        out["errors"].append(f"{path}: no se puede leer ({e})")
        return out
    except json.JSONDecodeError as e:
        out["errors"].append(f"{path}: JSON inválido (línea {e.lineno}: {e.msg})")
        return out
    for problem in validate_policies(data):
        out["errors"].append(f"{path}: {problem}")
    if isinstance(data, list):
        out["raw"] = data
        out["count"] = len(data)
    if not out["errors"]:
        # Canónico vía el MISMO cargador del engine, para que el diff compare
        # lo que el engine vería y no diferencias de formato.
        out["by_id"] = {p.id: p.to_dict() for p in load_policies(path)}
    return out


def load_live_fence_rows(path: str | Path) -> dict[str, dict]:
    """Config viva -> filas canónicas por id. Fail-soft: ausente/corrupta = {}."""
    try:
        return {f.id: _fence_row(f) for f in load_fences(path)}
    except Exception:
        return {}


def load_live_policy_rows(path: str | Path) -> dict[str, dict]:
    return {p.id: p.to_dict() for p in load_policies(Path(path))}  # ya fail-soft


def load_raw_policies(path: str | Path) -> list[dict]:
    """policies.json crudo (para el replay, que espera dicts)."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except (OSError, ValueError):
        return []


def diff_rows(live: dict[str, dict], cand: dict[str, dict]) -> dict:
    """Diff por id entre config viva y candidata: added/changed/removed."""
    return {
        "added": sorted(i for i in cand if i not in live),
        "changed": sorted(i for i in cand if i in live and cand[i] != live[i]),
        "removed": sorted(i for i in live if i not in cand),
    }


def what_if(data_dir: str | Path, policies: list[dict], fences: Optional[list[Fence]]) -> dict:
    """Replay de las políticas que quedarían activas, sobre el histórico local.

    `fences`: si el apply trae geocercas candidatas, el fence_state se
    recalcula contra ellas (what-if de geocercas + políticas a la vez); si no,
    se usa el fence_state grabado en el trail. Solo lectura: es un plan.
    """
    data_dir = Path(data_dir)
    points = load_trail_points(data_dir / "trails.jsonl")
    result: dict = {"points": len(points), "replays": []}
    if not points:
        return result
    states: dict[str, dict] = {}
    try:
        for d in json.loads((data_dir / "device_states.json").read_text(encoding="utf-8")):
            if isinstance(d, dict) and d.get("device_id"):
                states[d["device_id"]] = d
    except (OSError, ValueError):
        pass
    for p in policies:
        if not p.get("enabled", True) or not p.get("when"):
            continue
        result["replays"].append(replay_policy(p, points, fences=fences, device_states=states))
    return result


def apply_atomic(target: str | Path, text: str) -> None:
    """Escribe el candidato TAL CUAL, de forma atómica (tmp + os.replace)."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)
