"""Tests de la fuente de posture osquery (parse del results log + enrich).

Herméticos: escriben logs sintéticos en tempdir, no requieren osquery
instalado y NUNCA tocan red.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.core.posture_osquery import (  # noqa: E402
    OsqueryPosture,
    parse_results_log,
)


def check(cond, msg):
    assert cond, f"FAIL: {msg}"


NOW = 1_785_270_000.0


def _log(lines) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="lucidfence-osq-")) / "osqueryd.results.log"
    tmp.write_text("\n".join(json.dumps(l) if isinstance(l, dict) else l for l in lines),
                   encoding="utf-8")
    return tmp


def _snap(name, host, rows, ts=NOW):
    return {"name": name, "hostIdentifier": host, "unixTime": ts,
            "action": "snapshot", "snapshot": rows}


def test_snapshot_mapping_all_fields():
    log = _log([
        _snap("pack/lucidfence/lf_os_version", "MAC-01",
              [{"name": "macOS", "version": "15.5", "platform": "darwin"}]),
        _snap("lf_disk_encryption", "MAC-01",
              [{"name": "/dev/disk3s1", "encrypted": "1", "type": "APFS Encryption"}]),
        _snap("lf_storage", "MAC-01",
              [{"path": "/", "blocks": "500000000", "blocks_available": "100000000",
                "blocks_size": "1024"}]),
        _snap("lf_battery", "MAC-01", [{"percent_remaining": "87"}]),
        _snap("lf_agent_health", "MAC-01", [{"version": "5.17.0", "uuid": "u1"}]),
    ])
    p = parse_results_log(log, now=NOW)
    check("MAC-01" in p, "host presente")
    d = p["MAC-01"]
    check(d["os_version"] == "macOS 15.5", f"os_version mapeado: {d}")
    check(d["encryption_enabled"] is True, "encrypted=1 => True")
    check(d["storage_total_gb"] == round(500000000 * 1024 / 1024**3, 1), "total GB")
    check(d["storage_free_gb"] == round(100000000 * 1024 / 1024**3, 1), "free GB")
    check(d["battery_level"] == 87.0, "battery")
    check(d["osquery_version"] == "5.17.0", "agent health")
    check(d["posture_source"] == "osquery", "provenance")


def test_differential_and_stale_and_garbage():
    old = NOW - 3600  # 60 min > max_age 30
    log = _log([
        # formato differential (columns/action)
        {"name": "lf_disk_encryption", "hostIdentifier": "w-01", "unixTime": NOW,
         "action": "added", "columns": {"name": "C:", "encrypted": "0"}},
        # señal caducada: debe descartarse
        _snap("lf_battery", "w-01", [{"percent_remaining": "9"}], ts=old),
        # basura: línea no-JSON y query desconocida
        "esto no es json {",
        _snap("query_desconocida", "w-01", [{"x": 1}]),
    ])
    p = parse_results_log(log, max_age_min=30, now=NOW)
    d = p.get("w-01", {})
    check(d.get("encryption_enabled") is False, "differential encrypted=0 => False")
    check("battery_level" not in d, "señal caducada descartada (evidence gate)")


def test_newest_entry_wins():
    log = _log([
        _snap("lf_battery", "h1", [{"percent_remaining": "50"}], ts=NOW - 600),
        _snap("lf_battery", "h1", [{"percent_remaining": "20"}], ts=NOW - 10),
    ])
    p = parse_results_log(log, now=NOW)
    check(p["h1"]["battery_level"] == 20.0, "gana la entrada más reciente")


def test_missing_log_returns_empty():
    check(parse_results_log("/no/existe/osqueryd.results.log") == {}, "sin log => {}")


def test_enrich_matches_host_and_overrides():
    log = _log([
        _snap("lf_os_version", "SERIAL-9", [{"name": "macOS", "version": "15.5"}]),
        _snap("lf_disk_encryption", "SERIAL-9", [{"name": "d", "encrypted": "1"}]),
    ])
    src = OsqueryPosture(results_log=str(log), max_age_min=10**9)
    device = {"device_id": "dev-1", "serial": "serial-9",
              "os_version": "macOS 14.0", "encryption_enabled": False}
    merged = src.enrich(device)
    check(merged["os_version"] == "macOS 15.5", "osquery pisa el dato del adapter")
    check(merged["encryption_enabled"] is True, "cifrado real del endpoint")
    check(merged["posture_source"] == "osquery", "provenance en el device")
    # host sin match: el device queda intacto
    other = src.enrich({"device_id": "otro"})
    check("posture_source" not in other, "sin match => sin cambios")


def test_from_config_gate():
    check(OsqueryPosture.from_config({}) is None, "sin config posture => None")
    check(OsqueryPosture.from_config({"posture": {"source": "nada"}}) is None,
          "source distinto => None")
    src = OsqueryPosture.from_config(
        {"posture": {"source": "osquery", "results_log": "/tmp/x.log"}})
    check(src is not None and src.results_log == "/tmp/x.log", "config válida")


def test_engine_cycle_with_posture_never_raises():
    """El engine con posture mal configurada (log inexistente) sigue vivo."""
    from helpers import make_temp_engine
    eng = make_temp_engine()
    eng.config["posture"] = {"source": "osquery", "results_log": "/no/existe.log"}
    from lucidfence.core.posture_osquery import OsqueryPosture as OP
    eng.posture = OP.from_config(eng.config)
    d = eng.posture.enrich({"device_id": "d1"})
    check(d == {"device_id": "d1"}, "log ausente => device intacto, sin raise")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests OK")
