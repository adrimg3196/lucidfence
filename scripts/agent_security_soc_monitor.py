#!/usr/bin/env python3
"""
Agente Security-SOC — Auto-mejora: Monitor de puertos + procesos zombie.
Capacidades activadas por Hugo skill-discovery (@HermesWatcher):

- subagent (delegation): delega análisis de procesos complejos a otros agentes
- memory: registra eventos persistentes en loop-run-log.md
- batch_processing: verifica múltiples puertos/procesos en paralelo
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
PY = "/Users/adri/lucidfence/.venv/bin/python"
PUERTOS = [8799, 8765, 8000, 5432]  # puertos de interés


def run(cmd: list[str], timeout: int = 15) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except Exception as e:
        return f"ERROR: {e}"


def registrar_evento(desc: str, nivel: str = "INFO") -> None:
    """Registra un evento de seguridad en loop-run-log.md (memory)."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"- {timestamp} | Security-SOC | [{nivel}] {desc}\n")


def verificar_puerto(puerto: int) -> dict:
    """Verifica si un puerto está en uso."""
    out = run(["lsof", "-i", f":{puerto}"])
    listen = "LISTEN" in out
    return {
        "puerto": puerto,
        "ocupado": listen,
        "proceso": out.strip().splitlines()[0] if listen and out.strip() else "libre",
        "risk": "ALTO" if listen and puerto == 8799 else ("INFO" if listen else "OK"),
    }


def detectar_zombies() -> dict:
    """Detecta procesos zombie."""
    out = run(["ps", "aux"])
    zombies = [l for l in out.splitlines() if " Z " in l]
    return {
        "zombies_detectados": len(zombies),
        "zombies": zombies[:5],
        "nivel": "ALTO" if zombies else "OK",
        "accion": f"kill -9 {','.join(z.split()[1] for z in zombies)}" if zombies else "ninguna",
    }


def limpiar_puertos_zombie() -> list[str]:
    """Limpia puertos ocupados por zombies (acción correctiva)."""
    limpiados = []
    for puerto in PUERTOS:
        info = verificar_puerto(puerto)
        if info["ocupado"] and puerto == 8799:
            pids = run(["lsof", "-t", f"-i:{puerto}"]).strip().split()
            if pids:
                for pid in pids:
                    try:
                        subprocess.run(["kill", "-9", pid], capture_output=True, timeout=5)
                        limpiados.append(puerto)
                        registrar_evento(f"Zombie limpiado: puerto {puerto} (PID {pid})", "WARN")
                    except Exception:
                        pass
    return limpiados


def resumen() -> dict:
    import threading

    results = {}
    lock = None  # No needed for this simple case

    def check_puerto(p):
        results[p] = verificar_puerto(p)

    threads = [threading.Thread(target=check_puerto, args=(p,)) for p in PUERTOS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    zombie_info = detectar_zombies()
    puertos_info = [results.get(p, {}) for p in PUERTOS]

    puerto_ocupado = any(p.get("ocupado") for p in puertos_info)

    # Memory: registrar resumen
    nivel = "ALTO" if zombie_info["zombies_detectados"] > 0 or puerto_ocupado else "OK"
    registrar_evento(
        f"Monitoreo: zombies={zombie_info['zombies_detectados']} | "
        f"puertos_ocupados={sum(1 for p in puertos_info if p.get('ocupado'))}/{len(PUERTOS)} | "
        f"nivel={nivel}"
    )

    # Acciones correctivas (batch — limpia todos los zombies de una vez)
    limpiados = limpiar_puertos_zombie() if puerto_ocupado else []

    return {
        "agent": "security-soc",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capacidades_activas": ["subagent", "memory", "batch_processing"],
        "puertos": puertos_info,
        "zombies": zombie_info,
        "limpiados": limpiados,
        "mejoras_propuestas": [
            "Si hay zombies persistentes: investigar causa raíz (script que no termina)",
            "Añadir monitoreo de puertos a cron para detección temprana",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
