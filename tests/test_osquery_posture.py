"""Contract tests for the optional osquery posture integration."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from lucidfence.core.osquery_posture import (
    COMMON_QUERIES,
    OsqueryPostureProvider,
    normalize_posture,
    parse_result_event,
    read_result_log,
)
from lucidfence.core.engine import Engine
from lucidfence.core.location_source import LocationReport
from lucidfence.core.policies import RiskEngine


def _table(rows, ts=1_700_000_000):
    return {"rows": rows, "ts": ts}


def test_parse_official_snapshot_and_reject_differential_formats():
    snapshot = parse_result_event({
        "name": "lucidfence_os_version",
        "hostIdentifier": "host-a",
        "unixTime": "1700000000",
        "snapshot": [{"name": "macOS", "version": "15.5"}],
    })
    assert snapshot == {
        "host": "host-a",
        "query": "os_version",
        "rows": [{"name": "macOS", "version": "15.5"}],
        "ts": 1_700_000_000.0,
    }

    differential = parse_result_event({
        "name": "pack_lucidfence_lucidfence_osquery_info",
        "hostIdentifier": "host-b",
        "unixTime": 1_700_000_001,
        "action": "added",
        "columns": {"version": "5.19.0", "config_valid": "1"},
    })
    assert differential is None
    assert parse_result_event({
        **{
            "name": "lucidfence_osquery_info",
            "hostIdentifier": "host-b",
            "columns": {"version": "old"},
        },
        "action": "removed",
    }) is None


def test_parser_ignores_unknown_queries_and_missing_identity():
    assert parse_result_event({
        "name": "other_pack_processes",
        "hostIdentifier": "host-a",
        "snapshot": [],
    }) is None
    assert parse_result_event({
        "name": "lucidfence_os_version",
        "snapshot": [],
    }) is None


def test_result_log_is_bounded_and_skips_bad_json():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "results.log"
        lines = [
            "{not-json}",
            json.dumps({
                "name": "lucidfence_os_version",
                "hostIdentifier": "host-a",
                "unixTime": "1700000000",
                "snapshot": [{"name": "Ubuntu", "version": "24.04"}],
            }),
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        events = read_result_log(path, max_bytes=4096, max_lines=5)
        assert len(events) == 1
        assert events[0]["host"] == "host-a"


def test_normalize_posix_posture():
    gib = 1024 ** 3
    posture = normalize_posture({
        "system_info": _table([{
            "hostname": "mac-01",
            "uuid": "uuid-01",
            "hardware_vendor": "Apple Inc.",
            "hardware_model": "MacBookPro18,3",
            "hardware_serial": "SERIAL01",
        }]),
        "os_version": _table([{"name": "macOS", "version": "15.5", "platform": "darwin"}]),
        "osquery_info": _table([{"version": "5.19.0", "config_valid": "1"}]),
        "mounts": _table([{
            "device": "/dev/disk3s1",
            "path": "/",
            "blocks_size": "4096",
            "blocks": str(100 * gib // 4096),
            "blocks_available": str(8 * gib // 4096),
        }]),
        "disk_encryption": _table([{
            "name": "/dev/disk3s1",
            "encrypted": "1",
            "encryption_status": "encrypted",
        }]),
        "battery": _table([{
            "state": "Battery Power",
            "charging": "0",
            "charged": "0",
            "percent_remaining": "14",
        }]),
    })
    assert posture["posture_source"] == "osquery"
    assert posture["os_version"] == "macOS 15.5"
    assert posture["storage_total_gb"] == 100.0
    assert posture["storage_free_gb"] == 8.0
    assert posture["encryption_enabled"] is True
    assert posture["battery_level"] == 14
    assert posture["battery_state"] == "discharging"
    assert posture["osquery_config_valid"] is True
    assert posture["serial_number"] == "SERIAL01"


def test_normalize_windows_bitlocker_and_boot_drive():
    gib = 1024 ** 3
    posture = normalize_posture({
        "logical_drives": _table([{
            "device_id": "C:",
            "size": str(256 * gib),
            "free_space": str(20 * gib),
            "boot_partition": "1",
        }]),
        "bitlocker": _table([{
            "device_id": r"\\?\Volume{abc}",
            "drive_letter": "C:",
            "protection_status": "1",
            "percentage_encrypted": "100",
        }]),
    })
    assert posture["storage_total_gb"] == 256.0
    assert posture["storage_free_gb"] == 20.0
    assert posture["encryption_enabled"] is True


def test_provider_maps_host_identity_and_rejects_stale_events():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "results.log"
        path.write_text("\n".join([
            json.dumps({
                "name": "lucidfence_system_info",
                "hostIdentifier": "host-a",
                "unixTime": "1700000000",
                "snapshot": [{"hostname": "sales-mac", "hardware_serial": "SERIAL01"}],
            }),
            json.dumps({
                "name": "lucidfence_os_version",
                "hostIdentifier": "host-a",
                "unixTime": "1700000000",
                "snapshot": [{"name": "macOS", "version": "15.5"}],
            }),
        ]) + "\n", encoding="utf-8")
        provider = OsqueryPostureProvider({
            "enabled": True,
            "mode": "results_log",
            "results_path": str(path),
            "host_map": {"SERIAL01": "uem-device-42"},
            "max_age_seconds": 900,
        })
        provider.refresh(now=1_700_000_100)
        assert provider.posture_for("uem-device-42")["os_version"] == "macOS 15.5"
        assert provider.status()["fresh"] == 1

        # Staleness threshold must reject aged events.
        provider.refresh(now=1_700_002_000)
        assert provider.posture_for("uem-device-42")["encryption_enabled"] is False  # fails closed!
        assert provider.status()["fresh"] == 0

        # A forged far-future timestamp must not remain permanently fresh.
        path.write_text(json.dumps({
            "name": "lucidfence_os_version",
            "hostIdentifier": "host-a",
            "unixTime": "1800000000",
            "snapshot": [{"name": "macOS", "version": "99"}],
        }) + "\n", encoding="utf-8")
        provider.refresh(now=1_700_000_100)
        assert provider.posture_for("uem-device-42")["encryption_enabled"] is False  # fails closed!
        assert provider.status()["fresh"] == 0


def test_provider_never_disables_staleness():
    provider = OsqueryPostureProvider({
        "enabled": True,
        "max_age_seconds": 0,
    })
    assert provider.max_age_seconds == 60


def test_provider_drops_ambiguous_aliases_until_hosts_are_explicitly_mapped():
    provider = OsqueryPostureProvider({"enabled": True})
    hosts = {
        "host-id-a": {
            "system_info": _table([{"hostname": "shared-name", "hardware_serial": "SERIAL-A"}]),
            "os_version": _table([{"name": "macOS", "version": "15.5"}]),
        },
        "host-id-b": {
            "system_info": _table([{"hostname": "shared-name", "hardware_serial": "SERIAL-B"}]),
            "os_version": _table([{"name": "Windows", "version": "11"}]),
        },
    }
    provider._index_hosts(hosts)
    assert provider.posture_for("shared-name") == {}
    assert provider.posture_for("host-id-a")["os_version"] == "macOS 15.5"
    assert provider.posture_for("host-id-b")["os_version"] == "Windows 11"

    explicit = OsqueryPostureProvider({
        "enabled": True,
        "host_map": {"host-id-a": "uem-a", "host-id-b": "uem-b"},
    })
    explicit._index_hosts(hosts)
    assert explicit.posture_for("uem-a")["os_version"] == "macOS 15.5"
    assert explicit.posture_for("uem-b")["os_version"] == "Windows 11"


def test_local_mode_executes_only_fixed_queries_without_shell():
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

        class Result:
            returncode = 0
            stdout = "[]"
        return Result()

    provider = OsqueryPostureProvider({
        "enabled": True,
        "mode": "local",
        "device_id": "local-device",
        "binary": "/usr/local/bin/osqueryi",
    })
    with patch("lucidfence.core.osquery_posture.subprocess.run", fake_run):
        provider.refresh(now=1_700_000_000)
    assert calls
    for argv, kwargs in calls:
        assert argv[0] == "/usr/local/bin/osqueryi"
        assert argv[1] == "--json"
        assert argv[2] in COMMON_QUERIES.values() or argv[2].startswith("SELECT ")
        assert kwargs["shell"] is False
        assert kwargs["timeout"] <= 30


def test_local_mode_rejects_non_osquery_executable():
    provider = OsqueryPostureProvider({
        "enabled": True,
        "mode": "local",
        "device_id": "local-device",
        "binary": "/bin/sh",
    })
    provider.refresh(now=1_700_000_000)
    assert "osquery.binary" in provider.status()["error"]


def test_osquery_evidence_changes_geospatial_risk_explainably():
    risk = RiskEngine().evaluate({
        "device_id": "dev-1",
        "compliant": True,
        "storage_total_gb": 100,
        "storage_free_gb": 8,
        "encryption_enabled": False,
        "battery_level": 14,
        "os_version": "macOS 15.5",
        "osquery_config_valid": False,
    }, "inside", {"hour": 12})
    assert risk["risk_score"] >= 29
    assert "disco casi lleno (<10% libre)" in risk["reasons"]
    assert "almacenamiento sin cifrar" in risk["reasons"]
    assert "batería crítica (≤15%)" in risk["reasons"]
    assert "configuración de osquery no válida" in risk["reasons"]


def test_unknown_encryption_is_not_treated_as_disabled():
    risk = RiskEngine().evaluate({
        "device_id": "dev-unknown",
        "compliant": True,
        "encryption_enabled": None,
    }, "inside", {"hour": 12})
    assert "almacenamiento sin cifrar" not in risk["reasons"]


def test_engine_merges_osquery_posture_before_risk_evaluation():
    class OneDeviceSource:
        def fetch(self):
            return [LocationReport(
                device_id="uem-01",
                name="Endpoint 01",
                platform="macos",
                lat=40.4168,
                lng=-3.7038,
                compliant=True,
            )]

    class FixedPosture:
        def refresh(self):
            return None

        def posture_for(self, device_id, *, aliases=()):
            assert device_id == "uem-01"
            return {
                "posture_source": "osquery",
                "posture_collected_at": "2026-07-28T20:00:00+00:00",
                "storage_total_gb": 100.0,
                "storage_free_gb": 5.0,
                "encryption_enabled": False,
                "osquery_version": "5.19.0",
                "osquery_config_valid": True,
            }

        def status(self):
            return {"enabled": True, "mode": "test", "hosts": 1, "fresh": 1, "error": None}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "fences.json").write_text('{"fences":[]}', encoding="utf-8")
        (root / "routes.json").write_text("[]", encoding="utf-8")
        (root / "policies.json").write_text("[]", encoding="utf-8")
        engine = Engine({
            "mode": "simulation",
            "data_dir": str(root / "data"),
            "fences_path": str(root / "fences.json"),
            "routes_path": str(root / "routes.json"),
            "policies_path": str(root / "policies.json"),
            "sim_seed_path": str(root / "seed.json"),
        })
        engine.source = OneDeviceSource()
        engine.osquery = FixedPosture()
        stats = engine.run_once()

        state = engine.store.get("uem-01")
        assert state is not None
        assert state.posture_source == "osquery"
        assert state.storage_free_gb == 5.0
        assert state.encryption_enabled is False
        assert state.risk_score >= 23
        assert stats["osquery_posture"]["fresh"] == 1


def test_engine_integration_with_actual_jsonl_results_including_corruption():
    """Integration test that starts a real cycle with Engine, reads a real JSONL

    log with valid and malformed lines, and asserts the engine maps it safely
    and detects the correct posture fields.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log_path = root / "osqueryd.results.log"
        now_ts = 1700000000.0

        # Write valid system info and mounts data alongside some corrupted lines
        log_path.write_text("\n".join([
            "{invalid-corrupt-line-not-json}",
            json.dumps({
                "name": "lucidfence_system_info",
                "hostIdentifier": "host-test-1",
                "unixTime": str(now_ts),
                "snapshot": [{"hostname": "test-host-name-1", "hardware_serial": "SERIAL-TEST-1"}]
            }),
            "{another-bad-line}",
            json.dumps({
                "name": "lucidfence_disk_encryption",
                "hostIdentifier": "host-test-1",
                "unixTime": str(now_ts),
                "snapshot": [{"name": "/dev/disk3s1", "encrypted": "1"}]
            }),
            json.dumps({
                "name": "lucidfence_mounts",
                "hostIdentifier": "host-test-1",
                "unixTime": str(now_ts),
                "snapshot": [{
                    "device": "/dev/disk3s1",
                    "path": "/",
                    "blocks_size": "4096",
                    "blocks": str(100 * (1024**3) // 4096),
                    "blocks_available": str(8 * (1024**3) // 4096)
                }]
            })
        ]) + "\n", encoding="utf-8")

        # Configure Engine
        (root / "fences.json").write_text('{"fences":[]}', encoding="utf-8")
        (root / "routes.json").write_text("[]", encoding="utf-8")
        (root / "policies.json").write_text("[]", encoding="utf-8")

        engine = Engine({
            "mode": "simulation",
            "data_dir": str(root / "data"),
            "fences_path": str(root / "fences.json"),
            "routes_path": str(root / "routes.json"),
            "policies_path": str(root / "policies.json"),
            "sim_seed_path": str(root / "seed.json"),
            "osquery": {
                "enabled": True,
                "mode": "results_log",
                "results_path": str(log_path),
                "host_map": {"SERIAL-TEST-1": "device-uem-1"},
                "max_age_seconds": 900
            }
        })

        class MockSource:
            def fetch(self):
                return [LocationReport(
                    device_id="device-uem-1",
                    name="Test Device 1",
                    platform="macos",
                    lat=40.4168,
                    lng=-3.7038,
                    compliant=True,
                    serial_number="SERIAL-TEST-1"
                )]

        engine.source = MockSource()

        # Run cycle with patch on current time matching JSONL timestamps
        with patch("time.time", return_value=now_ts + 10):
            engine.run_once()

        # Verify posture mapping and storage/encryption updating
        state = engine.store.get("device-uem-1")
        assert state is not None
        assert state.posture_source == "osquery"
        assert state.encryption_enabled is True
        assert state.storage_total_gb == 100.0
        assert state.storage_free_gb == 8.0


def test_engine_integration_fail_closed_on_corrupt_log():
    """Assures fail-closed behavior when the results log is fully corrupt."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log_path = root / "osqueryd.results.log"
        # Write fully corrupt lines
        log_path.write_text("{\n{not-json-line}\n", encoding="utf-8")

        # Configure Engine
        (root / "fences.json").write_text('{"fences":[]}', encoding="utf-8")
        (root / "routes.json").write_text("[]", encoding="utf-8")
        (root / "policies.json").write_text("[]", encoding="utf-8")

        engine = Engine({
            "mode": "simulation",
            "data_dir": str(root / "data"),
            "fences_path": str(root / "fences.json"),
            "routes_path": str(root / "routes.json"),
            "policies_path": str(root / "policies.json"),
            "sim_seed_path": str(root / "seed.json"),
            "osquery": {
                "enabled": True,
                "mode": "results_log",
                "results_path": str(log_path),
                "host_map": {"SERIAL-FAIL": "device-uem-fail"},
                "max_age_seconds": 900
            }
        })

        class MockSource:
            def fetch(self):
                return [LocationReport(
                    device_id="device-uem-fail",
                    name="Fail Device",
                    platform="macos",
                    lat=40.4168,
                    lng=-3.7038,
                    compliant=True,
                    serial_number="SERIAL-FAIL"
                )]

        engine.source = MockSource()
        engine.run_once()

        # Verify state store has fail-closed (not compliant / no encryption) posture
        state = engine.store.get("device-uem-fail")
        assert state is not None
        assert state.posture_source == "osquery"
        assert state.encryption_enabled is False
        assert state.osquery_config_valid is False
        assert "ValueError" in engine.osquery.status()["error"]
