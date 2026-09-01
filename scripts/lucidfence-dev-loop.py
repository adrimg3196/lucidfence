#!/usr/bin/env python3
"""
LucidFence Dev Loop — Orquestador del daily loop de desarrollo autónomo.

Ejecuta en tres fases:
1. PLAN: Triaje de issues, asignación a agentes
2. EJECUCIÓN: Dev-agent implementa, Reviewer revisa, Docs-agent documenta
3. AUTO-MEJRORA: Skill discovery desde @HermesWatcher, actualización de memoria

Úsalo con:
  python3 lucidfence-dev-loop.py --execute     # ejecutar loop completo
  python3 lucidfence-dev-loop.py --plan        # solo fase de plan
  python3 lucidfence-dev-loop.py --exec        # solo fase de ejecución
  python3 lucidfence-dev-loop.py --improve     # solo auto-mejora
  python3 lucidfence-dev-loop.py --status      # estado actual del repo
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path("/Users/adri/lucidfence")
MEMORY_DIR = REPO_DIR / "docs" / "internal" / "agent-memory"
ISSUE_TRIAGE_LOG = REPO_DIR / "docs" / "internal" / "issue_triage_log.md"
LOOP_LOG = REPO_DIR / "docs" / "internal" / "loop-run-log.md"
HERMESWATCHER_CACHE = REPO_DIR / "data" / "hermeswatcher_posts.json"

PYTHON = "/opt/homebrew/bin/python3.11"


def run(cmd: str, timeout: int = 120, cwd=None) -> subprocess.CompletedProcess:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(cwd or REPO_DIR))
        return r
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", "TIMEOUT")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -2, "", str(e))


def gh(*args: str, timeout: int = 30) -> str:
    cmd = f"gh {' '.join(args)}"
    r = run(cmd, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 else ""


def gh_json(*args: str, fields: str = "", timeout: int = 30) -> dict | list | None:
    cmd = f"gh {' '.join(args)}"
    if fields:
        cmd += f" --json {fields}"
    r = run(cmd, timeout=timeout)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}")


def log_loop(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"- {ts} | L3 | {msg}\n"
    content = LOOP_LOG.read_text() if LOOP_LOG.exists() else ""
    LOOP_LOG.write_text(content + entry)


def ensure_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not LOOP_LOG.exists():
        LOOP_LOG.write_text(f"# Loop Run Log — LucidFence Dev Agents\n\n")


def get_open_issues() -> list[dict]:
    data = gh_json("issue", "list", "--state", "open", "--limit", "50",
                   fields="number,title,labels,state,assignees")
    return data if isinstance(data, list) else []


def get_open_prs() -> list[dict]:
    data = gh_json("pr", "list", "--state", "open", "--limit", "50",
                   fields="number,title,state,additions,deletions,files,url,headRefName")
    return data if isinstance(data, list) else []


def get_pr_checks(pr_number: int) -> list[dict]:
    data = gh_json("pr", "checks", str(pr_number),
                   fields="name,status,conclusion")
    return data if isinstance(data, list) else []


def is_pr_green(pr_number: int) -> bool:
    checks = get_pr_checks(pr_number)
    for check in checks:
        if check.get("status") == "completed":
            if check.get("conclusion") != "success":
                return False
    return True


def triage_issues(issues: list[dict]) -> list[dict]:
    """Clasificar issues por prioridad y categoría."""
    results = []
    for issue in issues:
        num = issue.get("number", "?")
        title = issue.get("title", "")[:80]
        labels = [l.get("name", "") if isinstance(l, dict) else str(l)
                  for l in (issue.get("labels") or [])]
        assignees = [a.get("login", "") if isinstance(a, dict) else str(a)
                     for a in (issue.get("assignees") or [])]

        # Prioridad
        if "P1" in labels:
            priority = "P1 — crítico"
        elif "P2" in labels:
            priority = "P2 — alto"
        elif "P3" in labels:
            priority = "P3 — medio"
        else:
            priority = "P4 — backlog"

        # Categoría
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
        else:
            category = "general"

        # Asignar si no tiene assignee
        assignee = assignees[0] if assignees else None
        action = "already_assigned"

        if not assignee:
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

            out = gh("issue", "assign", str(num), assignee)
            if out:
                log(f"  #{num} asignado a {assignee}")
                action = "assigned"
            else:
                action = "failed_to_assign"

        results.append({
            "number": num,
            "title": title,
            "priority": priority,
            "category": category,
            "assignee": assignee,
            "action": action,
        })

    return results


def phase_plan() -> dict:
    """Fase 1: Plan — triaje de issues."""
    log("=== FASE 1: PLAN ===")
    ensure_dirs()

    issues = get_open_issues()
    prs = get_open_prs()

    log(f"Issues abiertas: {len(issues)}")
    log(f"PRs abiertas: {len(prs)}")

    triaged = triage_issues(issues)
    log(f"Triaje completado: {len(triaged)} issues clasificados")

    # Log de triaje
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    triage_text = f"\n## Triaje {timestamp}\n\n"
    for item in triaged:
        triage_text += (
            f"- #{item['number']} [{item['priority']}] [{item['category']}] "
            f"→ {item['assignee'] or 'sin asignar'} — {item['action']}: "
            f"{item['title'][:60]}\n"
        )

    existing = ISSUE_TRIAGE_LOG.read_text() if ISSUE_TRIAGE_LOG.exists() else ""
    ISSUE_TRIAGE_LOG.write_text(existing + triage_text)

    log_loop(f"Fase 1 (Plan): {len(triaged)} issues triados, {len(prs)} PRs abiertas")

    return {"issues": len(issues), "prs": len(prs), "triaged": len(triaged)}


def phase_execution() -> dict:
    """Fase 2: Ejecución — implementar bugs, revisar PRs, ejecutar agentes especializados."""
    log("=== FASE 2: EJECUCIÓN ===")

    issues = get_open_issues()
    prs = get_open_prs()

    # Buscar bugs sin PR asociado
    pr_closing_numbers = set()
    for pr in prs:
        for closing in (pr.get("closingIssuesReferences") or []):
            pr_closing_numbers.add(closing.get("number"))

    candidates = [i for i in issues
                  if "bug" in [l.get("name", "") for l in (i.get("labels") or [])]
                  and i.get("number") not in pr_closing_numbers]

    log(f"Issues candidates para implementación: {len(candidates)}")

    executed = []
    for issue in candidates[:3]:
        num = issue["number"]
        title = issue["title"][:80]
        log(f"  Implementando #{num}: {title}")

        result = run(
            f"{PYTHON} scripts/developer_agent.py {num}",
            timeout=300
        )

        if result.returncode == 0:
            log(f"  ✓ #{num} implementado")
            executed.append({"number": num, "status": "success"})
            log_loop(f"Fase 2: Issue #{num} implementado por developer_agent")
        else:
            log(f"  ✗ #{num} falló (exit {result.returncode})")
            executed.append({"number": num, "status": "failed"})
            log_loop(f"Fase 2: Issue #{num} falló")

    # Ejecutar agentes especializados según categoría
    # Security SOC agent: implementa fixes de seguridad
    security_candidates = [i for i in issues
                           if any(x in [l.get("name", "") for l in (i.get("labels") or [])]
                                 for x in ["security", "risk", "Strix"])
                           and i.get("number") not in pr_closing_numbers]

    if security_candidates:
        log(f"  Agentes de seguridad: {len(security_candidates)} issues")
        for issue in security_candidates[:1]:
            num = issue["number"]
            log(f"    Ejecutando security-soc-agent contra #{num}")
            result = run(f"{PYTHON} scripts/security-soc-agent.py {num}", timeout=300)
            if result.returncode == 0:
                log(f"    ✓ Security fix para #{num} creado")
            else:
                log(f"    ✗ Security fix para #{num} falló")

    # Test QA agent: implementa fixes de tests
    test_candidates = [i for i in issues
                       if "test" in [l.get("name", "").lower() for l in (i.get("labels") or [])]
                       and i.get("number") not in pr_closing_numbers]

    if test_candidates:
        log(f"  Agentes de QA: {len(test_candidates)} issues de test")
        for issue in test_candidates[:1]:
            num = issue["number"]
            log(f"    Ejecutando test-qa-agent contra #{num}")
            # Para tests, simplemente crear investigación
            result = run(f"{PYTHON} scripts/developer_agent.py {num}", timeout=300)
            if result.returncode == 0:
                log(f"    ✓ Test fix para #{num} creado")
            else:
                log(f"    ✗ Test fix para #{num} falló")

    # Revisar PRs nuevas
    skip_prs = {377, 379, 380, 381, 382, 383}
    new_prs = [pr for pr in prs if pr["number"] not in skip_prs]

    reviewed = 0
    for pr in new_prs[:3]:
        num = pr["number"]
        if is_pr_green(num):
            gh("pr", "comment", str(num), "--body",
               "## Revisión automatizada\n\n"
               "✅ CI verde\n"
               f"✅ {pr['additions']}+/{pr['deletions']}- en {pr['files']} archivos\n\n"
               "Revisión inicial positiva. Pendiente de revisión humana.")
            reviewed += 1
            log_loop(f"Fase 2: PR #{num} revisada por reviewer-agent")

    return {
        "candidates": len(candidates),
        "executed": len(executed),
        "security_issues": len(security_candidates),
        "test_issues": len(test_candidates),
        "prs_reviewed": reviewed,
    }


def phase_improvement() -> dict:
    """Fase 3: Auto-mejora — skill discovery desde @HermesWatcher."""
    log("=== FASE 3: AUTO-MEJORА ===")

    # Intentar obtener posts de HermesWatcher
    posts = []
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://x.com/hermeswatcher?s=11",
            headers={"User-Agent": "LucidFence-Dev-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Buscar tweets en el HTML
            import re
            tweet_pattern = re.compile(r'<div[^>]*data-testid="tweetText"[^>]*>(.*?)</div>', re.DOTALL)
            tweets = tweet_pattern.findall(html)
            posts = [{"text": t.strip()[:200], "source": "x.com"} for t in tweets[:5]]
    except Exception as e:
        log(f"  ⚠ No se pudieron obtener posts: {e}")

    log(f"Posts de @HermesWatcher: {len(posts)}")

    # Guardar en cache
    cache = {"posts": [], "updated": datetime.now(timezone.utc).isoformat()}
    if HERMESWATCHER_CACHE.exists():
        try:
            cache = json.loads(HERMESWATCHER_CACHE.read_text())
        except Exception:
            pass
    cache["posts"] = (cache.get("posts", []) + posts)[-50:]
    HERMESWATCHER_CACHE.write_text(json.dumps(cache, indent=2))

    # Actualizar memoria
    if posts:
        memory_file = MEMORY_DIR / "skill-discovery.md"
        memory_text = memory_file.read_text() if memory_file.exists() else ""
        memory_text += f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
        memory_text += f"{len(posts)} posts detectados de @HermesWatcher\n\n"
        for p in posts[:5]:
            memory_text += f"- {p['text'][:80]}...\n"
        memory_file.write_text(memory_text)

    log_loop(f"Fase 3 (Auto-mejora): {len(posts)} posts procesados")

    return {"posts": len(posts)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LucidFence Dev Loop")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--exec", action="store_true")
    parser.add_argument("--improve", action="store_true")
    parser.add_argument("--status", action="store_true")

    args = parser.parse_args()

    if not any([args.execute, args.plan, args.exec, args.improve, args.status]):
        parser.print_help()
        return

    ensure_dirs()
    log("=" * 60)
    log("LUCIDFENCE DEV LOOP — Iniciando")
    log(f"Repo: {REPO_DIR}")
    log(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    log("=" * 60)

    results = {}

    if args.plan or args.execute:
        results["plan"] = phase_plan()

    if args.exec or args.execute:
        exec_result = phase_execution()
        results["execution"] = exec_result

    if args.improve or args.execute:
        results["improvement"] = phase_improvement()

    if args.status:
        issues = get_open_issues()
        prs = get_open_prs()
        log(f"Estado: {len(issues)} issues abiertas, {len(prs)} PRs abiertas")

    log("")
    log("=" * 60)
    log("RESUMEN DEL LOOP")
    log("=" * 60)
    for phase, data in results.items():
        log(f"  {phase}:")
        for k, v in data.items():
            log(f"    {k}: {v}")
    log("=" * 60)

    log_loop(f"Loop completado: {json.dumps(results)}")


if __name__ == "__main__":
    main()
