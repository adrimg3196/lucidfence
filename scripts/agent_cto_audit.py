#!/usr/bin/env python3
"""
Agente CTO — Auto-mejora: Auditoría de seguridad proactiva.
Capacidades activadas por Hugo skill-discovery (@HermesWatcher):

- subagent (delegation): cuando detecta hallazgos complejos,
  delega investigación a agentos especializados vía subprocess.
- memory: registra hallazgos persistentes en loop-run-log.md
  (no solo stdout) para contexto cross-sesión.
- batch_processing: ejecuta verificaciones independientes en paralelo
  cuando es posible (deps, secretos, puertos son independientes).
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
PY = "/Users/adri/lucidfence/.venv/bin/python"


def run(cmd: list[str], timeout: int = 30) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return f"TIMEOUT: {' '.join(cmd)}"
    except Exception as e:
        return f"ERROR: {e}"


def registrar_en_loop(entry: str) -> None:
    """Registra un hallazgo en loop-run-log.md (capacidad memory)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"- {timestamp} | Agente CTO | {entry}\n")


def auditoria_dependencias() -> dict:
    deps = {}
    try:
        txt = (REPO / "pyproject.toml").read_text()
        in_deps = False
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("[") and "dependencies" in line:
                in_deps = True
                continue
            if line.startswith("[") and "dependencies" not in line:
                in_deps = False
                continue
            if in_deps and line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 1:
                    deps[parts[0]] = parts[1] if len(parts) > 1 else "*"
    except Exception as e:
        return {"error": str(e)}

    # Verificar si pip-audit está disponible
    pip_audit = run([PY, "-m", "pip_audit", "--version"], timeout=5)
    tiene_pip_audit = "usage:" not in pip_audit and "ERROR" not in pip_audit

    return {
        "dependencias_encontradas": len(deps),
        "dependencias": list(deps.keys()),
        "pip_audit_disponible": tiene_pip_audit,
        "nivel": "INFO",
        "nota": "pip-audit disponible" if tiene_pip_audit else "Instalar pip-audit para escaneo de CVEs",
    }


def detectar_secretos() -> dict:
    """Busca patrones reales de secrets en el repo (tokens, claves, passwords).

    Excluye comentarios, strings de ejemplo/doc, patrones en tests/fixtures.
    """
    secretos = []
    import re

    # Regex más estricto: solo línea que no sea comentario ni test
    pat = re.compile(
        r'^[^#\"\'\n]*?(?:api[_-]?key|apikey|secret|password|passwd|token|aws_secret|private_key)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})',
        re.IGNORECASE | re.MULTILINE,
    )

    for f in REPO.rglob("*.py"):
        path_str = str(f)
        # Excluir .venv, __pycache__, tests/fixtures, ejemplos
        if any(x in path_str for x in [".venv", "__pycache__", "tests/", "test_", "/fixtures/", "example"]):
            continue
        try:
            content = f.read_text()
            for m in pat.finditer(content):
                # Verificar que el archivo no sea un test/fixture
                if "test" in f.name.lower() or "fixture" in f.name.lower():
                    continue
                secretos.append(f"{f.relative_to(REPO)}:{m.group(0)[:60]}...")
        except Exception:
            pass

    # Filtrar falsos positivos: líneas que contienen "example", "test", "sample"
    secretos = [s for s in secretos if not any(x in s.lower() for x in ["example", "test_", "sample_", "demo_"])]

    return {
        "secretos_detectados": len(secretos),
        "secretos": secretos[:10],
        "nivel": "ALTO" if secretos else "OK",
        "accion": "Rotar secrets inmediatamente" if secretos else "ninguna",
    }


def analisis_puertos() -> dict:
    out = run(["lsof", "-i", ":8799"])
    ocupado = "LISTEN" in out
    return {
        "puerto_8799_ocupado": ocupado,
        "proceso": out.strip() if ocupado else "libre",
        "impacto": "Suite honesta falla si hay proceso en 8799" if ocupado else "OK",
        "nivel": "ALTO" if ocupado else "OK",
        "accion": "kill -9 $(lsof -t -i :8799 2>/dev/null)" if ocupado else "ninguna",
    }


def delegar_hallazgos_complejos(hallazgos: list[str]) -> list[str]:
    """Delegar hallazgos complejos a otros agentes (capacidad subagent).

    En lugar de procesar todo aquí, delega a agentes especializados
    cuando el hallazgo requiere análisis profundo.
    """
    delegados = []
    for hallazgo in hallazgos:
        if "CVE" in hallazgo or "vulnerabilidad" in hallazgo.lower():
            # Delegar a security-soc para análisis profundo
            try:
                result = subprocess.run(
                    [PY, "scripts/agent_security_soc_monitor.py"],
                    capture_output=True, text=True, timeout=30, cwd=REPO
                )
                if result.returncode == 0:
                    delegados.append(f"Delegado a security-soc: {hallazgo[:80]}")
            except Exception:
                delegados.append(f"No se pudo delegar: {hallazgo[:80]}")
    return delegados


def resumen() -> dict:
    # Ejecutar verificaciones en paralelo (batch_processing)
    # Las 3 verificaciones son independientes entre sí
    import threading

    results = {}
    lock = threading.Lock()

    def run_auditoria(nombre, func):
        results[nombre] = func()

    t1 = threading.Thread(target=run_auditoria, args=("dependencias", auditoria_dependencias))
    t2 = threading.Thread(target=run_auditoria, args=("secretos", detectar_secretos))
    t3 = threading.Thread(target=run_auditoria, args=("puertos", analisis_puertos))
    t1.start(); t2.start(); t3.start()
    t1.join(); t2.join(); t3.join()

    deps = results.get("dependencias", {})
    secretos = results.get("secretos", {})
    puertos = results.get("puertos", {})

    # Hallazgos complejos → delegar (subagent)
    hallazgos = []
    if secretos.get("secretos_detectados", 0) > 0:
        hallazgos.append(f"Secretos detectados: {secretos['secretos_detectados']}")
    if puertos.get("puerto_8799_ocupado"):
        hallazgos.append("Puerto 8799 ocupado por zombie")

    delegados = delegar_hallazgos_complejos(hallazgos) if hallazgos else []

    # Memory: registrar en loop-log
    nivel_global = "OK"
    if secretos.get("secretos_detectados", 0) > 0:
        nivel_global = "ALTO"
    elif puertos.get("puerto_8799_ocupado"):
        nivel_global = "ALTO"

    registrar_en_loop(
        f"Auditoría: deps={deps.get('dependencias_encontradas',0)} | "
        f"secretos={secretos.get('secretos_detectados',0)} | "
        f"puerto8799={'OCUPADO' if puertos.get('puerto_8799_ocupado') else 'libre'} | "
        f"nivel={nivel_global}" +
        (f" | delegados: {len(delegados)}" if delegados else "")
    )

    return {
        "agent": "cto",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capacidades_activas": ["subagent", "memory", "batch_processing"],
        "dependencias": deps,
        "secretos": secretos,
        "puertos": puertos,
        "delegados": delegados,
        "mejoras_propuestas": [
            "Instalar pip-audit: pip install pip-audit → cron semanal",
            "Revisar puerto 8799: si hay zombie, kill + registrar",
            "Si se detectan secretos reales: rotar y usar .env / vault",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
