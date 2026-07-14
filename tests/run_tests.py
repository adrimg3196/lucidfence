"""Zero-dependency test runner for the LucidFence SaaS.

Discovers every `test_*.py` in `tests/` and runs it, mirroring pytest's
behaviour without adding a dependency (the product stays stdlib-only).

Why subprocess isolation?
-------------------------
Several modules (test_qa_workflows, test_qa_e2e, test_it_admin_features, ...)
share ONE long-lived SaaS on :8765 and MUTATE its in-memory state (signup
rate-limit counter, the seeded demo owner, the simulation fleet). Loading them
in a single process let that state leak from one module to the next: a saturated
rate-limit counter or a clobbered demo user made later modules fail with
`KeyError: 0`, `credenciales inválidas`, or "no incidents derived". So each
test file is executed as its OWN subprocess (`python3 tests/<file>.py`), with a
single freshly-spawned, isolated SaaS on :8765 that is reclaimed from any
leftover process and torn down afterwards. State never leaks between modules.

The real per-module test counts are aggregated from each subprocess's own
`PASS`/`FAIL` lines so the final `N passed, M failed` reflects actual checks
(not just file count), which is what scripts/lucidfence_monitor.py gates on
(min 110 passed).

Notes:
  * The server is spawned with a Python >= 3.10 interpreter (the product source
    uses PEP 604 `X | None` syntax at runtime), preferring the repo's `.venv`.
  * The server runs against the real `data/` so the committed demo account
    (ciso@acme.test) and seeded simulation fleet needed by a few integration
    tests are present. We own a FRESH server on :8765 (reclaiming any leftover)
    so we never inherit a dev server's in-memory signup rate-limit counter or
    collide with a server already bound to the port.
"""

from __future__ import annotations

import atexit
import os
import re
import signal
import socket
import subprocess
import sys
import time
from typing import List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVER_PORT = 8765

_SRV = {"p": None}  # type: ignore[var-annotated]

# Lines like "  PASS foo", "  [PASS] bar", "FAIL baz" emitted by the modules.
_PASS_RE = re.compile(r"^\s*(?:\[)?PASS\b", re.IGNORECASE)
_FAIL_RE = re.compile(r"^\s*(?:\[)?FAIL\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Python interpreter selection (the product requires >= 3.10)                  #
# --------------------------------------------------------------------------- #
def _python3_10plus() -> str:
    """Find a Python interpreter >= 3.10 (the product uses 3.10+ syntax).

    Prefers a local .venv if present, then common candidates. Falls back to
    sys.executable (caller's python3) even if older -- the server spawn will
    surface a clear SyntaxError rather than us guessing wrong.
    """
    candidates: List[str] = []
    venv_py = os.path.join(ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_py):
        candidates.append(venv_py)
    candidates += [
        "python3.13", "python3.12", "python3.11", "python3.10",
        "python3.14", "python3", sys.executable,
    ]
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            out = subprocess.run(
                [cand, "-c", "import sys;print(sys.version_info[:2])"],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        if out.returncode != 0:
            continue
        try:
            major, minor = eval(out.stdout.strip())  # noqa: S307 - our own literal tuple
        except Exception:
            continue
        if (major, minor) >= (3, 10):
            return cand
    return sys.executable


# --------------------------------------------------------------------------- #
# Port reclamation (kill any leftover server so we own a clean :8765)          #
# --------------------------------------------------------------------------- #
def _port_owner_pid(port: int) -> Optional[int]:
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


def _start_server() -> Optional["subprocess.Popen"]:
    """Spawn a clean SaaS on :8765 with the rate limit relaxed. Returns proc."""
    if _port_owner_pid(SERVER_PORT) is not None:
        _free_port(SERVER_PORT)
        for _ in range(25):
            if _port_owner_pid(SERVER_PORT) is None:
                break
            time.sleep(0.2)
    py = _python3_10plus()
    env = dict(os.environ)
    env["LUCIDFENCE_AUTH_SIGNUP_LIMIT"] = "100000"
    env["LUCIDFENCE_AUTH_SIGNUP_WINDOW_SECONDS"] = "3600"
    env["LUCIDFENCE_PORT"] = str(SERVER_PORT)
    env["LUCIDFENCE_HOST"] = "127.0.0.1"
    proc = subprocess.Popen(
        [py, "saas_server.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _SRV["p"] = proc
    for _ in range(60):
        if _server_up():
            return proc
        time.sleep(0.5)
    return None


def _count_checks(out: str) -> Tuple[int, int]:
    """Count PASS/FAIL lines a module emitted so we report real test counts."""
    passed = 0
    failed = 0
    for line in out.splitlines():
        if _PASS_RE.match(line):
            passed += 1
        elif _FAIL_RE.match(line):
            failed += 1
    return passed, failed


def _run_one_module(path: str) -> Tuple[int, str]:
    """Execute a single test file as a subprocess. Returns (exit_code, output)."""
    env = dict(os.environ)
    env["LUCIDFENCE_PORT"] = str(SERVER_PORT)
    env["LUCIDFENCE_HOST"] = "127.0.0.1"
    # Mirror the loader's sys.path so `from core import ...`, `from saas.x import ...`
    # and `from helpers import ...` resolve inside the subprocess too.
    existing = env.get("PYTHONPATH", "")
    extra = os.pathsep.join([ROOT, HERE])
    env["PYTHONPATH"] = (extra + os.pathsep + existing) if existing else extra
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") + (exc.stderr or "")
        return 124, out
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def main() -> None:
    total_passed = 0
    total_failed = 0
    modules_failed: List[Tuple[str, str]] = []

    atexit.register(_kill_server)

    def _on_signal(signum, frame):  # noqa: ANN001 - signal handler signature
        _kill_server()
        sys.exit(1)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    files = sorted(
        os.path.join(HERE, fn)
        for fn in os.listdir(HERE)
        if fn.startswith("test_") and fn.endswith(".py")
    )

    server_started = False
    for path in files:
        name = os.path.basename(path)
        # Every integration module needs the server; pure-logic ones don't.
        needs_server = True
        if needs_server:
            if not server_started or not _server_up():
                _kill_server()
                proc = _start_server()
                server_started = proc is not None
                if not server_started:
                    modules_failed.append((name, "no se pudo arrancar saas_server.py"))
                    print(f"  FAIL  {name}: no se pudo arrancar saas_server.py")
                    total_failed += 1
                    continue
            code, out = _run_one_module(path)
            mod_p, mod_f = _count_checks(out)
            if code == 0 and mod_f == 0:
                total_passed += mod_p
                total_failed += mod_f
                summary = ""
                for line in reversed(out.splitlines()):
                    if "passed" in line or "OK" in line or "complete" in line:
                        summary = line.strip()
                        break
                print(f"  PASS  {name} ({mod_p} checks)" + (f" :: {summary}" if summary else ""))
            else:
                total_failed += max(mod_f, 1)
                tail = "\n".join(out.strip().splitlines()[-8:])
                modules_failed.append((name, tail))
                print(f"  FAIL  {name} (exit={code}, {mod_p} passed / {mod_f} failed)")
                if tail:
                    print("        " + tail.replace("\n", "\n        "))

    _kill_server()

    print(f"\n=== {total_passed} passed, {total_failed} failed ===")
    if modules_failed:
        print("\nFAILURES:")
        for name, msg in modules_failed:
            print(f"  - {name}:")
            for ln in msg.splitlines():
                print(f"      {ln}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
