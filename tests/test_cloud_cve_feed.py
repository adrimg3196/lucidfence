"""Cloud vitrina CVE: usar feed real del engine cuando hay señal y fallback demo si no."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core import cloud_publisher  # noqa: E402
from lucidfence.core import cve  # noqa: E402
import lucidfence.core.cve_feed_nvd as cve_feed_nvd  # noqa: E402


def test_cloud_demo_prefers_engine_cve_feed_when_sync_available():
    old_sync = cve_feed_nvd.sync_nvd_feed
    old_feed = dict(cve._FEED)
    # Use official isolation helpers to prevent cross-test _FEED pollution.
    saved = cve.isolate_feed()

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
            from lucidfence.saas.tenant import TenantStore
            from lucidfence.core.engine import Engine

            workdir = Path(tmp) / "tenant"
            ts = TenantStore(workdir)
            org = ts.create(name="test", owner_id="cloud")
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
        cve.restore_feed(saved or {})


def test_cloud_cve_summary_falls_back_to_demo_without_engine_signal():
    status = {"cve_summary": {"apps_total": 0, "vulnerable_apps": 0}, "devices": []}
    summary = cloud_publisher._cve_summary_for_cloud(status, total=5)
    assert summary["demo"] is True


def test_cloud_demo_seeds_tenant_with_refreshed_repository_cache():
    old_root = cloud_publisher.ROOT
    old_sync = cve_feed_nvd.sync_nvd_feed
    saved = cve.isolate_feed()
    try:
        with tempfile.TemporaryDirectory(prefix="lucidfence-cloud-cache-") as tmp:
            root = Path(tmp) / "repo"
            source = root / "data" / "cve_feed_nvd.json"
            source.parent.mkdir(parents=True)
            payload = {
                "source": "NVD",
                "generated": "2026-09-02T00:00:00Z",
                "apps": {
                    "google chrome": [
                        {
                            "id": "CVE-2099-4242",
                            "severity": "high",
                            "score": 8.0,
                            "title": "cached",
                            "epss": 0.0,
                        }
                    ]
                },
            }
            source.write_text(json.dumps(payload), encoding="utf-8")
            cloud_publisher.ROOT = root
            cve_feed_nvd.sync_nvd_feed = lambda **_kwargs: 0

            engine = cloud_publisher.build_demo_engine(Path(tmp) / "tenant")
            loaded_path = Path(engine.cve_feed_load["path"])

            assert engine.cve_feed_load["ok"] is True, engine.cve_feed_load
            assert loaded_path != source
            assert json.loads(loaded_path.read_text(encoding="utf-8")) == payload
    finally:
        cloud_publisher.ROOT = old_root
        cve_feed_nvd.sync_nvd_feed = old_sync
        cve.restore_feed(saved or {})


def test_engine_cve_feed_load_is_observable_fail_unknown_not_open():
    """Engine must record CVE feed load health on status() and NOT fail-open.

    A broken feed path must surface as cve_feed_load.ok==False (observable),
    never silently degrade to 'no CVEs'. See task t_6479d79a item 8.
    """
    saved = cve.isolate_feed()
    try:
        with tempfile.TemporaryDirectory(prefix="lucidfence-engine-cfe-") as tmp:
            from lucidfence.saas.tenant import TenantStore
            from lucidfence.core.engine import Engine

            ts = TenantStore(tmp)
            org = ts.create(name="t", owner_id="cloud")
            tdir = ts.data_dir(org.id)
            (Path(tdir) / "fences.json").write_text('{"fences": []}', encoding="utf-8")
            (Path(tdir) / "policies.json").write_text("[]", encoding="utf-8")
            (Path(tdir) / "routes.json").write_text("[]", encoding="utf-8")
            cloud_publisher._write_demo_seed(Path(tdir) / "fleet_seed.json")

            # Point the feed loader at a directory (not a file) => osError on load.
            bad_feed = str(Path(tdir) / "no_such_dir")
            eng = Engine({
                "mode": "simulation", "autostart": False, "data_dir": str(tdir),
                "org_id": org.id, "sim_seed_path": str(Path(tdir) / "fleet_seed.json"),
                "fences_path": str(Path(tdir) / "fences.json"),
                "routes_path": str(Path(tdir) / "routes.json"),
                "policies_path": str(Path(tdir) / "policies.json"),
                "cve_feed_path": bad_feed,
            })
            st = eng.status()
            load = st.get("cve_feed_load")
            assert load is not None, "cve_feed_load must be present on status()"
            assert load["ok"] is False, f"broken feed must be observable, got {load}"
            assert load["error"], "error must be recorded (fail-unknown, not fail-open)"
    finally:
        cve.restore_feed(saved or {})
