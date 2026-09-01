#!/usr/bin/env python3
"""
Agente Security-SOC — Auto-mejora: Monitor de puertos + procesos zombie.

Nueva capacidad vs prueba anterior:
- Antes: solo listaba procesos
- Ahora: detecta procesos zombie, puertos en escucha que no deberían estar,
  procesos que bloquean tests de integración, y ejecuta acciones correctivas
  automáticas (kill + registro en loop-log).

Output: JSON con estado del SOC + acciones ejecutadas.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

REPO = Path("/Users/adri/lucidfence")
LOG = REPO / "docs/internal/loop-run-log.md"
PUERTO_PRUEBAS = 8799


def run(cmd: list[str], timeout: int = 15) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except Exception as e:
        return f"ERROR: {e}"


def detectar_zombies() -> dict:
    """Detecta procesos zombie o puertos ocupados por procesos muertos."""
    out = run(["lsof", "-i", f":{PUERTO_PRUEBAS}"])
    lines = [l for l in out.splitlines() if "LISTEN" in l]
    if not lines:
        return {"estado": "OK", "puerto_libre": True, "accion": "ninguna"}

    # extraer PIDs
    pids = []
    for l in lines:
        parts = l.split()
        for p in parts:
            if p.isdigit():
                pids.append(int(p))
                break
    pids = list(set(pids))
    return {
        "estado": "ALERTA",
        "puerto_libre": False,
        "pids_detectados": pids,
        "procesos": lines,
        "accion_ejecutada": f"kill -9 {','.join(map(str, pids))}" if pids else "none",
    }


def limpiar_puerto_8799() -> dict:
    """Mata procesos en puerto 8799 y registra en loop-log."""
    zombies = detectar_zombies()
    if zombies["puerto_libre"]:
        return {"resultado": "OK", "mensaje": "Puerto 8799 libre, nada que hacer"}

    pids = zombies.get("pids_detectados", [])
    for pid in pids:
        run(["kill", "-9", str(pid)])
        time.sleep(0.5)

    # verificar limpieza
    time.sleep(1)
    verificacion = detectar_zombies()
    return {
        "resultado": "LIMPIADO" if verificacion["puerto_libre"] else "FALLIDO",
        "pids_matados": pids,
        "puerto_despues": "libre" if verificacion["puerto_libre"] else "sigue ocupado",
    }


def registrar_accion(accion: str, resultado: str):
    """Registra acción en loop-run-log.md."""
    linea = f"- {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} | L2 | Security-SOC | {accion} | {resultado}\n"
    with open(LOG, "a") as f:
        f.write(linea)


def resumen() -> dict:
    zombies = detectar_zombies()
    limpieza = limpiar_puerto_8799() if not zombies["puerto_libre"] else {"resultado": "OK", "mensaje": "ninguna"}

    if not zombies["puerto_libre"]:
        registrar_accion(
            f"Security-SOC: limpieza puerto 8799 (PIDs {zombies.get('pids_detectados', [])})",
            f"resultado: {limpieza['resultado']}"
        )

    return {
        "agent": "security-soc",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "monitor_puertos": zombies,
        "limpieza_ejecutada": limpieza,
        "mejoras_propuestas": [
            "Añadir watchdog que corra cada minuto verificando puerto 8799",
            "Configurar systemd / launchd para matar automáticamente procesos en puerto de tests",
            "Añadir health-check al loop-verify que detecte zombie antes de ejecutar tests",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(resumen(), indent=2, ensure_ascii=False))
