import os, sys
sys.path.insert(0, ".")
import config_loader
from pathlib import Path
from saas.tenant import TenantStore
from core.engine import Engine
from core.routes import route_for_device

ROOT = Path(".")
ts = TenantStore(ROOT / "data")
org = "org_c40aa88904"
cfg = config_loader.load(ROOT / "config.json")
cfg["mode"] = "simulation"
cfg["dry_run"] = True
cfg["data_dir"] = str(ts.data_dir(org))
cfg["sim_seed_path"] = str(ts.data_dir(org) / "fleet_seed.json")
cfg["routes_path"] = str(ts.data_dir(org) / "routes.json")
cfg["policies_path"] = str(ts.data_dir(org) / "policies.json")
cfg["fences_path"] = str(ts.data_dir(org) / "fences.json")
eng = Engine(cfg)
r = route_for_device(eng.routes, "dev-002")
print("ROUTE id:", r.id if r else None)

# Monkeypatch _dedupe_action to trace
orig = eng._dedupe_action
def traced(ds, action, fence_id, trigger, policy_name, severity, params=None):
    res = orig(ds, action, fence_id, trigger, policy_name, severity, params)
    print(f"  [dedupe] action={action} fence={fence_id} trigger={trigger} returned_fired={res}")
    return res
eng._dedupe_action = traced

off_seen = False
run = 0
for _ in range(90):
    eng.run_once()
    run += 1
    d = [x for x in eng.store.snapshot().values() if x.device_id == "dev-002"]
    if d and d[0].route_state == "off_route":
        off_seen = True
print("off_seen", off_seen, "after runs", run)
evs = [e for e in eng.store.recent_events(100000) if e.get("kind") == "route_exit" and e.get("device_id") == "dev-002"]
acts = [a for a in eng.store.recent_actions(100000) if a.get("trigger") == "route_exit" and a.get("device_id") == "dev-002"]
print("evs", len(evs), "acts", len(acts))
print("sample act", acts[:1])
