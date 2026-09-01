#!/usr/bin/env python3
"""
Agente Desarrollador simplificado — toma un issue y crea investigación + PR.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/adri/lucidfence")
PY = "/opt/homebrew/bin/python3.11"


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(REPO))
        return r
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


def gh(*args):
    r = run(f"gh {' '.join(args)}", timeout=30)
    return r.stdout.strip() if r.returncode == 0 else ""


def gh_json(*args, fields=""):
    cmd = f"gh {' '.join(args)}"
    if fields:
        cmd += f" --json {fields}"
    r = run(cmd, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except:
        return None


def git(*args):
    r = run(f"git {' '.join(args)}", timeout=30)
    return r.stdout.strip() if r.returncode == 0 else ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/developer_agent.py <issue-number>")
        sys.exit(1)

    num = int(sys.argv[1])
    branch = f"dev/{num}-auto-impl"

    print(f"[developer_agent] Issue #{num}")

    # Crear branch
    git("checkout", "-b", branch)
    print(f"  Branch: {branch}")

    # Obtener issue
    issue = gh_json("issue", "view", str(num), fields="title,body")
    title = issue.get("title", f"Issue #{num}") if issue else f"Issue #{num}"
    body = issue.get("body", "") if issue else ""

    # Crear investigación
    research_dir = REPO / "docs" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40]
    doc = research_dir / f"proposal-{num}-{slug}.md"

    doc.write_text(f"""# Investigación: {title}

**Issue:** #{num}

{body[:500] if body else 'Ver el issue para detalles.'}

---

*developer_agent el {datetime.now(timezone.utc).strftime('%Y-%m-%d')}*
""")
    git("add", str(doc))
    print(f"  Doc: {doc.name}")

    # Commit
    git("add", "-A")
    git("commit", "-m", f"docs(research): investigación issue #{num}",
        "-m", "Co-authored-by: Hermes Agent <hermes-agent@nousresearch.com>")

    # Push
    r = run(f"git push -u origin {branch}", timeout=60)
    if r.returncode != 0:
        print(f"  Push falló, intentando forzado...")
        run(f"git push -f -u origin {branch}", timeout=60)

    # PR
    body_pr = f"""## Resumen

Investigación automática para issue #{num}.

Closes #{num}
"""
    pr_out = gh("pr", "create", "--title", f"Auto-investigación #{num}",
                "--body", body_pr, "--head", branch, "--base", "main")
    if pr_out and ("pull/" in pr_out):
        print(f"  PR creado")
    else:
        print(f"  PR: {pr_out[:100] if pr_out else 'N/A'}")

    # Volver
    git("checkout", "-")
    print(f"[developer_agent] Completado")
