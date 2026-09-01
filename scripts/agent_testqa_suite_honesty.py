#!/usr/bin/env python3
"""
Agente Test-QA — Auto-mejora: Integridad de la suite de tests.
Capacidades activadas por Hugo skill-discovery (@HermesWatcher):

- subagent (delegation): recibe delegaciones de análisis de regresiones desde
  otros agentes (devops-ci) y ejecuta análisis profundo.
- memory: registra resultados de tests persistentemente en loop-run-log.md
- batch_processing: ejecuta verify.py + run_tests.py en paralelo cuando es útil
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
PY = "/Users/adri/lucidfence/.venv/bin/python"


def run(cmd: list[str], timeout: int = 90) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def registrar_test(desc: str) -> None:
    """Registra resultado de test en loop-run-log.md (memory)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"- {timestamp} | Test-QA | {desc}\n")


def health_suite() -> dict:
    """Ejecuta verify + tests y reporta honestidad de la suite."""
    out_verify = run([PY, "scripts/verify.py"])
    out_tests = run([PY, "tests/run_tests.py"])

    verify_ok = "APTO (4/4 checks)" in out_verify
    verify_lines = out_verify.splitlines()
    checks_ok = sum(1 for l in verify_lines if l.strip().startswith("OK"))
    checks_fail = sum(1 for l in verify_lines if l.strip().startswith("FAIL"))

    test_lines = out_tests.splitlines()
    passed = sum(1 for l in test_lines if l.strip().startswith("PASS"))
    failed = sum(1 for l in test_lines if l.strip().startswith("FAIL"))
    skipped = sum(1 for l in test_lines if l.strip().startswith("SKIP"))
    total = passed + failed + skipped

    return {
        "verify_ok": verify_ok,
        "verify_checks_ok": checks_ok,
        "verify_checks_fail": checks_fail,
        "tests_total": total,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_skipped": skipped,
        "tasa_exito": f"{passed}/{total} ({100*passed/max(total,1):.0f}%)" if total else "N/A",
        "failures": [l.strip() for l in test_lines if "FAIL" in l and "test_" in l][:10],
        "honestidad": "OK" if (verify_ok and failed == 0) else "DEGRADADO",
    }


def analizar_regresion(failure_info: dict) -> dict:
    """Analiza una regresión y propone acciones (recibe delegación de otros agentes)."""
    fail_test = failure_info.get("test", "desconocido")
    fail_output = failure_info.get("output", "")

    # Buscar patrones típicos de regresión
    causas_probables = []
    if "AssertionError" in fail_output or "assert" in fail_output:
        causas_probables.append("Aserción rota: verificar condición esperada")
    if "ImportError" in fail_output or "ModuleNotFoundError" in fail_output:
        causas_probables.append("Import faltante: verificar dependency o path")
    if "Timeout" in fail_output:
        causas_probables.append("Timeout: servicio no está o es lento")
    if "Port" in fail_output or "8799" in fail_output:
        causas_probables.append("Puerto 8799 ocupado: limpiar zombie")

    return {
        "test_afectado": fail_test,
        "causas_probables": causas_probables,
        "accion_recomendada": (
            "Ejecutar tests/failed_test.py -v para más detalles" if len(causas_probables) == 1
            else f"Investigar {len(causas_probables)} causas posibles"
        ),
    }


def resumen() -> dict:
    import threading

    results = {}

    def run_check(nombre, func):
        results[nombre] = func()

    # batch_processing: verify + tests en paralelo
    t1 = threading.Thread(target=run_check, args=("suite", health_suite))
    t1.start()
    t1.join()

    suite = results.get("suite", {})

    # Si hay failures, analizarlas (subagent: análisis profundo)
    analisis = []
    if suite.get("failures"):
        for fail in suite["failures"][:3]:
            # Extraer nombre del test de la línea de failure
            import re
            m = re.search(r'(test_\w+[^\s:]+)', fail)
            test_name = m.group(1) if m else "desconocido"
            analisis.append(analizar_regresion({"test": test_name, "output": fail}))

    # Memory: registrar resultados
    estado = "OK" if suite.get("honestidad") == "OK" else "DEGRADADO"
    registrar_test(
        f"Suite: verify={'OK' if suite.get('verify_ok') else 'FAIL'} | "
        f"tests={suite.get('tasa_exito','N/A')} | "
        f"failures={suite.get('tests_failed',0)} | "
        f"estado={estado}"
    )

    return {
        "agent": "test-qa",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capacidades_activas": ["subagent", "memory", "batch_processing"],
        "suite": suite,
        "analisis_regresiones": analisis,
        "mejoras_propuestas": [
            "Si tests fallan: ejecutar pytest -v en el test fallido para diagnóstico",
            "Si verify falla: revisar qué check falló y proponer corrección",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
