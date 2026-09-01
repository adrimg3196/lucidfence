#!/usr/bin/env python3
"""
Agente DevOps-Release — Auto-mejora: Salud de CI y pipeline.
Capacidades activadas por Hugo skill-discovery (@HermesWatcher):

- subagent (delegation): delega análisis de regressions a test-qa
- memory: registra estado de CI persistentemente en loop-run-log.md
- batch_processing: ejecuta verify + tests + git-status en paralelo
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
PY = "/Users/adri/lucidfence/.venv/bin/python"


def run(cmd: list[str], timeout: int = 60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def registrar_ci(desc: str) -> None:
    """Registra evento de CI en loop-run-log.md (memory)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"- {timestamp} | DevOps-CI | {desc}\n")


def health_verify() -> dict:
    out = run([PY, "scripts/verify.py"])
    resultado = "APTO" if "APTO (4/4 checks)" in out else "FALLO"
    lines = out.splitlines()
    checks_ok = sum(1 for l in lines if l.strip().startswith("OK"))
    checks_fail = sum(1 for l in lines if l.strip().startswith("FAIL"))
    return {
        "verify_resultado": resultado,
        "checks_ok": checks_ok,
        "checks_fail": checks_fail,
        "detalle": [l.strip() for l in lines if l.strip() and ("OK" in l or "FAIL" in l or "APTO" in l or "FALLO" in l)][:10],
    }


def health_tests() -> dict:
    out = run([PY, "tests/run_tests.py"])
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
        "failures": [l.strip() for l in lines if "FAIL" in l and "test_" in l][:5],
    }


def health_git() -> dict:
    branch = run(["git", "branch", "--show-current"]).strip()
    dirty = run(["git", "status", "--short"]).strip()
    recent = run(["git", "log", "--all", "--oneline", "-5"]).strip()
    return {
        "branch": branch,
        "dirty": "SI" if dirty else "NO",
        "files_dirty": len(dirty.splitlines()) if dirty else 0,
        "commits_recientes": recent.splitlines() if recent else [],
    }


def delegar_regresion(failures: list[str]) -> list[str]:
    """Delegar análisis de regresiones a test-qa (subagent)."""
    if not failures:
        return []
    try:
        result = subprocess.run(
            [PY, "scripts/agent_testqa_suite_honesty.py"],
            capture_output=True, text=True, timeout=60, cwd=REPO
        )
        if result.returncode == 0:
            return [f"Regresión delegada a test-qa: {failures[0][:80]}"]
    except Exception:
        pass
    return []


def resumen() -> dict:
    import threading

    results = {}

    def run_check(nombre, func):
        results[nombre] = func()

    # batch_processing: ejecutar verify + tests + git-status en paralelo
    t1 = threading.Thread(target=run_check, args=("verify", health_verify))
    t2 = threading.Thread(target=run_check, args=("tests", health_tests))
    t3 = threading.Thread(target=run_check, args=("git", health_git))
    t1.start(); t2.start(); t3.start()
    t1.join(); t2.join(); t3.join()

    verify = results.get("verify", {})
    tests = results.get("tests", {})
    git = results.get("git", {})

    # Subagent: delegar regresiones detectadas
    regresiones_delegadas = delegar_regresion(tests.get("failures", []))

    # Memory: registrar en loop-log
    estado = "OK" if verify.get("verify_resultado") == "APTO" and tests.get("tests_failed", 0) == 0 else "DEGRADADO"
    registrar_ci(
        f"CI: verify={verify.get('verify_resultado','?')} | "
        f"tests={tests.get('tasa_exito','N/A')} | "
        f"branch={git.get('branch','?')} | "
        f"dirty={git.get('dirty','?')} | "
        f"estado={estado}" +
        (f" | delegadas: {len(regresiones_delegadas)}" if regresiones_delegadas else "")
    )

    return {
        "agent": "devops-ci",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capacidades_activas": ["subagent", "memory", "batch_processing"],
        "verify": verify,
        "tests": tests,
        "git": git,
        "regresiones_delegadas": regresiones_delegadas,
        "mejoras_propuestas": [
            "Si verify falla: investigar qué check falló y proponer fix",
            "Si tests fallan: analizar regressions y proponer rollback si es crítico",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
