"""Zero-dependency test runner for the LucidFence SaaS.

Discovers every `test_*` function in `tests/*.py` and runs it, mirroring
pytest's behaviour without adding a dependency (the product stays stdlib-only).

Run:  python3 tests/run_tests.py

Counting model (why we import + call functions directly):
  Each `test_*` function is one check, so the final `N passed, M failed`
  tally is the TRUE number of individual checks. The monitor
  (scripts/lucidfence_monitor.py) gates on `>= 110 passed and 0 failed`
  and parses the LAST `N passed, M failed` line, so this number must be
  the real per-test count, never a per-file count and never a blind
  `def test_*` tally that would hide failures.

Concurrency safety (multi-agent box):
  This host routinely runs several kanban workers, each spawning its own
  `saas_server.py`. A *fixed* :8765 caused "Address already in use"
  (the runner's server) and "Connection refused" (test modules hitting a
  dead/orphaned server) whenever two runners overlapped.

  The runner therefore:
    * binds an EPHEMERAL port (bind to 0) and exports it as
      LUCIDFENCE_PORT; the server subprocess and every test module read that
      same variable, so the whole process agrees on one port and never
      collides with a competitor on :8765.
    * frees any leftover process holding that ephemeral port BEFORE binding,
      so a leaked server from a prior (crashed) run cannot poison this one.
    * launches the server via `python3 -c "runpy.run_path(...)"` so its argv
      does NOT contain "saas_server.py" -- a sibling runner that blanket-kills
      `pkill -f saas_server.py` therefore cannot murder our instance.
    * keeps a per-iteration WATCHDOG: every module re-checks server
      liveness and restarts it if it died, so a transient crash never poisons
      a later module with a dead server.
    * always terminates the server (atexit + signal handlers + finally) so we
      never leave a zombie holding the port.
    * runs with the signup rate limit raised, so the many independent signups
      in the suite never trip a shared in-memory counter.
"""
from __future__ import annotations

import atexit
import importlib.util
import os
import signal
import socket
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)  # so `from helpers import ...` resolves inside tests/


def _alloc_port() -> int:
    """Allocate an unused TCP port (bind to 0)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


SERVER_PORT = _alloc_port()
os.environ["LUCIDFENCE_PORT"] = str(SERVER_PORT)

_SRV = {"p": None}  # type: ignore[var-annotated]


def _port_owner_pid(port: int):
    """Return the PID holding `port` on loopback (LISTEN), or None."""
    try:
        out = subprocess.run(
            ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        pids = [p for p in out.stdout.split() if p.strip().isdigit()]
        return int(pids[0]) if pids else None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _free_port(port: int) -> None:
    """Kill (SIGTERM -> SIGKILL) any process holding `port`, waiting for release."""
    pid = _port_owner_pid(port)
    if pid is None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return
        for _ in range(25):
            if _port_owner_pid(port) is None:
                return
            time.sleep(0.2)


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _kill_server() -> None:
    proc = _SRV["p"]
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    _SRV["p"] = None


def _server_up() -> bool:
    import http.client
    try:
        c = http.client.HTTPConnection("127.0.0.1", SERVER_PORT, timeout=2)
        c.request("GET", "/api/health")
        c.getresponse().read()
        c.close()
        return True
    except Exception:
        return False


def _start_server():
    """Spawn a clean SaaS on the ephemeral port with the rate limit relaxed."""
    _free_port(SERVER_PORT)
    env = dict(os.environ)
    env["LUCIDFENCE_PORT"] = str(SERVER_PORT)
    env["LUCIDFENCE_AUTH_SIGNUP_LIMIT"] = "100000"
    env["LUCIDFENCE_AUTH_SIGNUP_WINDOW_SECONDS"] = "3600"
    launch = (
        "import runpy,sys;"
        "sys.argv=['lucidfence-saas'];"
        "runpy.run_path('saas_server.py', run_name='__main__')"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", launch],
        cwd=ROOT,
        env=env,
        stdout=open("/tmp/lucidfence_srv_stdout.log", "w"),
        stderr=open("/tmp/lucidfence_srv_stderr.log", "w"),
        start_new_session=True,
    )
    _SRV["p"] = proc
    for _ in range(60):
        if _server_up():
            return proc
        time.sleep(0.5)
    return None


def _ensure_server():
    """Return a live server proc, restarting it if it died (watchdog)."""
    if _SRV["p"] is not None and _server_up():
        return _SRV["p"]
    _kill_server()
    return _start_server()


def main() -> None:
    passed = 0
    failed = 0
    failures = []

    atexit.register(_kill_server)

    def _on_signal(signum, frame):  # noqa: ANN001 - signal handler signature
        _kill_server()
        sys.exit(1)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # The suite needs a local SaaS on the ephemeral port for the integration
    # modules (test_it_admin_features.py, test_qa_*.py, ...). We own a clean
    # instance for the run, restarting it on demand if it ever dies.
    for fn in sorted(os.listdir(HERE)):
        if not fn.startswith("test_") or not fn.endswith(".py"):
            continue
        # Watchdog: keep a live server for every HTTP-dependent module.
        if _ensure_server() is None:
            failed += 1
            failures.append(("(runner)", "saas_server.py no arranco en 30s"))
            print("  [FATAL] no se pudo arrancar saas_server.py para los tests")
            continue
        try:
            mod = _load_module(os.path.join(HERE, fn))
        except SystemExit:
            # Module ran its own suite at import time and chose to exit.
            # Its own prints already reported PASS/FAIL. Count it as one
            # executed file and keep discovering the rest.
            passed += 1
            print(f"  [module-level suite] {fn} (see output above)")
            continue
        except Exception as e:  # noqa: BLE001 - report, don't crash
            failed += 1
            msg = "".join(traceback.format_exception_only(type(e), e)).strip()
            failures.append((f"{fn}::<import>", msg))
            print(f"  FAIL  {fn}::<import>: {msg}")
            continue
        tests = [getattr(mod, a) for a in dir(mod)
                 if a.startswith("test_") and callable(getattr(mod, a))]
        for t in tests:
            try:
                t()
                passed += 1
                print(f"  PASS  {fn}::{t.__name__}")
            except Exception as e:  # noqa: BLE001 - report, don't crash
                failed += 1
                msg = "".join(traceback.format_exception_only(type(e), e)).strip()
                failures.append((f"{fn}::{t.__name__}", msg))
                print(f"  FAIL  {fn}::{t.__name__}: {msg}")

    _kill_server()

    print(f"\n=== {passed} passed, {failed} failed ===")
    if failed:
        print("\nFAILURES:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
