"""Regression test for #310: saas_api_op.main() must exit non-zero (2) on
authorization denial, NOT return/exit 0. A serverless function that exits 0
after rejecting a mutation looks successful to the platform -> fail-open in
observability (dashboards, retries, alerting). Denial == failure.

Assignee: empresa-ceo. Fix lives in scripts/saas_api_op.py (sys.exit(2)).
"""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_denial_exits_2_not_0():
    mod = _load(ROOT / "scripts" / "saas_api_op.py")
    # No secret configured -> authorize() fails-closed. Denial must exit(2).
    env = {"ACTION": "remove_tenant", "TENANT_ID": "victim", "PAYLOAD": "{}"}
    saved = {k: os.environ.get(k) for k in
             ("LUCIDFENCE_API_SECRET", "LUCIDFENCE_API_SIGNATURE",
              "LUCIDFENCE_API_ROLE", "ACTION", "TENANT_ID", "PAYLOAD")}
    for k in saved:
        os.environ.pop(k, None)
    try:
        os.environ.update(env)
        raised = None
        try:
            mod.main()
        except SystemExit as e:
            raised = e
        assert raised is not None, "denial must call sys.exit, not return silently"
        assert raised.code == 2, f"denial exit code must be 2 (fail-closed), got {raised.code}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    test_denial_exits_2_not_0()
    print("OK: denial exit(2) regression test passes")
