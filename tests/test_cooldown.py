"""TDD: persisted cooldown for destructive actions (wipe/lock/clear_passcode/reboot).

A standing violation (e.g. outside + rooted) must not re-issue a destructive
command every cycle or after a server restart. The engine records the last
execution time per (device, action) and suppresses re-fires within a cooldown
window. Non-destructive actions (notify/message/locate) are never cooled.
"""
import os
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config_loader  # noqa: E402
from saas.tenant import TenantStore  # noqa: E402
from core.engine import Engine  # noqa: E402
from core.policies import Policy  # noqa: E402
from core.location_source import LocationReport  # noqa: E402
from helpers import make_temp_engine  # noqa: E402

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _engine(cooldown=3600):
    eng = make_temp_engine(cooldown_seconds=cooldown)
    # Deterministic: wipe any persisted cooldown state left by prior runs.
    cd = Path(eng.data_dir) / "action_cooldowns.json"
    if cd.exists():
        cd.unlink()
    return eng


class _InsideSource:
    """One device permanently 'outside + rooted' so a destructive policy fires."""
    def fetch(self):
        return [LocationReport(device_id="dev-destruct", name="At Risk",
                                platform="android", status="active",
                                compliant=False, lat=40.0, lng=-3.0)]


def _destructive_policy():
    return [Policy(id="pw", name="Wipe on breach", description="wipe on breach",
                   when=[{"field": "risk_score", "op": "gte", "value": 0}],
                   actions=[{"action": "wipe", "params": {}}])]


def test_destructive_action_fires_once_per_cycle():
    eng = _engine()
    eng.source = _InsideSource()
    eng.routes = []
    eng.policies = _destructive_policy()
    eng.run_once()
    wipes = [a for a in eng._cycle_actions
             if a.get("device_id") == "dev-destruct" and a.get("action") == "wipe"]
    assert len(wipes) == 1, wipes


def test_destructive_action_suppressed_by_cooldown_within_window():
    eng = _engine(cooldown=3600)
    tdir = eng.data_dir
    cd = Path(tdir) / "action_cooldowns.json"
    if cd.exists():
        cd.unlink()
    eng.source = _InsideSource()
    eng.routes = []
    eng.policies = _destructive_policy()
    eng.run_once()  # fires once, records timestamp
    fired1 = [a for a in eng._cycle_actions if a.get("action") == "wipe"]
    assert len(fired1) == 1, fired1
    # cooldown is 3600s; a second immediate cycle must be suppressed
    eng.run_once()
    fired2 = [a for a in eng._cycle_actions if a.get("action") == "wipe"]
    assert len(fired2) == 0, fired2
    # the suppression is persisted: a fresh Engine (simulating restart) sees it.
    # NOTE: build eng2 WITHOUT wiping the cooldown file (created by eng).
    cfg = {
        "mode": "simulation",
        "autostart": False,
        "data_dir": str(tdir),
        "org_id": eng.org_id,
        "fences_path": eng.fences_path,
        "routes_path": str(eng.routes_path),
        "policies_path": str(eng.policies_path),
        "action_cooldown_seconds": 3600,
    }
    eng2 = Engine(cfg)
    eng2.source = _InsideSource()
    eng2.routes = []
    eng2.policies = _destructive_policy()
    eng2.run_once()
    fired3 = [a for a in eng2._cycle_actions if a.get("action") == "wipe"]
    assert len(fired3) == 0, "cooldown not persisted across restart"


def test_cooldown_expires_and_allows_refire():
    eng = _engine(cooldown=3600)
    eng.source = _InsideSource()
    eng.routes = []
    eng.policies = _destructive_policy()
    # freeze clock so the first fire is at T=1_000_000
    real_time = _time.time
    _time.time = lambda: 1_000_000.0
    try:
        eng.run_once()
        assert len([a for a in eng._cycle_actions if a.get("action") == "wipe"]) == 1
        # same clock -> still within window -> suppressed
        eng.run_once()
        assert len([a for a in eng._cycle_actions if a.get("action") == "wipe"]) == 0
        # advance clock beyond cooldown -> allowed to refire
        _time.time = lambda: 1_000_000.0 + 3601.0
        eng.run_once()
        assert len([a for a in eng._cycle_actions if a.get("action") == "wipe"]) == 1, \
            "cooldown should expire and allow refire"
    finally:
        _time.time = real_time


def test_non_destructive_action_never_cooled():
    eng = _engine(cooldown=3600)
    eng.source = _InsideSource()
    eng.routes = []
    eng.policies = [Policy(id="pn", name="Notify", description="notify",
                           when=[{"field": "risk_score", "op": "gte", "value": 0}],
                           actions=[{"action": "notify", "params": {"msg": "x"}}])]
    eng.run_once()
    eng.run_once()
    # Other automation layers (e.g. SOAR) may also emit notify in the same
    # cycle. Assert specifically on this policy's action, not on every notify.
    fired = [a for a in eng._cycle_actions
             if a.get("action") == "notify" and a.get("trigger") == "policy:pn"]
    assert len(fired) == 1, "policy notify should fire once in every cycle"
    # but the cooldown store must NOT have recorded notify
    assert eng.store.last_action_at("dev-destruct", "notify") == 0.0, \
        "non-destructive actions must not be cooled"
