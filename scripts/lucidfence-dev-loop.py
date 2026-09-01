#!/usr/bin/env python3
"""
lucidfence-dev-loop.py — Orquestador del daily loop de desarrollo autónomo.

Ejecuta en tres fases:
1. PLAN: Triaje de issues, asignación a agentes
2. EJECUTION: Dev-agent implementa, Reviewer revisa, Docs-agent documenta
3. AUTO-MEJRORA: Skill discovery desde @HermesWatcher, actualización de memoria

Úsalo con:
  python3 lucidfence-dev-loop.py --execute     # ejecutar loop completo
  python3 lucidfence-dev-loop.py --plan        # solo fase de plan
  python3 lucidfence-dev-loop.py --improve     # solo auto-mejora
  python3 lucidfence-dev-loop.py --status      # estado actual del repo
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Configuración ──────────────────────────────────────────────────────────

REPO_DIR = Path("/Users/adri/lucidfence")
AGENTS_DIR = Path("/Users/adri/.hermes/profiles")
LOOP_LOG = REPO_DIR / "docs/internal/loop-run-log.md"
MEMORY_DIR = REPO_DIR / "docs/internal/agent-memory"
ISSUE_TRIAGE_LOG = REPO_DIR / "docs/internal/issue_triage_log.md"
HERMESWATCHER_CACHE = REPO_DIR / "data/hermeswatcher_posts.json"

PYTHON = "/opt/homebrew/bin/python3.11"

# ── Helpers ─────────────────────────────────────────────────────────────────

def run(cmd: str, timeout: int = 60, cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Ejecutar comando, devolver (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            cwd=cwd or REPO_DIR
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)

def gh(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Ejecutar gh CLI."""
    return run(f"gh {' '.join(args)}", timeout=timeout)

def log(msg: str) -> None:
    """Log simple en stdout."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}")

def log_loop(msg: str) -> None:
    """Log en loop-run-log.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"- {ts} | L3 | {msg}\n"
    LOOP_LOG.write_text(LOOP_LOG.read_text() + entry) if LOOP_LOG.exists() else LOOP_LOG.write_text(entry)

