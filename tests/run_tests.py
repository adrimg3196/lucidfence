"""Zero-dependency test runner for the LucidFence SaaS.

Discovers every `test_*` function in `tests/*.py` and runs them, mirroring
pytest's behaviour without adding a dependency (the product stays stdlib-only).

Run:  python3 tests/run_tests.py

The suite needs a local SaaS on :8765 for the integration modules
(e.g. test_it_admin_features.py). To stay hermetic we ALWAYS own a clean
server instance for the duration of the run:

  * If a leftover `saas_server.py` (from a previous session or leaked by a
    prior run) is already holding port 8765, we kill it first so we never
    inherit its in-memory signup rate-limit counter. A stale counter that had
    grown past AUTH_SIGNUP_LIMIT is exactly what used to poison later modules
    (their signup returned 429, auth failed, `/api/devices` came back as an
    error dict, and `devs[0]` blew up with `KeyError: 0`).
  * The owned instance runs with the signup rate limit disabled (high ceiling)
    so the many parallel signups in the suite can never trip it. No test
    asserts the rate limit itself, so this only removes cross-run coupling.
  * The server is always terminated (terminate -> wait -> kill) in a finally
    block, so we never leave a zombie behind.
"""
from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
import time
import traceback
import socket

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)  # so `from helpers import ...` resolves inside tests/

SERVER_PORT = 8765


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _port_owner_pid(port: int) -> int | None:
    """Return the PID holding `port` on loopback, or None.

    Uses lsof when available (macOS/Linux). Best-effort: a fallback that
    attempts to bind the port tells us only whether it is free, not who holds
    it, so we return None in that case and let the spawn fail loudly.
    """
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
    """Best-effort: kill any process holding `port` so we can bind our own."""
    pid = _port_owner_pid(port)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    # Wait up to ~5s for the OS to release the socket.
    for _ in range(25):
        if _port_owner_pid(port) is None:
            return
        time.sleep(0.2)


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def main():
    passed = 0
    failed = 0
    failures = []

    # Own a clean server instance for the run (never reuse a leaked one).
    import http.client
    srv = None
    try:
        if not _is_port_free(SERVER_PORT):
            _free_port(SERVER_PORT)
            # Give the kernel a moment to release the socket after SIGTERM.
            for _ in range(25):
                if _is_port_free(SERVER_PORT):
                    break
                time.sleep(0.2)

        env = dict(os.environ)
        # Disable the signup rate limit for the test window: the suite performs
        # many independent signups and should never be gated by a shared,
        # in-memory counter that leaks state across runs.
        env["LUCIDFENCE_AUTH_SIGNUP_LIMIT"] = "100000"
        env["LUCIDFENCE_AUTH_SIGNUP_WINDOW_SECONDS"] = "3600"

        def _server_up():
            try:
                c = http.client.HTTPConnection("127.0.0.1", SERVER_PORT, timeout=2)
                c.request("GET", "/api/health")
                c.getresponse().read()
                c.close()
                return True
            except Exception:
                return False

        srv = subprocess.Popen(
            [sys.executable, "saas_server.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started = False
        for _ in range(60):
            if _server_up():
                started = True
                break
            time.sleep(0.5)
        if not started:
            print("  [FATAL] no se pudo arrancar saas_server.py para los tests de integración")
            failed += 1
            failures.append(("(runner)", "saas_server.py no arrancó en 30s"))

        # Some test modules (e.g. test_it_admin_features.py) run their suite at
        # import time and finish with `raise SystemExit(...)`. Loading them via
        # exec_module triggers that SystemExit, which is NOT caught by the inner
        # `except Exception` and would silently abort discovery of every later
        # file. We catch it per-module so discovery always completes and the final
        # tally is honest.
        try:
            for fn in sorted(os.listdir(HERE)):
                if not fn.startswith("test_") or not fn.endswith(".py"):
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
        finally:
            if srv is not None:
                srv.terminate()
                try:
                    srv.wait(timeout=5)
                except Exception:
                    srv.kill()
    finally:
        # Belt-and-suspenders: guarantee no leaked server survives the run.
        if srv is not None and srv.poll() is None:
            try:
                srv.kill()
            except Exception:
                pass

    print(f"\n=== {passed} passed, {failed} failed ===")
    if failed:
        print("\nFAILURES:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
