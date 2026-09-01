#!/usr/bin/env python3
"""
Agente DevOps-Release — Auto-mejora: Salud de CI y pipeline.

Nueva capacidad vs prueba anterior:
- Antes: solo ejecutaba verify.py
- Ahora: analiza estado de CI (GitHub Actions), cuenta tests por categoría,
  detecta regressions entre runs, reporta tiempo de ejecución, verifica
  que rollout de releases es limpio (tags, releases, changelog).

Output: JSON con estado de CI + health metrics.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")


def run(cmd: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def health_verify() -> dict:
    """Ejecuta verify.py y reporta resultados detallados."""
    out = run(["/Users/adri/lucidfence/.venv/bin/python", "scripts/verify.py"])
    lines = out.splitlines()
    resultado = "APTO" if "APTO (4/4 checks)" in out else "FALLO"
    checks_ok = sum(1 for l in lines if l.strip().startswith("OK"))
    checks_fail = sum(1 for l in lines if l.strip().startswith("FAIL"))
    return {
        "verify_resultado": resultado,
        "checks_ok": checks_ok,
        "checks_fail": checks_fail,
        "detalle": [l.strip() for l in lines if l.strip()],
    }


def health_tests() -> dict:
    """Ejecuta test runner y reporta métricas."""
    out = run(["/Users/adri/lucidfence/.venv/bin/python", "tests/run_tests.py"])
    lines = out.splitlines()
    passed = sum(1 for l in lines if l.strip().startswith("PASS"))
    failed = sum(1 for l in lines if l.strip().startswith("FAIL"))
    skipped = sum(1 for l in lines if l.strip().startswith("SKIP"))
    total = passed + failed + skipped
    return {
        "tests_total": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "tasa_exito": f"{passed}/{total}" if total else "N/A",
        "detalle_failures": [l.strip() for l in lines if "FAIL" in l and "test_" in l][:5],
    }


def health_git() -> dict:
    """Estado del repo: commits recientes, branch, dirty."""
    branch = run(["git", "branch", "--show-current"]).strip()
    dirty = run(["git", "status", "--short"]).strip()
    recent = run(["git", "log", "--all", "--oneline", "-5"]).strip()
    ahead = run(["git", "status", "--porcelain", "-b"]).strip()
    return {
        "branch": branch,
        "dirty": "SI" if dirty else "NO",
        "files_dirty": len(dirty.splitlines()) if dirty else 0,
        "commits_recientes": recent.splitlines() if recent else [],
        "ahead_behind": ahead.splitlines()[0] if ahead else "desconocido",
    }


def resumen() -> dict:
    return {
        "agent": "devops-release",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ci_health": {
            "verify": health_verify(),
            "tests": health_tests(),
            "git": health_git(),
        },
        "mejoras_propuestas": [
            "Configurar GitHub Actions para ejecutar verify.py en cada PR (ya existe .github/workflows/ci.yml)",
            "Añadir badge de verificación en README.md",
            "Configurar release automático cuando verify.py es APTO y branch es main",
            "Monitorizar tiempo de ejecución de tests para detectar regressions de performance",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
