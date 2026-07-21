"""Performance regression guardrails for the LucidFence engine.

Run:
    python3 tests/run_tests.py

Thresholds are chosen from local baseline on a 10-device simulation tenant.
"""
from __future__ import annotations

import importlib.util
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.engine import Engine


def _build_tenant(tmp: Path) -> Path:
    api_spec = importlib.util.spec_from_file_location("saas_api_op", ROOT / "scripts" / "saas_api_op.py")
    api = importlib.util.module_from_spec(api_spec)
    assert api_spec and api_spec.loader
    api_spec.loader.exec_module(api)
    api.BASE = tmp / "data" / "cloud_tenants"
    payload = {
        "name": "Perf bench",
        "fleet": [
            {
                "id": f"dev-{i}",
                "name": f"Device {i}",
                "platform": "android",
                "lat": 40.4168 + (i % 5) * 0.001,
                "lng": -3.7038 + (i % 5) * 0.001,
                "compliant": True,
                "department": "Ops",
            }
            for i in range(10)
        ],
        "fences": [
            {
                "id": "f1",
                "name": "HQ",
                "kind": "circle",
                "center": {"lat": 40.4168, "lng": -3.7038},
                "radius_m": 500,
            }
        ],
    }
    api.create_tenant("perf-bench", payload)
    return api.BASE / "perf-bench"


def test_engine_tick_p95_regression() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="lucidfence-perf-"))
    tdir = _build_tenant(tmp)
    tdata = tdir / "data"
    cfg = {
        "mode": "simulation",
        "autostart": False,
        "data_dir": str(tdata),
        "org_id": tdir.name,
        "sim_seed_path": str(tdata / "fleet_seed.json"),
        "fences_path": str(tdata / "fences.json"),
        "routes_path": str(tdata / "routes.json"),
        "policies_path": str(tdata / "policies.json"),
        "action_cooldown_seconds": 3600,
        "incident_webhook_url": "",
    }
    eng = Engine(cfg)

    samples = []
    for _ in range(20):
        t0 = time.perf_counter()
        eng.run_once()
        samples.append(time.perf_counter() - t0)

    p95 = sorted(samples)[int(len(samples) * 0.95)]
    mean = statistics.mean(samples)
    print(f"perf bench mean={mean:.4f}s p95={p95:.4f}s")
    assert p95 < 0.05, f"engine tick p95 regression: {p95:.4f}s"
