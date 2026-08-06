"""Tests for the tenant-local multi-UEM provider registry (lucidfence.saas.providers).

Offline: round-trips a provider list through integration.json and proves the
secret is masked on read-back.

Run via the runner:  python3 tests/run_tests.py
Run directly:        python3 tests/test_provider_registry.py
"""
import os
import sys
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from pathlib import Path
from lucidfence.saas.providers import list_providers, save_providers, mask_provider

passed = 0
fails = []


def check(cond, msg):
    global passed
    if cond:
        passed += 1
        print("  PASS", msg)
    else:
        fails.append(msg)
        print("  FAIL", msg)


def test_roundtrip_and_mask():
    tmp = Path(tempfile.mkdtemp())
    tdir = tmp / "tenants" / "org_x"
    tdir.mkdir(parents=True)
    provs = [
        {"name": "applivery", "org_id": "o1", "endpoint": "https://api.x/v1", "secret": "sk-123"},
        {"name": "jamf", "org_id": "o2", "secret": "sk-456"},
    ]
    save_providers(tdir, provs)
    got = list_providers(tdir)
    check(len(got) == 2, "two providers persisted")
    check(any(p["name"] == "applivery" and p.get("secret") == "sk-123" for p in got),
          "secret stored on disk (0600 tenant file)")
    # mask_provider must drop the secret and flag configured
    masked = [mask_provider(p) for p in got]
    check(all("secret" not in p for p in masked), "masked provider drops secret")
    check(all(p.get("configured") is True for p in masked), "masked provider flagged configured")
    # integration.json must exist and be 0600
    mode = (tdir / "integration.json").stat().st_mode & 0o777
    check(mode == 0o600, f"integration.json is 0600 (got {oct(mode)})")
    # raw file still has the secret (proves it's isolated, not leaked via mask)
    raw = json.loads((tdir / "integration.json").read_text())
    check(any(p.get("secret") for p in raw.get("providers", [])), "secret present in raw file only")


def test_empty_default():
    tmp = Path(tempfile.mkdtemp())
    tdir = tmp / "tenants" / "org_empty"
    tdir.mkdir(parents=True)
    check(list_providers(tdir) == [], "no integration.json -> empty list")


if __name__ == "__main__":
    test_roundtrip_and_mask()
    test_empty_default()
    print(f"\n=== provider-registry: {passed} passed, {len(fails)} failed ===")
    sys.exit(1 if fails else 0)
