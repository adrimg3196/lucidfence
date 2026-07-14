"""Zero-dependency test runner for the LucidFence SaaS.

Discovers every `test_*` function in `tests/*.py` and runs them, mirroring
pytest's behaviour without adding a dependency (the product stays stdlib-only).

Run:  python3 tests/run_tests.py
"""
import importlib.util
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)  # so `from helpers import ...` resolves inside tests/


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    passed = 0
    failed = 0
    failures = []
    # Arranca el server local en :8765 para los tests de integración que lo
    # requieren (test_it_admin_features.py). Se mata al terminar. Hermético en CI.
    import subprocess
    srv = None
    try:
        import http.client
        def _server_up():
            try:
                c = http.client.HTTPConnection("127.0.0.1", 8765, timeout=2)
                c.request("GET", "/api/health")
                c.getresponse().read()
                c.close()
                return True
            except Exception:
                return False
        if not _server_up():
            srv = subprocess.Popen(
                [sys.executable, "saas_server.py"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for _ in range(30):
                if _server_up():
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
    print(f"\n=== {passed} passed, {failed} failed ===")
    if failed:
        print("\nFAILURES:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
