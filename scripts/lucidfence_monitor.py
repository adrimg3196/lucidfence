#!/usr/bin/env python3
"""Monitor operativo de LucidFence.

Ejecuta dos health-checks de producto:
  1. Suite local de tests: `python3 tests/run_tests.py` debe cerrar con 0 fallos
     y al menos 110 tests pasados.
  2. Vitrina HTTP: `cloud.html` debe responder 2xx/3xx.

Si un check falla, crea una tarjeta de fix en el board Hermes Kanban
`lucidfence` con idempotency-key estable para no duplicar incidentes abiertos.

Uso recomendado:
  python3 scripts/lucidfence_monitor.py
  python3 scripts/lucidfence_monitor.py --dry-run

Variables útiles:
  LUCIDFENCE_ROOT=/ruta/proyecto
  LUCIDFENCE_BOARD=lucidfence
  LUCIDFENCE_VITRINA_URL=https://...
  LUCIDFENCE_TEST_COMMAND="python3 tests/run_tests.py"
  LUCIDFENCE_MIN_TESTS=110
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


# Ruta canónica del proyecto en este host. Se mantiene explícita porque el
# monitor también se copia a ~/.hermes/scripts/ para cron, donde parents[1]
# apuntaría a ~/.hermes en vez del repo.
DEFAULT_ROOT = Path("/Users/adri/geofence-uem")
DEFAULT_BOARD = "lucidfence"
DEFAULT_VITRINA_URL = "https://adrimg3196.github.io/lucidfence/cloud.html"
DEFAULT_TEST_COMMAND = f"{shlex.quote(sys.executable)} tests/run_tests.py"
DEFAULT_MIN_TESTS = 110


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str


@dataclass(frozen=True)
class Incident:
    title: str
    assignee: str
    body: str
    key: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Health-check LucidFence + auto-kanban.")
    parser.add_argument("--root", default=os.environ.get("LUCIDFENCE_ROOT", str(DEFAULT_ROOT)))
    # No usamos HERMES_KANBAN_BOARD como default: cuando el monitor se valida
    # desde un worker de otro board (p.ej. uem-ops), debe seguir creando fixes
    # en el board canónico de LucidFence salvo override explícito.
    parser.add_argument("--board", default=os.getenv("LUCIDFENCE_BOARD", DEFAULT_BOARD))
    parser.add_argument("--vitrina-url", default=os.environ.get("LUCIDFENCE_VITRINA_URL", DEFAULT_VITRINA_URL))
    parser.add_argument("--test-command", default=os.environ.get("LUCIDFENCE_TEST_COMMAND", DEFAULT_TEST_COMMAND))
    parser.add_argument("--min-tests", type=int, default=int(os.environ.get("LUCIDFENCE_MIN_TESTS", DEFAULT_MIN_TESTS)))
    parser.add_argument("--dry-run", action="store_true", help="No crea tarjetas; solo imprime lo que haría.")
    parser.add_argument("--http-timeout", type=float, default=15.0)
    parser.add_argument("--test-timeout", type=float, default=300.0)
    return parser.parse_args()


def http_check(url: str, timeout: float) -> CheckResult:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "lucidfence-monitor/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            final_url = response.geturl()
            ok = 200 <= int(status) < 400
            return CheckResult(ok=ok, detail=f"HTTP {status} ({final_url})")
    except urllib.error.HTTPError as exc:
        return CheckResult(ok=False, detail=f"HTTP {exc.code}: {exc.reason}")
    except Exception as exc:  # noqa: BLE001 - monitor must report, not crash silently
        return CheckResult(ok=False, detail=f"{type(exc).__name__}: {exc}")


def tests_check(root: Path, command: str, min_tests: int, timeout: float) -> CheckResult:
    if not root.exists():
        return CheckResult(ok=False, detail=f"root inexistente: {root}")

    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(ok=False, detail=f"no se pudo ejecutar `{command}`: {type(exc).__name__}: {exc}")

    output = f"{completed.stdout}\n{completed.stderr}"
    # Algunos módulos imprimen subtallies propios durante la importación; el
    # resumen fiable es el último `X passed, Y failed` que emite el runner.
    matches = re.findall(r"(\d+)\s+passed,\s+(\d+)\s+failed", output)
    tail = "\n".join(output.strip().splitlines()[-12:])
    if not matches:
        return CheckResult(
            ok=False,
            detail=f"runner sin tally parseable; exit={completed.returncode}; tail={tail!r}",
        )

    passed, failed = (int(value) for value in matches[-1])
    ok = completed.returncode == 0 and failed == 0 and passed >= min_tests
    return CheckResult(
        ok=ok,
        detail=f"{passed} passed, {failed} failed, exit={completed.returncode}, min={min_tests}",
    )


def create_kanban_card(board: str, incident: Incident, root: Path, dry_run: bool) -> bool:
    command = [
        "hermes",
        "kanban",
        "--board",
        board,
        "create",
        incident.title,
        "--assignee",
        incident.assignee,
        "--body",
        incident.body,
        "--idempotency-key",
        incident.key,
        "--json",
    ]

    if dry_run:
        print(f"[monitor] DRY-RUN crearía tarjeta board={board} assignee={incident.assignee} key={incident.key}: {incident.title}")
        return True

    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60, check=False)
    if completed.returncode == 0:
        print(f"[monitor] tarjeta creada/reusada: {incident.title} :: {completed.stdout.strip()}")
        return True

    print(
        f"[monitor] ERROR creando tarjeta `{incident.title}`: exit={completed.returncode}\n"
        f"stdout={completed.stdout.strip()}\nstderr={completed.stderr.strip()}",
        file=sys.stderr,
    )
    return False


def build_incidents(test_result: CheckResult, http_result: CheckResult, vitrina_url: str, min_tests: int) -> list[Incident]:
    incidents: list[Incident] = []

    if not test_result.ok:
        incidents.append(
            Incident(
                title="FIX: suite de tests LucidFence por debajo del gate",
                assignee="default",
                body=(
                    f"El monitor LucidFence detectó que la suite no cumple el gate de >= {min_tests} tests "
                    f"pasados y 0 fallos. Detalle: {test_result.detail}. "
                    "Reparar la suite o ajustar el gate si el alcance cambió intencionadamente."
                ),
                key="lucidfence-monitor-tests-gate",
            )
        )

    if not http_result.ok:
        incidents.append(
            Incident(
                title="FIX: vitrina LucidFence caída o sin HTTP OK",
                assignee="integrations-specialist",
                body=(
                    f"El monitor LucidFence no recibió respuesta HTTP 2xx/3xx de la vitrina {vitrina_url}. "
                    f"Detalle: {http_result.detail}. Revisar static/cloud.html, GitHub Pages/deploy y publicar de nuevo."
                ),
                key="lucidfence-monitor-vitrina-down",
            )
        )

    return incidents


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    os.environ["HERMES_KANBAN_BOARD"] = args.board

    test_result = tests_check(root, args.test_command, args.min_tests, args.test_timeout)
    http_result = http_check(args.vitrina_url, args.http_timeout)

    print(f"[monitor] tests: {'OK' if test_result.ok else 'FAIL'} — {test_result.detail}")
    print(f"[monitor] vitrina: {'OK' if http_result.ok else 'FAIL'} — {http_result.detail}")

    incidents = build_incidents(test_result, http_result, args.vitrina_url, args.min_tests)
    if not incidents:
        print("[monitor] OK — sin incidentes; no se crean tarjetas")
        return 0

    created_all = True
    for incident in incidents:
        created_all = create_kanban_card(args.board, incident, root, args.dry_run) and created_all

    print(f"[monitor] {len(incidents)} incidente(s) detectado(s)")
    return 1 if not created_all else 2


if __name__ == "__main__":
    raise SystemExit(main())
