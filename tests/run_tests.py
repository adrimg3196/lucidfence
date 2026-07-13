"""Zero-dependency test runner for the Geofence UEM SaaS.

Discovers every `test_*` function in `tests/*.py` and runs them, mirroring
pytest's behaviour without adding a dependency (the product stays stdlib-only).

Run:  python3 tests/run_tests.py
"""
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


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
    for fn in sorted(os.listdir(HERE)):
        if not fn.startswith("test_") or not fn.endswith(".py"):
            continue
        mod = _load_module(os.path.join(HERE, fn))
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
    print(f"\n=== {passed} passed, {failed} failed ===")
    if failed:
        print("\nFAILURES:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
