"""Cloud vitrina CVE: usar feed real del engine cuando hay señal y fallback demo si no."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cloud_publisher  # noqa: E402
from core import cve  # noqa: E402
import core.cve_feed_nvd as cve_feed_nvd  # noqa: E402


def test_cloud_demo_prefers_engine_cve_feed_when_sync_available():
    old_sync = cve_feed_nvd.sync_nvd_feed
    old_feed = dict(cve._FEED)
    # Isolate: the engine merges the NVD feed into the global cve._FEED, and
    # other suites may have populated it. Reset so the fake below is the only
    # source — keeps the assertion deterministic regardless of run order.
    cve._FEED.clear()

    def fake_sync(out_path: str, **_kwargs) -> int:
        payload = {
            "source": "NVD",
            "generated": "2026-07-14T00:00:00Z",
            "apps": {
                "google chrome": [
                    {"id": "CVE-2099-0001", "severity": "critical", "score": 9.8,
                     "title": "test nvd chrome", "epss": 0.0}
                ],
                "zoom": [
                    {"id": "CVE-2099-0002", "severity": "high", "score": 8.1,
                     "title": "test nvd zoom", "epss": 0.0}
                ],
            },
        }
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(payload), encoding="utf-8")
        return 2

    cve_feed_nvd.sync_nvd_feed = fake_sync
    try:
        with tempfile.TemporaryDirectory(prefix="lucidfence-cloud-cve-") as tmp:
            feed_path = Path(tmp) / "cve_feed_nvd.json"
            # Aislar el feed para que el test no toque data/cve_feed_nvd.json del repo.
            from saas.tenant import TenantStore
            from core.engine import Engine

            workdir = Path(tmp) / "tenant"
            ts = TenantStore(workdir)
            org = ts.create(name="test", owner_id="cloud", plan="pro")
            tdir = ts.data_dir(org.id)
            (tdir / "fences.json").write_text(json.dumps({"fences": []}), encoding="utf-8")
            (tdir / "policies.json").write_text("[]", encoding="utf-8")
            (tdir / "routes.json").write_text("[]", encoding="utf-8")
            cloud_publisher._write_demo_seed(tdir / "fleet_seed.json")

            eng = Engine({
                "mode": "simulation",
                "autostart": False,
                "data_dir": str(tdir),
                "org_id": org.id,
                "sim_seed_path": str(tdir / "fleet_seed.json"),
                "fences_path": str(tdir / "fences.json"),
                "routes_path": str(tdir / "routes.json"),
                "policies_path": str(tdir / "policies.json"),
                "cve_feed_path": str(feed_path),
                "cve_feed_sync": True,
                "cve_feed_sleep_s": 0,
            })
            eng.run_once()
            payload = cloud_publisher.serialize(eng, eng.org_id)

        summary = payload["cve_summary"]
        assert summary.get("demo") is False, summary
        assert summary.get("source") == "engine-cve-feed", summary
        assert summary.get("vulnerable_apps", 0) >= 2, summary
        ids = {e["cve"] for e in summary.get("ejemplos", [])}
        assert "CVE-2099-0001" in ids, summary
    finally:
        cve_feed_nvd.sync_nvd_feed = old_sync
        cve._FEED.clear()
        cve._FEED.update(old_feed)


def test_cloud_cve_summary_falls_back_to_demo_without_engine_signal():
    status = {"cve_summary": {"apps_total": 0, "vulnerable_apps": 0}, "devices": []}
    summary = cloud_publisher._cve_summary_for_cloud(status, total=5)
    assert summary["demo"] is True
    assert summary["vulnerable_apps"] > 0
