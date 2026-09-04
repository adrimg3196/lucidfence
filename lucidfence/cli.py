#!/usr/bin/env python3
"""LucidFence CLI — local-first geofencing control plane for macOS and Linux."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.app_paths import ensure_data_dir  # noqa: E402

VERSION = "1.6.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
STARTUP_TIMEOUT_SECONDS = 15.0


def _host(value: Optional[str] = None) -> str:
    return value or os.environ.get("LUCIDFENCE_HOST", DEFAULT_HOST)


def _port(value: Optional[int] = None) -> int:
    return int(value or os.environ.get("LUCIDFENCE_PORT", DEFAULT_PORT))


def _runtime_dir() -> Path:
    return ensure_data_dir()


def _pid_file() -> Path:
    return _runtime_dir() / "lucidfence.pid"


def _log_file() -> Path:
    return _runtime_dir() / "lucidfence.log"


def _url(host: str, port: int) -> str:
    public_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{public_host}:{port}"


def _healthy(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(_url(host, port) + "/", timeout=timeout) as response:
            body = response.read(4096)
            return response.status == 200 and b"LucidFence" in body
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _read_pid_record() -> dict:
    try:
        raw = _pid_file().read_text().strip()
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and int(data.get("pid", 0)) > 0:
                return data
            if isinstance(data, int) and data > 0:
                return {"pid": data, "legacy": True}
        except (json.JSONDecodeError, TypeError, ValueError):
            # Backward compatibility with the plain integer used by 1.1.0.
            return {"pid": int(raw), "legacy": True}
    except (OSError, ValueError):
        pass
    return {}


def _read_pid() -> Optional[int]:
    pid = _read_pid_record().get("pid")
    return int(pid) if pid else None


def _pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _process_command(pid: int) -> str:
    """Return the live process command on macOS/Linux, or empty on failure."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True, capture_output=True, timeout=2, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _owned_process(record: dict) -> bool:
    """Prove that a PID belongs to this installed LucidFence server."""
    try:
        pid = int(record.get("pid", 0))
    except (TypeError, ValueError):
        return False
    if not _pid_alive(pid):
        return False
    server = str((ROOT / "saas_server.py").resolve())
    recorded_server = str(record.get("server") or server)
    return recorded_server == server and server in _process_command(pid)


def _write_pid_record(process: subprocess.Popen, host: str, port: int) -> None:
    record = {
        "pid": process.pid,
        "server": str((ROOT / "saas_server.py").resolve()),
        "host": host,
        "port": port,
        "started_at": time.time(),
    }
    _pid_file().write_text(json.dumps(record, separators=(",", ":")) + "\n")
    try:
        _pid_file().chmod(0o600)
    except OSError:
        pass


