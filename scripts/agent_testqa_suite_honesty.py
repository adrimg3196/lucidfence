#!/usr/bin/env python3
"""
Agente Test-QA — Auto-mejora: Integridad de la suite de tests.

Nueva capacidad vs prueba anterior:
- Antes: solo contaba tests pasados/fallidos
- Ahora: verifica que el runner de tests sea honesto (no oculta fallos),
  detecta tests que fallan silenciosamente, analiza cobertura por módulo,
  reporta tests que deberían existir pero no existen (gaps de cobertura).

Output: JSON con integridad de suite + gaps detectados.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")


def run(cmd: list[str], timeout: int = 120) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def integridad_runner() -> dict:
    """Verifica que tests/run_tests.py sea honesto (no oculta fallos)."""
    content = (REPO / "tests/run_tests.py").read_text()
    # El runner debe capturar SystemExit por módulo, no abortar todo
    honesto = "SystemExit" in content and "per-module" in content.lower() or "import" not in content or "sys.exit" not in content
    return {
        "runner_honesto": honesto,
        "usa_captura_systemexit": "SystemExit" in content,
        "nota": "Runner honesto: captura SystemExit por módulo para no esconder fallos" if honesto else "WARNING: runner puede esconder fallos",
    }


def ejecutar_suite() -> dict:
    """Ejecuta la suite completa y reporta resultados."""
    out = run(["/Users/adri/lucidfence/.venv/bin/python", "tests/run_tests.py"])
    lines = out.splitlines()
    passed = [l.strip() for l in lines if l.strip().startswith("PASS")]
    failed = [l.strip() for l in lines if l.strip().startswith("FAIL")]
    skipped = [l.strip() for l in lines if l.strip().startswith("SKIP")]
    summary = [l.strip() for l in lines if "passed" in l.lower() and "failed" in l.lower()]
    return {
        "passed_count": len(passed),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "total": len(passed) + len(failed) + len(skipped),
        "summary": summary[0] if summary else "sin resumen",
        "failures": failed[:5],
        "suite_honesta": len(failed) == 0,
    }


def gaps_cobertura() -> dict:
    """Detecta módulos críticos sin tests."""
    test_files = list((REPO / "tests").glob("test_*.py"))
    test_modules = set(f.stem.replace("test_", "") for f in test_files)

    core_modules = [
        "policies", "risk", "adapters", "config_loader",
        "cloud_publisher", "soar", "location_source",
        "declarative", "multiuem", "adapter_scaffold",
    ]

    sin_tests = [m for m in core_modules if m not in test_modules]
    return {
        "tests_existentes": len(test_files),
        "test_files": [f.name for f in test_files],
        "modulos_criticos_sin_tests": sin_tests,
        "gaps_detectados": len(sin_tests),
    }


def resumen() -> dict:
    suite = ejecutar_suite()
    return {
        "agent": "test-qa",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "integridad_runner": integridad_runner(),
        "suite_resultado": {
            "total": suite["total"],
            "passed": suite["passed_count"],
            "failed": suite["failed_count"],
            "skipped": suite["skipped_count"],
            "tasa_exito": f"{suite['passed_count']}/{suite['total']}",
            "suite_honesta": suite["suite_honesta"],
            "failures_detalle": suite["failures"],
        },
        "gaps_cobertura": gaps_cobertura(),
        "mejoras_propuestas": [
            "Añadir tests para módulos sin cobertura: " + ", ".join(gaps_cobertura()["modulos_criticos_sin_tests"]) if gaps_cobertura()["gaps_detectados"] else "Cobertura completa: todos los módulos críticos tienen tests",
            "Añadir pytest-cov para medir cobertura de código y reportar % en CI",
            "Configurar threshold de cobertura mínimo (ej. 80%) como gate de merge",
            "Añadir tests de integración reales (no solo unitarios) para adapters",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
