#!/usr/bin/env python3
"""CLI for the Geofence UEM product.

Usage:
  python3 cli.py serve        # run the engine loop + local dashboard (default)
  python3 cli.py run-once     # run a single evaluation cycle and print stats
  python3 cli.py watch        # run cycles in foreground at the configured interval
  python3 cli.py seed         # (re)create the demo fleet seed
  python3 cli.py status       # print a compact status snapshot
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import config_loader
from core.engine import Engine


def _engine() -> Engine:
    cfg = config_loader.load(Path("config.json"))
    return Engine(cfg)


def cmd_serve():
    import saas_server  # noqa: F401  (multi-tenant SaaS: engine + auth + http server)
    saas_server.main()


def cmd_run_once():
    eng = _engine()
    stats = eng.run_once()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_watch():
    eng = _engine()
    interval = eng.interval
    print(f"Watching (interval={interval}s). Ctrl+C to stop.")
    try:
        while True:
            stats = eng.run_once()
            print(f"[{stats['ts']}] cycle={stats['cycle']} inside={stats['inside']} "
                  f"outside={stats['outside']} unknown={stats['unknown']} "
                  f"events={stats['events_this_cycle']} actions={stats['actions_this_cycle']}")
            time.sleep(interval)
    except KeyboardInterrupt:
        sys.exit(0)


def cmd_seed():
    from core.location_source import SimulationLocationSource
    cfg = config_loader.load(__import__("pathlib").Path("config.json"))
    sim = SimulationLocationSource(seed_path=cfg.get("sim_seed_path", "data/fleet_seed.json"))
    print("Demo fleet seed ready:", sim.seed_path)


def cmd_status() -> None:
    eng = _engine()
    eng.run_once()
    st = eng.status()
    print(json.dumps(st, ensure_ascii=False, indent=2))


def cmd_validate() -> None:
    from core.fences import load_fences, validate_fences
    cfg = config_loader.load(Path("config.json"))
    fences = load_fences(cfg.get("fences_path", "fences.json"))
    problems = validate_fences(fences)
    if problems:
        print("FENCE CONFIG INVALID:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"FENCE CONFIG OK: {len(fences)} fence(s) validated, 0 problems.")


def cmd_report() -> None:
    import subprocess
    out = Path("reports")
    cmd = [sys.executable, "reports.py", "--out", str(out)]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=False)


def main():
    cmds = {
        "serve": cmd_serve,
        "run-once": cmd_run_once,
        "watch": cmd_watch,
        "seed": cmd_seed,
        "status": cmd_status,
        "validate": cmd_validate,
        "report": cmd_report,
    }
    name = sys.argv[1] if len(sys.argv) > 1 else "serve"
    fn = cmds.get(name)
    if not fn:
        print("Unknown command:", name)
        print("Available:", ", ".join(cmds))
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()