def _rollback_start(process: subprocess.Popen) -> None:
    """Terminate a failed child and remove only its own PID record."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    if _read_pid() == process.pid:
        _pid_file().unlink(missing_ok=True)


def _server_env(host: str, port: int) -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "LUCIDFENCE_HOST": host,
        "LUCIDFENCE_PORT": str(port),
        "LUCIDFENCE_DATA_DIR": str(_runtime_dir()),
        "PYTHONUNBUFFERED": "1",
    })
    return env


def cmd_serve(args) -> int:
    host, port = _host(args.host), _port(args.port)
    server = ROOT / "saas_server.py"
    if not server.is_file():
        print(f"ERROR: instalación incompleta; falta {server}", file=sys.stderr)
        return 2
    print(f"LucidFence · app local · {_url(host, port)}")
    print(f"Datos: {_runtime_dir()}")
    os.execve(sys.executable, [sys.executable, str(server)], _server_env(host, port))
    return 0


def cmd_start(args) -> int:
    host, port = _host(args.host), _port(args.port)
    url = _url(host, port)
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    def healthy_before_deadline() -> bool:
        remaining = deadline - time.monotonic()
        return remaining > 0 and _healthy(host, port, timeout=min(0.8, remaining))

    if healthy_before_deadline():
        print(f"LucidFence ya está activo: {url}")
        if args.open_browser:
            webbrowser.open(url)
        return 0

    runtime = _runtime_dir()
    log_path = _log_file()
    log_handle = log_path.open("ab", buffering=0)
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "saas_server.py")],
        env=_server_env(host, port),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        close_fds=True,
        start_new_session=True,
    )
    log_handle.close()
    _write_pid_record(process, host, port)

    while time.monotonic() < deadline:
        if healthy_before_deadline():
            print(f"LucidFence iniciado: {url}")
            print(f"Datos: {runtime}")
            print(f"Log: {log_path}")
            if args.open_browser:
                webbrowser.open(url)
            return 0
        if process.poll() is not None:
            break
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(0.25, remaining))

    print(f"ERROR: LucidFence no arrancó. Revisa {log_path}", file=sys.stderr)
    _rollback_start(process)
    return 1


def cmd_stop(args) -> int:
    record = _read_pid_record()
    pid = record.get("pid")
    if not _pid_alive(pid):
        _pid_file().unlink(missing_ok=True)
        print("LucidFence ya estaba detenido.")
        return 0
    if not _owned_process(record):
        _pid_file().unlink(missing_ok=True)
        print(f"ERROR: el PID {pid} no pertenece a esta instalación de LucidFence; no se enviaron señales.", file=sys.stderr)
        return 1
    assert pid is not None
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if not _pid_alive(pid):
            _pid_file().unlink(missing_ok=True)
            print("LucidFence detenido.")
            return 0
        time.sleep(0.1)
    print(f"ERROR: el proceso {pid} no respondió a SIGTERM.", file=sys.stderr)
    return 1


def cmd_restart(args) -> int:
    stopped = cmd_stop(args)
    if stopped:
        return stopped
    return cmd_start(args)


def cmd_status(args) -> int:
    host, port = _host(args.host), _port(args.port)
    record = _read_pid_record()
    pid = record.get("pid")
    healthy = _healthy(host, port)
    state = "activo" if healthy else "detenido"
    print(f"LucidFence: {state}")
    print(f"URL: {_url(host, port)}")
    print(f"PID: {pid if _owned_process(record) else '—'}")
    print(f"Datos: {_runtime_dir()}")
    print(f"Log: {_log_file()}")
    return 0 if healthy else 1


def cmd_open(args) -> int:
    host, port = _host(args.host), _port(args.port)
    if not _healthy(host, port):
        rc = cmd_start(SimpleNamespace(host=host, port=port, open_browser=False))
        if rc:
            return rc
    webbrowser.open(_url(host, port))
    return 0


def cmd_validate_config(args) -> int:
    from lucidfence.core.config_validator import _main as validate_main
    return validate_main(["--config", args.config] + (["--json"] if args.json else []))


def cmd_adapter_new(args) -> int:
    from lucidfence.core.adapter_scaffold import scaffold_adapter
    # El scaffolding es un flujo de contribuidor: opera sobre el checkout
    # actual si lo hay; si no, sobre el árbol del paquete instalado.
    cwd = Path.cwd()
    root = cwd if (cwd / "lucidfence" / "core" / "adapters").is_dir() else ROOT
    result = scaffold_adapter(args.name, root)
    if not result.get("ok"):
        print(f"ERROR: {result.get('error')}", file=sys.stderr)
        return 2
    print(f"Adapter '{args.name}' generado ({result['class_name']}):")
    print(f"  {result['adapter_path']}")
    print(f"  {result['test_path']}")
    print("\nSiguientes pasos:")
    for step in result["next_steps"]:
        print(f"  {step}")
    return 0


def cmd_mcp(_args) -> int:
    server = Path(__file__).resolve().parent / "mcp" / "lucidfence_mcp.py"
    if not server.is_file():
        print(f"ERROR: instalación incompleta; falta {server}", file=sys.stderr)
        return 2
    os.execve(sys.executable, [sys.executable, str(server)], dict(os.environ))
    return 0


def cmd_shell(_args) -> int:
    from lucidfence.shell import LucidFenceShell
    LucidFenceShell(ROOT).cmdloop()
    return 0


def cmd_doctor(args) -> int:
    from lucidfence.core.doctor import run_doctor
    report = run_doctor(ROOT, ensure_data_dir(), _port(args.port))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for check in report["checks"]:
            mark = "OK" if check["ok"] else ("WARN" if check["severity"] == "warning" else "FAIL")
            print(f"[{mark:4}] {check['name']}: {check['detail']}")
        print(f"doctor: {'PASS' if report['ok'] else 'FAIL'} ({report['errors']} errors, {report['warnings']} warnings)")
    return 0 if report["ok"] else 1


def _quickstart_command(subcommand: str) -> str:
    """Return a command the current installation path can actually run."""
    program = (
        "lucidfence" if shutil.which("lucidfence")
        else "python3 -m lucidfence.cli"
    )
    return f"{program} {subcommand}"


def cmd_quickstart(args) -> int:
    """Del install a ver tu flota, en pasos autoverificados.

    Reduce el time-to-first-value: un admin que acaba de instalar corre
    `lucidfence quickstart` y en 4 pasos comprobados (entorno → app → dashboard
    → fuente de datos) llega a su flota, con la acción concreta si algo falta.
    """
    host, port = _host(args.host), _port(args.port)
    url = _url(host, port)
    print("LucidFence · quickstart · gratis y 100% local\n")

    # 1/4 — entorno (reutiliza el mismo diagnóstico que `lucidfence doctor`)
    from lucidfence.core.doctor import run_doctor
    report = run_doctor(ROOT, ensure_data_dir(), port)
    if report["ok"]:
        print("[1/4] OK  Entorno listo (Python, dependencias, ficheros).")
    else:
        print(f"[1/4] FAIL Entorno con {report['errors']} problema(s):")
        for check in report["checks"]:
            if not check["ok"] and check["severity"] != "warning":
                print(f"          - {check['name']}: {check['detail']}")
        print(f"      Arréglalo y repite `{_quickstart_command('quickstart')}`.")
        return 1

    # 2/4 — app local arrancada
    if _healthy(host, port):
        print(f"[2/4] OK  App ya activa en {url}")
    else:
        rc = cmd_start(SimpleNamespace(host=host, port=port, open_browser=False))
        if rc != 0 or not _healthy(host, port):
            print(
                "[2/4] FAIL La app no arrancó. Revisa "
                f"`{_quickstart_command('status')}` y el log."
            )
            return 1
        print(f"[2/4] OK  App arrancada en {url}")

    # 3/4 — dashboard vivo
    print(f"[3/4] OK  Dashboard vivo: {url}")

    # 4/4 — fuente de datos de la flota
    if Path("config.json").is_file():
        print(
            "[4/4] OK  config.json detectado — valida tu UEM: "
            f"`{_quickstart_command('validate-config')}`"
        )
    else:
        print("[4/4] --  Sin config.json: arranca en modo demo (flota simulada).")
        print("          Conecta tu UEM real (Intune/Jamf/Applivery/Fleet):")
        print("          copia config.example.json a config.json, edítalo y")
        print(f"          verifica con `{_quickstart_command('validate-config')}`.")

    print(f"\nListo. Abre tu flota:  {url}")
    print("Integra un UEM real:   docs/integrations/  (mínimo privilegio por UEM)")
    if getattr(args, "open_browser", False):
        webbrowser.open(url)
    return 0


def cmd_apply(args) -> int:
    """Políticas y geocercas como código: valida -> diff -> what-if -> aplica.

    GitOps sin servidor: la config candidata vive en git y `lucidfence apply`
    la valida con los mismos validadores del engine, enseña el plan y solo
    escribe con --yes (dry-run por defecto, igual que el enforcement arranca
    en observe). Jamás toca dispositivos: solo ficheros locales del data dir.
    """
    from lucidfence.core import config_apply as ca
    if not args.fences and not args.policies:
        print("ERROR: indica al menos --fences o --policies", file=sys.stderr)
        return 2
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else _runtime_dir()
    mode = "apply" if args.yes else "dry-run (usa --yes para aplicar)"
    print(f"LucidFence · apply · {mode}")
    print(f"Data dir: {data_dir}\n")

    # (etiqueta, fichero vivo destino, resultado del candidato, filas vivas)
    plans: list[tuple[str, Path, dict, dict]] = []
    cand_fences = None
    cand_policies_raw = None
    if args.fences:
        res = ca.load_fences_candidate(args.fences)
        cand_fences = res["fences"]
        target = data_dir / "fences.json"
        plans.append(("fences.json", target, res, ca.load_live_fence_rows(target)))
    if args.policies:
        res = ca.load_policies_candidate(args.policies)
        cand_policies_raw = res["raw"]
        target = data_dir / "policies.json"
        plans.append(("policies.json", target, res, ca.load_live_policy_rows(target)))

    print("[1/4] VALIDAR")
    errors = [e for _l, _t, res, _v in plans for e in res["errors"]]
    if errors:
        for e in errors:
            print(f"  ERROR {e}")
        print(f"\n{len(errors)} error(es) de validación: no se aplica nada.")
        return 1
    for label, _t, res, _v in plans:
        kind = "geocercas" if label == "fences.json" else "políticas"
        print(f"  OK  {res['path']}: {res['count']} {kind} válidas")

    print("\n[2/4] DIFF contra la config viva del data dir")
    for label, _t, res, live in plans:
        d = ca.diff_rows(live, res["by_id"])
        print(f"  {label}:")
        if not (d["added"] or d["changed"] or d["removed"]):
            print("    sin cambios")
        for fid in d["added"]:
            print(f"    + {fid}")
        for fid in d["changed"]:
            print(f"    ~ {fid}")
        for fid in d["removed"]:
            print(f"    - {fid}")

    print("\n[3/4] WHAT-IF (replay del cambio sobre el histórico local)")
    # Se simulan las políticas que quedarían activas tras el apply: las
    # candidatas si vienen, y si no las vivas (útil al cambiar solo geocercas).
    pol_replay = (cand_policies_raw if cand_policies_raw is not None
                  else ca.load_raw_policies(data_dir / "policies.json"))
    wi = ca.what_if(data_dir, pol_replay, cand_fences)
    if wi["points"] == 0:
        print("  sin histórico para simular (trails.jsonl vacío o ausente)")
    elif not wi["replays"]:
        print("  sin políticas activas que simular")
    else:
        for r in wi["replays"]:
            total = sum(r["actions_that_would_run"].values())
            acc = ", ".join(f"{k}×{v}" for k, v in sorted(r["actions_that_would_run"].items()))
            approx = "exacto" if r["approximation"]["exact"] else "aproximado"
            print(f"  {r['policy_id']}: con esta config habrían disparado {total} acciones"
                  f" ({acc or 'ninguna'}) en {r['devices_affected']} dispositivo(s)"
                  f" sobre {r['points_evaluated']} puntos [{approx}]")
            if r["destructive_actions"]:
                print(f"    ATENCIÓN: incluye acciones destructivas: {', '.join(r['destructive_actions'])}")

    print("\n[4/4] APLICAR")
    if not args.yes:
        print("  dry-run: no se ha escrito nada. Repite con --yes para aplicar.")
        return 0
    for _label, target, res, _live in plans:
        ca.apply_atomic(target, res["text"])
        print(f"  escrito {target}")
    print("  Reinicia o recarga la app (`lucidfence restart`) para que el engine cargue la config nueva.")
    return 0


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=None, help=f"interfaz de escucha (por defecto {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=None, help=f"puerto (por defecto {DEFAULT_PORT})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lucidfence",
        description="Geofencing y riesgo UEM/MDM, gratis y completamente local.",
    )
    parser.add_argument("--version", action="version", version=f"lucidfence {VERSION}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="ejecuta el servidor en primer plano")
    _common(serve)
    serve.set_defaults(func=cmd_serve)

    start = sub.add_parser("start", help="inicia la app en segundo plano")
    _common(start)
    start.add_argument("--no-open", dest="open_browser", action="store_false", help="no abrir el navegador")
    start.set_defaults(func=cmd_start, open_browser=True)

    stop = sub.add_parser("stop", help="detiene la instancia gestionada por la CLI")
    _common(stop)
    stop.set_defaults(func=cmd_stop)

    restart = sub.add_parser("restart", help="reinicia la app")
    _common(restart)
    restart.add_argument("--no-open", dest="open_browser", action="store_false")
    restart.set_defaults(func=cmd_restart, open_browser=True)

    status = sub.add_parser("status", help="muestra salud, PID y rutas locales")
    _common(status)
    status.set_defaults(func=cmd_status)

    open_cmd = sub.add_parser("open", help="abre el dashboard; inicia la app si hace falta")
    _common(open_cmd)
    open_cmd.set_defaults(func=cmd_open)

    doctor = sub.add_parser("doctor", help="diagnostica la instalación local")
    _common(doctor)
    doctor.add_argument("--json", action="store_true", help="salida estructurada")
    doctor.set_defaults(func=cmd_doctor)

    quickstart = sub.add_parser(
        "quickstart", help="del install a ver tu flota, en pasos autoverificados")
    _common(quickstart)
    quickstart.add_argument("--open", dest="open_browser", action="store_true",
                            help="abre el dashboard en el navegador al terminar")
    quickstart.set_defaults(func=cmd_quickstart, open_browser=False)

    apply_p = sub.add_parser(
        "apply", help="políticas y geocercas como código: valida, diff, what-if y aplica")
    apply_p.add_argument("--fences", default=None, help="fichero candidato de geocercas (formato fences.json)")
    apply_p.add_argument("--policies", default=None, help="fichero candidato de políticas (formato policies.json)")
    apply_p.add_argument("--data-dir", dest="data_dir", default=None,
                         help="data dir del tenant (por defecto el de la app local)")
    apply_p.add_argument("--yes", action="store_true",
                         help="aplica de verdad (por defecto dry-run: solo imprime el plan)")
    apply_p.set_defaults(func=cmd_apply)

    validate = sub.add_parser("validate-config",
                              help="valida el mapeo location_source contra la API real (cualquier UEM)")
    validate.add_argument("--config", default="config.json", help="ruta a config.json")
    validate.add_argument("--json", action="store_true", help="salida estructurada")
    validate.set_defaults(func=cmd_validate_config)

    adapter = sub.add_parser("adapter", help="herramientas del SDK de adapters MDM")
    adapter_sub = adapter.add_subparsers(dest="adapter_command", required=True)
    adapter_new = adapter_sub.add_parser(
        "new", help="genera el esqueleto de un adapter MDM nuevo + su contract test")
    adapter_new.add_argument("name", help="identificador del MDM (minúsculas, p.ej. mosyle)")
    adapter_new.set_defaults(func=cmd_adapter_new)

    mcp = sub.add_parser("mcp", help="ejecuta el MCP local read-only por stdio")
    mcp.set_defaults(func=cmd_mcp)

    shell = sub.add_parser("shell", help="abre la shell interactiva local")
    shell.set_defaults(func=cmd_shell)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args(["start"])
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
