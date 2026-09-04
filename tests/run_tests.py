"""Zero-dependency test runner for the LucidFence SaaS.

Discovers every `test_*` function in `tests/*.py` and runs them, mirroring
pytest's behaviour without adding a dependency (the product stays stdlib-only).

Run:  python3 tests/run_tests.py
"""
from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)  # so `from helpers import ...` resolves inside tests/

# Run as `python3 tests/run_tests.py`, this module is `__main__`. A test doing
# `from run_tests import SkipTest` would otherwise re-execute this file as a
# SECOND module object with its OWN SkipTest class — a different object than the
# one `main()` catches below, so raised skips would fall through to `except
# Exception` and be miscounted as failures. Aliasing `run_tests` to this very
# module makes the import return THIS SkipTest (same class object we catch).
# Guarded to __main__: when this file is imported/exec'd under another name
# (e.g. the audit regression loads it as `honest_runner`) it is already in
# sys.modules under its own name and needs no alias.
if __name__ == "__main__":
    sys.modules.setdefault("run_tests", sys.modules["__main__"])


_MIN_PY = (3, 11)
if sys.version_info < _MIN_PY:
    sys.stderr.write(
        f"ERROR: LucidFence tests need Python >={'%d.%d' % _MIN_PY}, "
        f"got {sys.version.split()[0]}. Use a venv: python3.11 -m venv .venv && . .venv/bin/activate\n"
    )
    sys.exit(2)


class SkipTest(Exception):
    """Raised by a test_* function when the environment cannot run it.

    A skipped test is neither passed nor failed: it is a test that *could not
    run here* for a declared, honest reason (a pinned dependency absent in this
    container, say), and would run normally where the environment supports it.
    This is NOT a way to silence a real failure — a test that raises anything
    other than SkipTest still counts as failed. See test_oidc_sso.py for the
    canonical use (cryptography pinned version absent → JWK.algorithm_name unset).
    """


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _system_exit_code(exc: SystemExit) -> int:
    """Normalize SystemExit exactly like Python's process semantics."""
    if exc.code is None:
        return 0
    return exc.code if isinstance(exc.code, int) else 1


def _allocate_qa_port() -> int:
    """Ask the kernel for a free loopback port instead of sharing :8765."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main():
    passed = 0
    skipped = 0
    failed = 0
    failures = []
    skips = []
    # Every runner gets its own loopback port. Parallel agents and a real local
    # LucidFence instance may coexist without sharing tenants or HTTP state.
    qa_port = _allocate_qa_port()
    qa_data = tempfile.TemporaryDirectory(prefix="lucidfence-qa-")
    managed_env = {
        "LUCIDFENCE_DATA_DIR": qa_data.name,
        "LUCIDFENCE_PORT": str(qa_port),
        "LUCIDFENCE_TEST_PORT": str(qa_port),
        "LUCIDFENCE_WEB_URL": f"http://127.0.0.1:{qa_port}/static/web.html",
    }
    previous_env = {key: os.environ.get(key) for key in managed_env}
    os.environ.update(managed_env)
    srv = None
    try:
        import http.client

        def _server_up():
            try:
                c = http.client.HTTPConnection("127.0.0.1", qa_port, timeout=2)
                c.request("GET", "/api/health")
                c.getresponse().read()
                c.close()
                return True
            except Exception:
                return False

        srv = subprocess.Popen(
            [sys.executable, "saas_server.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            if _server_up():
                break
            if srv.poll() is not None:
                break
            time.sleep(0.5)
    except Exception:
        pass

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
            except SystemExit as exc:
                # Module ran its own suite at import time and chose to exit.
                # Its own prints already reported PASS/FAIL. Count it as one
                # executed file and keep discovering the rest.
                code = _system_exit_code(exc)
                if code == 0:
                    passed += 1
                    print(f"  [module-level suite] {fn} (exit 0)")
                else:
                    failed += 1
                    msg = f"module-level suite exited {code}"
                    failures.append((f"{fn}::<import>", msg))
                    print(f"  FAIL  {fn}::<import>: {msg}")
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
                except SkipTest as exc:
                    # Not a pass and not a failure: the environment cannot run
                    # this test for a declared reason. It runs normally where
                    # the environment supports it (e.g. CI with pinned deps).
                    skipped += 1
                    reason = str(exc)
                    skips.append((f"{fn}::{t.__name__}", reason))
                    print(f"  SKIP  {fn}::{t.__name__}: {reason}")
                except SystemExit as exc:
                    failed += 1
                    code = _system_exit_code(exc)
                    msg = f"test raised SystemExit({code})"
                    failures.append((f"{fn}::{t.__name__}", msg))
                    print(f"  FAIL  {fn}::{t.__name__}: {msg}")
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
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        qa_data.cleanup()
    if skips:
        print("\nSKIPPED:")
        for name, msg in skips:
            print(f"  - {name}: {msg}")
    print(f"\n=== {passed} passed, {skipped} skipped, {failed} failed ===")
    if failed:
        print("\nFAILURES:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
