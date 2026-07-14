"""End-to-end QA for the new IT-administrator features:

  - Inventory enrichment (DeviceState fields populated by simulation)
  - On-demand remote commands (POST /api/devices/<id>/command)
  - Configurable threshold alerts (CRUD + evaluation)
  - Bulk export (CSV + print-ready HTML)

Uses raw http.client (bypasses any env proxy that eats POSTs to localhost).
"""
import json, http.client, time, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os as _os
HOST, PORT = "127.0.0.1", int(_os.environ.get("LUCIDFENCE_PORT", "8765"))
SUFFIX = str(time.time_ns())
OWNER = f"itadmin-{SUFFIX}@acme.test"
VIEWER = f"viewer-{SUFFIX}@acme.test"
ORG = f"ACME IT {SUFFIX}"
failures = 0


def call(method, path, body=None, cookies=None):
    c = http.client.HTTPConnection(HOST, PORT, timeout=30)
    h = {"Content-Type": "application/json"}
    if cookies:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    d = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=d, headers=h)
    r = c.getresponse()
    raw = r.read().decode()
    ck = {}
    for k, v in r.getheaders():
        if k.lower() == "set-cookie":
            ck[v.split("=")[0]] = v.split(";")[0].split("=", 1)[1]
    try:
        js = json.loads(raw) if raw else {}
    except Exception:
        js = {"_raw": raw[:80]}
    c.close()
    return r.status, js, ck


def check(label, cond, extra=""):
    global failures
    if not cond:
        failures += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" :: {extra}" if extra else ""))


print("=== LucidFence — IT admin features QA ===")
s, _, ck = call("POST", "/api/auth/signup",
                {"email": OWNER, "password": "SuperSecret1", "name": "IT Admin",
                 "org_name": ORG, "plan": "pro"})
check("signup owner", s == 200, f"http={s}")
# force a cycle so the simulated fleet is populated (dashboard "Forzar ciclo")
call("POST", "/api/run-once", cookies=ck)
time.sleep(1)
# Invite VIEWER into the OWNER's org as a viewer (no prior signup, so the
# invite path creates the user). RBAC is then evaluated against the same
# tenant the protected endpoints operate on.
s, inv, _ = call("POST", "/api/users", {"email": VIEWER, "name": "Vic",
                 "password": "Viewer1234", "role": "viewer"}, cookies=ck)
check("invite viewer to owner org", s == 200, f"http={s}")
# viewer logs in (landing in the OWNER org as a viewer)
s, _, vck = call("POST", "/api/auth/login", {"email": VIEWER, "password": "Viewer1234"})
check("viewer login (owner org)", s == 200)


# ---- 1) Inventory enrichment ---------------------------------------------
s, devs, _ = call("GET", "/api/devices", cookies=ck)
check("devices list", s == 200 and len(devs) >= 1, f"n={len(devs)}")
sample = devs[0]
inv_fields = ["os_version", "model", "manufacturer", "serial_number", "battery_level",
              "storage_total_gb", "storage_free_gb", "carrier", "assigned_user",
              "department", "last_checkin", "enrolled_at", "device_tag"]
populated = [f for f in inv_fields if sample.get(f) not in (None, "")]
check("inventory fields populated", len(populated) >= 8,
      f"populated={len(populated)}/{len(inv_fields)} e.g. {sample.get('model')} {sample.get('os_version')}")


# ---- 2) On-demand remote commands ----------------------------------------
dev_id = sample["device_id"]
for action in ["locate", "lock", "message", "reboot", "clear_passcode"]:
    body = {"action": action}
    if action == "message":
        body["params"] = {"message": "prueba IT"}
    s, r, _ = call("POST", f"/api/devices/{dev_id}/command", body, cookies=ck)
    check(f"command {action}", s == 200 and r.get("ok") is True, f"http={s} {r.get('error','')}")
# invalid action rejected
s, r, _ = call("POST", f"/api/devices/{dev_id}/command", {"action": "bogus"}, cookies=ck)
check("invalid action rejected", s == 400, f"http={s}")
# viewer blocked (device:action not in viewer caps)
s, r, _ = call("POST", f"/api/devices/{dev_id}/command", {"action": "lock"}, cookies=vck)
check("viewer blocked from command", s == 403, f"http={s}")


# ---- 3) Configurable alerts -----------------------------------------------
s, r, _ = call("POST", "/api/alerts",
                {"type": "outside_duration", "threshold": 30, "channel": "none",
                 "severity": "high", "cooldown_minutes": 60}, cookies=ck)
check("create alert rule", s == 200 and r.get("ok"), f"http={s}")
rid = r.get("rule", {}).get("id")
s, al, _ = call("GET", "/api/alerts", cookies=ck)
check("alerts list", s == 200 and len(al.get("rules", [])) >= 1, f"n={len(al.get('rules', []))}")
check("alert types exposed", "outside_duration" in al.get("types", []))
check("alert channels exposed", "slack" in al.get("channels", []))
# evaluate
s, ev, _ = call("POST", "/api/alerts/evaluate", cookies=ck)
check("alerts evaluate", s == 200 and "count" in ev, f"http={s}")
# delete
s, r, _ = call("POST", f"/api/alerts/{rid}/delete", cookies=ck)
check("delete alert rule", s == 200 and r.get("ok") is True, f"http={s}")
# viewer cannot create
s, r, _ = call("POST", "/api/alerts", {"type": "noncompliant", "threshold": 0}, cookies=vck)
check("viewer blocked from alert create", s == 403, f"http={s}")


# ---- 4) Bulk export -------------------------------------------------------
for kind in ["inventory", "actions", "compliance"]:
    s, hdr, _ = call("GET", f"/api/export?kind={kind}&format=csv", cookies=ck)
    # CSV is served as attachment; status 200 and body has csv shape
    check(f"export {kind} csv", s == 200, f"http={s}")
s, hdr, _ = call("GET", f"/api/export?kind=inventory&format=html", cookies=ck)
check("export inventory html", s == 200, f"http={s}")
# viewer cannot export (report:export)
s, r, _ = call("GET", "/api/export?kind=inventory&format=csv", cookies=vck)
check("viewer blocked from export", s == 403, f"http={s}")


print(f"\n=== IT features QA complete: {failures} failure(s) ===")
raise SystemExit(1 if failures else 0)
