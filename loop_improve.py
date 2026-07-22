#!/usr/bin/env python3
"""loop_improve.py — El /loop de mejora continua de LucidFence (MoA).

Arquitectura (ver AGENTS.md / ROADMAP_TOOLING.md):
  - PROPOSERS (paralelos): todos los modelos gratis disponibles. Se leen de
    config_loader / .env (LF_PROVIDER_*). Si hay API key, se llama al free tier
    real (OpenRouter/Nous, Groq, NVIDIA, Together, Fireworks, DeepInfra, GitHub,
    OpenAI). Si NO hay clave, el proposer degrada a analisis local deterministico
    para que el loop sea demostrable sin secretos.
  - AGREGADOR: Claude Opus 4.8. Se invoca via `claude` CLI (Claude Code) si esta
    presente en el PATH; si no, merge heuristico local. (El server MoA en
    127.0.0.1:8085 tambien es un agregador valido cuando esta arriba.)
  - VERIFY: corre tests/run_tests.py y valida roadmap_tooling.
  - HISTORY: cada iteracion se append-a a data/loop_history.jsonl.

Control de calidad:
  - Max 3 iteraciones por feature.
  - Temperatura decae 0.1 por iteracion.
  - El agregador decide parar cuando la calidad >= threshold (7/10).
  - Sin loops infinitos.

Uso:
  python3 loop_improve.py                     # mejora la proxima feature pendiente
  python3 loop_improve.py --feature F1.2      # mejora una feature concreta
  python3 loop_improve.py --max-iter 3 --dry-run
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import roadmap_tooling as rm
from core.provider_plugins import discover_provider_plugins, merge_providers
from core.loop_governance import KillSwitch

_CLI = os.environ.get("LUCIDFENCE_CLAUDE_CLI") or shutil.which("claude") or ""
_HISTORY = _HERE / "data" / "loop_history.jsonl"


def _kill_switch() -> KillSwitch:
    return KillSwitch(Path(os.environ.get("LUCIDFENCE_DATA_DIR", str(_HERE / "data"))))
_LOOP_CFG = {
    "max_iterations": 3,
    "temp_start": 0.7,
    "temp_decay": 0.1,
    "quality_threshold": 7,
}

# --- Inventario de modelos gratis (los que pide el usuario) ---
# Cada entrada: nombre, env-var de api key, base_url, modelo por defecto.
FREE_PROVIDERS = [
    {"name": "nous_openrouter", "env": "LF_PROVIDER_OPENROUTER_API_KEY",
     "base": "https://openrouter.ai/api/v1", "model": "nousresearch/hermes-3-llama-3.1-405b:free"},
    {"name": "groq", "env": "LF_PROVIDER_GROQ_API_KEY",
     "base": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    {"name": "nvidia", "env": "LF_PROVIDER_NVIDIA_API_KEY",
     "base": "https://integrate.api.nvidia.com/v1", "model": "meta/llama-3.1-70b-instruct"},
    {"name": "together", "env": "LF_PROVIDER_TOGETHER_API_KEY",
     "base": "https://api.together.xyz/v1", "model": "mistralai/Mixtral-8x22B-Instruct-v0.1"},
    {"name": "fireworks", "env": "LF_PROVIDER_FIREWORKS_API_KEY",
     "base": "https://api.fireworks.ai/inference/v1", "model": "accounts/fireworks/models/llama-v3p3-70b-instruct"},
    {"name": "deepinfra", "env": "LF_PROVIDER_DEEPINFRA_API_KEY",
     "base": "https://api.deepinfra.com/v1/openai", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    {"name": "github", "env": "LF_PROVIDER_GITHUB_API_KEY",
     "base": "https://models.inference.ai.azure.com", "model": "gpt-4o-mini"},
    {"name": "openai", "env": "LF_PROVIDER_OPENAI_API_KEY",
     "base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
]


def _provider_catalog():
    plugins = discover_provider_plugins(_HERE / "plugins" / "providers")
    return merge_providers(FREE_PROVIDERS, plugins)


def _available_providers():
    """Devuelve los providers con API key presente (los que se pueden llamar de verdad)."""
    out = []
    for p in _provider_catalog():
        if os.environ.get(p["env"]) or (Path(_HERE / ".env").exists() and _env_has(_HERE / ".env", p["env"])):
            out.append(p)
    return out


def _env_has(env_path, key):
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "=") and line.split("=", 1)[1].strip().strip('"\''):
                return True
    except Exception:
        pass
    return False


def _local_proposer(feature, temperature):
    """Analista local deterministico (fallback cuando no hay clave del provider)."""
    title = feature.get("title", "")
    cap = feature.get("capability", "")
    impact = feature.get("impact", "")
    effort = feature.get("effort", "")
    subtasks = "\n".join(f"  - {s['title']} [{s['status']}]" for s in feature.get("subtasks", []))
    return (
        f"[PROPOSAL:local-analysis] Para la feature '{feature['id']}' ({title}):\n"
        f"Capa={cap} Impacto={impact} Esfuerzo={effort}.\n"
        f"Pasos sugeridos:\n{subtasks}\n"
        f"Criterios de aceptacion: " + "; ".join(feature.get("acceptance_criteria", [])) + "\n"
        f"Riesgo: esfuerzo {effort} y dependencias {feature.get('dependencies', [])}. "
        f"Recomendacion: implementar subtareas en orden, verificar con tests/run_tests.py."
    )


def _call_provider(provider, prompt, temperature):
    """Llamada real a un free tier (OpenAI-compatible). Timeout corto. Retorna texto o None."""
    import urllib.request
    key = os.environ.get(provider["env"])
    if not key and Path(_HERE / ".env").exists():
        for line in Path(_HERE / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(provider["env"] + "="):
                key = line.split("=", 1)[1].strip().strip('"\'')
    if not key:
        return None
    body = json.dumps({
        "model": provider["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 800,
    }).encode()
    req = urllib.request.Request(provider["base"] + "/chat/completions", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[PROPOSAL:{provider['name']}:ERROR {e}]"


def _aggregate(proposals, feature, temperature):
    """Agrega propuestas con Opus 4.8 (claude CLI) si esta; si no, merge heuristico."""
    prompt = (
        "Eres el agregador final (Claude Opus 4.8) de un sistema Mixture-of-Agents "
        "para mejorar la herramienta de geofencing LucidFence.\n"
        f"FEATURE A MEJORAR: {feature['id']} — {feature.get('title')}\n"
        f"Capa={feature.get('capability')} Impacto={feature.get('impact')} Esfuerzo={feature.get('effort')}\n\n"
        "PROPUESTAS DE LOS PROPOSERS (modelos gratis):\n"
        + "\n\n".join(proposals)
        + "\n\nFusiona en UNA recomendacion coherente y senala conflictos. "
          "Responde en espanol, conciso, con pasos accionables."
    )
    if Path(_CLI).exists():
        try:
            r = subprocess.run(
                [_CLI, "-p", prompt, "--model", "opus", "--temperature", str(temperature)],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception as e:
            pass  # cae a merge heuristico
    # Merge heuristico local (sin clave/sin claude)
    merged = "\n".join(proposals)
    summary = (
        f"[AGGREGATE:local-heuristic] Resumen de {len(proposals)} propuestas para {feature['id']}.\n"
        "Consenso: implementar subtareas en orden, verificar con tests/run_tests.py y "
        "roadmap_tooling.py --validate. " + merged[:1500]
    )
    return summary


def _quality_score(text):
    """Score heuristico 0-10 (sin LLM). Premia estructura y longitud razonable."""
    if not text:
        return 0
    score = 2
    if "subtask" in text.lower() or "paso" in text.lower():
        score += 2
    if "test" in text.lower() or "qa" in text.lower():
        score += 2
    if len(text) > 300:
        score += 2
    if "conflict" in text.lower() or "riesgo" in text.lower():
        score += 1
    if "opus" in text.lower() or "agreg" in text.lower():
        score += 1
    return min(10, score)


def _verify():
    """Corre la suite honesta. Retorna (passed: bool, detail: str)."""
    try:
        r = subprocess.run(
            [sys.executable, "tests/run_tests.py"],
            capture_output=True, text=True, timeout=300, cwd=str(_HERE),
        )
        ok = r.returncode == 0
        # Extraer conteo si aparece
        detail = ""
        for line in r.stdout.splitlines():
            if "PASS" in line and "FAIL" in line:
                detail = line.strip()
        return ok, (detail or (r.stdout[-400:] if ok else r.stderr[-400:]))
    except Exception as e:
        return False, f"verify error: {e}"


def _record(entry):
    _HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def loop_metrics():
    """Aggregate bounded, secret-free quality metrics for dashboard/ops."""
    rows = []
    try:
        for line in _HISTORY.read_text(encoding="utf-8").splitlines()[-1000:]:
            item = json.loads(line)
            if isinstance(item, dict) and "score" in item:
                rows.append(item)
    except (OSError, json.JSONDecodeError):
        pass
    scores = [float(row.get("score") or 0) for row in rows]
    return {
        "iterations": len(rows),
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "providers": sorted({name for row in rows for name in row.get("providers", [])}),
        "quality_threshold": _LOOP_CFG["quality_threshold"],
        "below_threshold": sum(score < _LOOP_CFG["quality_threshold"] for score in scores),
    }


def _next_feature(d):
    """Dependency-aware priority: active first, then impact, then effort."""
    features = rm.all_features(d)
    done = {f["id"] for f in features if f["status"] in ("done", "deployed")}
    impact = {"p0_must": 0, "p1_should": 1, "p2_nice": 2}
    effort = {"small": 0, "medium": 1, "large": 2, "epic": 3}
    eligible = [f for f in features if f["status"] in ("in_progress", "planned")
                and set(f.get("dependencies") or []).issubset(done)]
    eligible.sort(key=lambda f: (0 if f["status"] == "in_progress" else 1,
                                 impact.get(f.get("impact"), 9), effort.get(f.get("effort"), 9), f["id"]))
    return eligible[0] if eligible else None


def _feature_evidence_complete(feature):
    subtasks = feature.get("subtasks") or []
    return bool(subtasks) and all(item.get("status") == "done" for item in subtasks)


def run_loop(feature_id=None, max_iter=None, dry_run=False) -> int:
    if not _kill_switch().enabled:
        print("⛔ /loop deshabilitado por kill switch persistente")
        return 4
    if max_iter is None:
        max_iter = int(_LOOP_CFG["max_iterations"])
    d = rm.load_roadmap()
    if not d:
        print("roadmap.json no encontrado", file=sys.stderr)
        return 1
    feature = None
    if feature_id:
        for f in rm.all_features(d):
            if f["id"] == feature_id:
                feature = f
    if feature is None:
        feature = _next_feature(d)
    if feature is None:
        print("No hay features pendientes para mejorar.")
        return 0

    print(f"\n🔁 /loop sobre {feature['id']} — {feature['title']}")
    print(f"   proposers gratis disponibles: "
          + (", ".join(p["name"] for p in _available_providers()) or "NINGUNO (modo local deterministico)"))

    temp = _LOOP_CFG["temp_start"]
    best = None
    best_score = -1
    for i in range(1, max_iter + 1):
        print(f"\n--- iteracion {i}/{max_iter} (temp={temp:.1f}) ---")
        # Proposers paralelos (simulados en secuencia; cada uno es independiente)
        proposals = []
        providers = _available_providers()
        with ThreadPoolExecutor(max_workers=max(1, min(8, len(providers)))) as pool:
            futures = {pool.submit(_call_provider, p, f"Mejora la feature {feature['id']}: {feature['title']}", temp): p for p in providers}
            for future in as_completed(futures):
                p = futures[future]
                out = future.result()
                if out:
                    proposals.append(f"[{p['name']}] {out}")
        # Siempre incluye el analista local como base
        proposals.append(_local_proposer(feature, temp))
        # Agregar con Opus 4.8 (o heuristico)
        merged = _aggregate(proposals, feature, temp)
        score = _quality_score(merged)
        print(f"   agregado ({len(merged)} chars), score={score}/10")
        if score > best_score:
            best_score = score
            best = merged
        if not dry_run:
            _record({
                "ts": datetime.now(timezone.utc).isoformat(),
                "feature": feature["id"],
                "iteration": i,
                "temperature": round(temp, 2),
                "providers": [p["name"] for p in _available_providers()],
                "aggregator": "opus-4.8 (claude)" if _CLI and Path(_CLI).exists() else "local-heuristic",
                "score": score,
                "merged_len": len(merged),
            })
        if score >= _LOOP_CFG["quality_threshold"]:
            print(f"   ✓ calidad >= {_LOOP_CFG['quality_threshold']}, paro.")
            break
        temp = max(0.0, temp - _LOOP_CFG["temp_decay"])

    print(f"\n✅ Mejor merge (score {best_score}/10):\n{best[:800]}")
    if dry_run:
        print("(dry-run: no persisto cambios de estado)")
        return 0

    # Verify + persistir estado de la feature
    ok, detail = _verify()
    print(f"\n🧪 QA: {detail}")
    if ok and _feature_evidence_complete(feature):
        # QA green is necessary but not proof that implementation happened.
        # Only already-completed subtasks may close a feature.
        feature["status"] = "done"
        feature["progress"] = {"pct": 100}
        rm.save_roadmap(d)
        print(f"   → {feature['id']} marcada DONE + roadmap.json persistido")
        _record({"ts": datetime.now(timezone.utc).isoformat(), "event": "feature_done",
                 "feature": feature["id"]})
    else:
        reason = "QA no paso" if not ok else "quedan subtareas sin evidencia"
        feature["status"] = "in_progress"
        rm.save_roadmap(d)
        print(f"   ⚠ {reason}; {feature['id']} queda in_progress (no la marco done)")
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser(description="LucidFence /loop de mejora (MoA)")
    ap.add_argument("--feature", help="ID de feature a mejorar (p.ej. F1.2)")
    ap.add_argument("--max-iter", type=int, default=_LOOP_CFG["max_iterations"])
    ap.add_argument("--dry-run", action="store_true")
    controls = ap.add_mutually_exclusive_group()
    controls.add_argument("--disable", metavar="REASON", help="activa el kill switch persistente")
    controls.add_argument("--enable", action="store_true", help="reactiva /loop")
    args = ap.parse_args()
    if args.disable:
        _kill_switch().disable(args.disable); print("/loop deshabilitado"); return
    if args.enable:
        _kill_switch().enable(); print("/loop habilitado"); return
    sys.exit(run_loop(feature_id=args.feature, max_iter=args.max_iter, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
