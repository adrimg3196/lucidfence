#!/usr/bin/env python3
import yaml
p = ".github/workflows/cron-watchdog.yml"
with open(p) as f:
    d = yaml.safe_load(f)
print("OK top keys:", list(d.keys()))
on_key = True if True in d else "on"  # YAML parses 'on' as boolean True
print("on.schedule:", d[on_key]["schedule"])
print("permissions:", d["jobs"]["watchdog"].get("permissions"))
print("step names:", [s.get("name") for s in d["jobs"]["watchdog"]["steps"]])
print("env:", d.get("env"))
# sanity: ensure the corrected jq filter string is present
src = open(p).read()
assert "select((.value|not))" in src, "corrected jq filter missing!"
assert "select(is_fail) ] | length" not in src, "OLD filter still present!"
print("jq filter: corrected version confirmed present, old version absent")