def ensure_memory_dir() -> None:
    """Asegurar directorio de memoria de agentes."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def ensure_loop_log() -> None:
    """Asegurar loop-run-log.md."""
    if not LOOP_LOG.exists():
        LOOP_LOG.write_text(
            f"# Loop Run Log — LucidFence Dev Agents\n"
            f"Última ejecución: {datetime.now(timezone.utc).isoformat()}\n\n"
        )

def get_open_issues() -> list[dict]:
    """Obtener issues abiertas."""
    code, stdout, _ = gh(["issue", "list", "--state", "open", "--limit", "50", "--json",
                           "number,title,labels,state,createdAt,assignees,body"])
    if code != 0:
        return []
    try:
        return json.loads(stdout)
    except:
        return []

def get_open_prs() -> list[dict]:
    """Obtener PRs abiertas."""
    code, stdout, _ = gh(["pr", "list", "--state", "open", "--limit", "50", "--json",
                           "number,title,state,additions,deletions,files,url,headRefName"])
    if code != 0:
        return []
    try:
        return json.loads(stdout)
    except:
        return []

def get_pr_diff(pr_number: int) -> list[str]:
    """Obtener archivos del diff de un PR."""
    code, stdout, _ = gh(["pr", "diff", str(pr_number), "--name-only"])
    if code != 0:
        return []
    return [l.strip() for l in stdout.strip().split("\n") if l.strip()]

def get_pr_checks(pr_number: int) -> dict:
    """Obtener estado de checks de un PR."""
    code, stdout, _ = gh(["pr", "checks", str(pr_number), "--json", "name,status,conclusion"])
    if code != 0:
        return {}
    try:
        return json.loads(stdout)
    except:
        return {}

def is_pr_green(pr_number: int) -> bool:
    """Verificar si un PR tiene todos los checks en verde."""
    checks = get_pr_checks(pr_number)
    for check in checks.get("checks", []):
        if check.get("status") == "completed":
            if check.get("conclusion") != "success":
                return False
    return True

def create_pr(title: str, body: str, head: str, base: str = "main") -> Optional[int]:
    """Crear un PR."""
    code, stdout, stderr = gh([
        "pr", "create",
        "--title", title,
        "--body", body,
        "--head", head,
        "--base", base,
    ], timeout=30)
    if code == 0:
        # Extract PR number from output
        for line in stdout.split("\n"):
            if line.strip().startswith("#"):
                try:
                    return int(line.strip().lstrip("#").strip())
                except:
                    pass
        # Fallback: parse URL
        for line in stdout.split("\n"):
            if "github.com/adrimg3196/lucidfence/pull/" in line:
                import re
                m = re.search(r"pull/(\d+)", line)
                if m:
                    return int(m.group(1))
    log(f"ERROR creando PR: {stderr[:200]}")
    return None

def close_issue(issue_number: int) -> bool:
    """Cerrar un issue."""
    code, _, _ = gh(["issue", "close", str(issue_number)])
    return code == 0

def assign_issue(issue_number: int, assignee: str = "hermes-agent") -> bool:
    """Asignar un issue."""
    code, _, _ = gh(["issue", "assign", str(issue_number), assignee])
    return code == 0

# ── Fase 1: Plan ────────────────────────────────────────────────────────────

def fase_plan() -> dict:
    """Fase de planificación: triaje de issues, asignación."""
    log("=== FASE 1: PLAN ===")
    ensure_loop_log()
    ensure_memory_dir()

    issues = get_open_issues()
    prs = get_open_prs()

    log(f"Issues abiertas encontradas: {len(issues)}")
    log(f"PRs abiertas encontradas: {len(prs)}")

    # Triaje de issues
    triage_result = []
    for issue in issues:
        num = issue["number"]
        title = issue["title"]
        labels = [l["name"] for l in issue.get("labels", [])]
        assignees = [a["login"] for a in issue.get("assignees", [])]

        # Prioridad
        priority = "P4 — backlog"
        if "P1" in labels:
            priority = "P1 — crítico"
        elif "P2" in labels:
            priority = "P2 — alto"
        elif "P3" in labels:
            priority = "P3 — medio"

        # Categoría
        category = "general"
        if "bug" in labels:
            category = "bug"
        elif "documentation" in labels:
            category = "docs"
        elif any(x in labels for x in ["security", "risk", "Strix"]):
            category = "security"
        elif "cloud-state" in labels or "cloud" in labels:
            category = "cloud"
        elif "HERMES" in labels:
            category = "hermes"

        # Asignar si no tiene assignee
        if not assignees:
            # Decision: asignar a agente basado en categoría
            if category == "bug":
                assignee = "empresa-test-qa"
            elif category == "security":
                assignee = "empresa-security-soc"
            elif category == "docs":
                assignee = "empresa-seo-docs"
            elif category == "cloud":
                assignee = "empresa-devops-release"
            elif category == "hermes":
                assignee = "agente-hermes"
            else:
                assignee = "empresa-dev"

            code, _, _ = gh(["issue", "assign", str(num), assignee])
            if code == 0:
                log(f"  #{num} asignado a {assignee}")
                triage_result.append({
                    "number": num,
                    "title": title,
                    "priority": priority,
                    "category": category,
                    "assignee": assignee,
                    "action": "assigned"
                })
            else:
                triage_result.append({
                    "number": num,
                    "title": title,
                    "priority": priority,
                    "category": category,
                    "assignee": None,
                    "action": "failed_to_assign"
                })
        else:
            triage_result.append({
                "number": num,
                "title": title,
                "priority": priority,
                "category": category,
                "assignee": assignees[0],
                "action": "already_assigned"
            })

    # Log de triaje
    if ISSUE_TRIAGE_LOG.exists():
        ISSUE_TRIAGE_LOG.write_text(
            ISSUE_TRIAGE_LOG.read_text() +
            f"\n## Triaje {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        )
    else:
        ISSUE_TRIAGE_LOG.write_text(
            f"# Issue Triaje Log\n\n"
            f"Última ejecución: {datetime.now(timezone.utc).isoformat()}\n\n"
        )

    for item in triage_result:
        ISSUE_TRIAGE_LOG.write_text(
            ISSUE_TRIAGE_LOG.read_text() +
            f"- #{item['number']} [{item['priority']}] [{item['category']}] → {item['assignee'] or 'sin asignar'} — {item['action']}: {item['title'][:60]}\n"
        )

    log(f"Triaje completado: {len(triage_result)} issues procesados")
    log_loop(f"Fase 1 (Plan): {len(triage_result)} issues triados, {len(prs)} PRs abiertas")

    return {
        "issues": len(issues),
        "prs": len(prs),
        "triaged": len(triage_result),
    }

# ── Fase 2: Ejecución ───────────────────────────────────────────────────────

def fase_ejecucion() -> dict:
    """Fase de ejecución: dev-agent implementa, review, docs."""
    log("=== FASE 2: EJECUCIÓN ===")

    # Verificar qué issues tienen code-ready label o son bugs asignados a dev
    issues = get_open_issues()
    prs = get_open_prs()

    # Buscar issues de bug asignados a empresa-dev que no tengan PR asociado
    candidates = []
    for issue in issues:
        num = issue["number"]
        title = issue["title"]
        labels = [l["name"] for l in issue.get("labels", [])]
        assignees = [a["login"] for a in issue.get("assignees", [])]

        if "bug" in labels and "empresa-dev" in assignees:
            # Verificar si ya tiene PR que lo cierra
            has_pr = False
            for pr in prs:
                for closing in pr.get("closingIssuesReferences", []):
                    if closing["number"] == num:
                        has_pr = True
                        break
            if not has_pr:
                candidates.append(issue)

    log(f"Issues candidates para implementación: {len(candidates)}")

    executed = []
    for issue in candidates[:3]:  # Max 3 por ejecución
        num = issue["number"]
        title = issue["title"]

        log(f"  Implementando #{num}: {title[:60]}")

        # Ejecutar dev-agent contra este issue
        code, stdout, stderr = run(
            f"cd {REPO_DIR} && {PYTHON} scripts/dev-agent.py {num}",
            timeout=300
        )

        if code == 0:
            log(f"  ✓ #{num} implementado exitosamente")
            executed.append({"number": num, "status": "success"})
            log_loop(f"Fase 2 (Ejecución): Issue #{num} implementado por dev-agent")
        else:
            log(f"  ✗ #{num} falló: {stderr[:100]}")
            executed.append({"number": num, "status": "failed", "error": stderr[:100]})
            log_loop(f"Fase 2 (Ejecución): Issue #{num} falló — {stderr[:100]}")

    # Revisión de PRs nuevas
    new_prs = [pr for pr in prs if pr["number"] not in [377, 379]]  # Excluir PRs conocidas

    for pr in new_prs[:2]:
        num = pr["number"]
        log(f"  Revisando PR #{num}: {pr['title'][:60]}")

        if is_pr_green(num):
            # Dejar comentario constructivo
            code, _, _ = gh([
                "pr", "comment", str(num),
                "--body", textwrap.dedent(f"""
                ## Revisión automatizada

                ✅ Checks de CI: verdes
                ✅ Cambios: {pr['additions']}+/{pr['deletions']}- en {pr['files']} archivos
                ✅ Branch: {pr['headRefName']}

                Revisión inicial positiva. Se recomienda revisión humana para validación final.
                """).strip()
            ])
            if code == 0:
                log(f"  ✓ PR #{num} revisado")
                log_loop(f"Fase 2 (Ejecución): PR #{num} revisado por reviewer-agent")

    return {
        "candidates": len(candidates),
        "executed": len(executed),
        "prs_reviewed": len(new_prs[:2]),
    }

# ── Fase 3: Auto-mejora ─────────────────────────────────────────────────────

def fetch_hermeswatcher_posts() -> list[dict]:
    """Obtener posts recientes de @HermesWatcher."""
    import gzip
    import urllib.request
    import json as json_mod

    url = "https://nitter.net/api/v1/user/11/tweets?count=10&skip=0"
    # Fallback: usar X.com directamente
    url = "https://x.com/hermeswatcher?s=11"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "LucidFence-Dev-Agent/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json_mod.loads(resp.read().decode())
            return data.get("tweets", [])
    except Exception as e:
        log(f"  Error obteniendo posts de HermesWatcher: {e}")
        return []

def fase_auto_mejora() -> dict:
    """Fase de auto-mejora: skill discovery desde @HermesWatcher."""
    log("=== FASE 3: AUTO-MEJORА ===")

    posts = fetch_hermeswatcher_posts()
    log(f"Posts de @HermesWatcher encontrados: {len(posts)}")

    skills_found = []
    for post in posts[:5]:
        text = post.get("text", "")
        if "skill" in text.lower() or "plugin" in text.lower() or "hermes" in text.lower():
            skills_found.append({
                "text": text[:100],
                "url": f"https://x.com/hermeswatcher/status/{post.get('id', 'unknown')}",
            })
            log(f"  Skill candidates: {text[:80]}...")

    # Guardar en cache
    if HERMESWATCHER_CACHE.exists():
        cache = json.loads(HERMESWATCHER_CACHE.read_text())
    else:
        cache = {"posts": []}
    cache["posts"] = (cache.get("posts", []) + posts)[-50:]  # Keep last 50
    HERMESWATCHER_CACHE.write_text(json.dumps(cache, indent=2))

    # Actualizar memoria de agentes
    if skills_found:
        memory_file = MEMORY_DIR / "skill-discovery.md"
        memory_file.write_text(
            memory_file.read_text() +
            f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
            f"{len(skills_found)} skills candidates encontrados:\n\n"
            + "\n".join(f"- {s['text'][:80]}..." for s in skills_found)
            + "\n"
        )

    log_loop(f"Fase 3 (Auto-mejora): {len(skills_found)} skills candidates detectados")

    return {
        "posts": len(posts),
        "skills_candidates": len(skills_found),
    }

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="LucidFence Dev Loop — Daily autonomous development")
    parser.add_argument("--execute", action="store_true", help="Ejecutar loop completo (plan+exec+improve)")
    parser.add_argument("--plan", action="store_true", help="Solo fase de planificación")
    parser.add_argument("--exec", action="store_true", help="Solo fase de ejecución")
    parser.add_argument("--improve", action="store_true", help="Solo auto-mejora (skill discovery)")
    parser.add_argument("--status", action="store_true", help="Ver estado actual del repo")
    parser.add_argument("--demo", action="store_true", help="Ejecutar demo en vivo")

    args = parser.parse_args()

    if not any([args.execute, args.plan, args.exec, args.improve, args.demo]):
        parser.print_help()
        return

    ensure_loop_log()
    ensure_memory_dir()

    log("=" * 60)
    log("LUCIDFENCE DEV LOOP — Iniciando")
    log(f"Repo: {REPO_DIR}")
    log(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    log("=" * 60)

    results = {}

    if args.plan or args.execute:
        results["plan"] = fase_plan()

    if args.exec or args.execute:
        results["execution"] = fase_ejecucion()

    if args.improve or args.execute:
        results["improvement"] = fase_auto_mejora()

    if args.demo:
        log("=== DEMO EN VIVO ===")
        log("Ejecutando ciclo completo de mejora...")
        results["demo"] = {
            "status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # Ejemplo: implementar un issue pequeño
        code, stdout, stderr = run(
            f"cd {REPO_DIR} && {PYTHON} scripts/dev-agent.py 2>&1 | tail -5",
            timeout=120
        )
        results["demo"]["output"] = stdout[-500:] if stdout else stderr[:500]

    # Resumen final
    log("")
    log("=" * 60)
    log("RESUMEN DEL LOOP")
    log("=" * 60)
    for phase, result in results.items():
        log(f"  {phase}: {json.dumps(result, indent=2)}")
    log("=" * 60)

    log_loop(f"Loop completado: {json.dumps(results)}")

if __name__ == "__main__":
    main()
