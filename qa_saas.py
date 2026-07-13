#!/usr/bin/env python3
"""End-to-end API QA for the LucidFence SaaS using raw http.client
(direct socket, bypasses any environment HTTP proxy that eats POSTs)."""
import json, http.client, time

HOST, PORT = "127.0.0.1", 8765
SUFFIX = str(time.time_ns())
OWNER_EMAIL = f"admin-{SUFFIX}@acme.test"
VIEWER_EMAIL = f"viewer-{SUFFIX}@acme.test"
ORG_NAME = f"Acme Logistics QA {SUFFIX}"
cookies = {}
failures = 0


def call(method, path, body=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    data = json.dumps(body).encode() if body is not None else None
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode()
    sc = resp.getheaders()
    for k, v in sc:
        if k.lower() == "set-cookie":
            name = v.split("=")[0]
            val = v.split(";")[0].split("=", 1)[1] if "=" in v else ""
            cookies[name] = val
    conn.close()
    try:
        js = json.loads(raw) if raw else {}
    except Exception:
        js = {"_raw": raw[:80]}
    return resp.status, js


def check(label, cond, extra=""):
    global failures
    if not cond:
        failures += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" :: {extra}" if extra else ""))
    return cond


print("=== LucidFence SaaS — QA (http.client direct) ===")
s = call("POST", "/api/auth/signup", {"email":OWNER_EMAIL,"password":"SuperSecret1","name":"Ana","org_name":ORG_NAME,"plan":"pro"})
print("signup:", s[0], s[1].get("error") if isinstance(s[1], dict) else s[1])
l = call("POST", "/api/auth/login", {"email":OWNER_EMAIL,"password":"SuperSecret1"})
ok = isinstance(l[1], dict) and l[1].get("ok")
check("login ok+token", ok, f"http={l[0]}")
check("session cookie", "gf_session" in cookies)
check("org cookie", "gf_org" in cookies)

o = call("GET", "/api/org")
pl = o[1].get("plan", {}).get("label") if isinstance(o[1], dict) else None
check("org = Pro plan", pl == "Pro", str(pl))

st = call("GET", "/api/status")
devs = st[1].get("device_count", 0) if isinstance(st[1], dict) else 0
check("status devices>0", devs > 0, f"devices={devs}, in={st[1].get('inside_count')}, out={st[1].get('outside_count')}, fences={len(st[1].get('fences', []))}" if isinstance(st[1], dict) else str(st[1])[:40])

ro = call("POST", "/api/run-once")
check("run-once ok", ro[1].get("ok") is True if isinstance(ro[1], dict) else False)

rk = call("GET", "/api/risk")
check("risk endpoint", isinstance(rk[1], dict) and "risk" in rk[1], f"risk={len(rk[1].get('risk', [])) if isinstance(rk[1], dict) else '?'}, noncompliant={rk[1].get('summary', {}).get('noncompliant') if isinstance(rk[1], dict) else '?'}")

po = call("GET", "/api/policies")
check("policies endpoint", isinstance(po[1], dict) and len(po[1].get("policies", [])) > 0, f"count={len(po[1].get('policies', [])) if isinstance(po[1], dict) else '?'}")

co = call("GET", "/api/compliance")
check("compliance endpoint", isinstance(co[1], dict) and "compliance_percent" in co[1], str(co[1].get("compliance_percent")) if isinstance(co[1], dict) else str(co[1])[:40])

an = call("GET", "/api/analytics")
check("analytics endpoint", isinstance(an[1], dict) and bool(an[1].get("analytics")))

rp = call("GET", "/api/report")
check("report endpoint", isinstance(rp[1], dict) and bool(rp[1].get("report")))

up = call("POST", "/api/plan/upgrade", {"plan": "enterprise"})
check("plan upgrade enterprise", up[1].get("plan") == "enterprise" if isinstance(up[1], dict) else False, f"max_dev={up[1].get('limits', {}).get('max_devices') if isinstance(up[1], dict) else '?'}")

us = call("GET", "/api/users")
check("users list", isinstance(us[1], dict) and len(us[1].get("users", [])) >= 1, f"users={len(us[1].get('users', [])) if isinstance(us[1], dict) else '?'}")

inv = call("POST", "/api/users", {"email": VIEWER_EMAIL, "name": "Vic", "password": "Viewer1234", "role": "viewer"})
check("invite viewer", inv[1].get("ok") is True if isinstance(inv[1], dict) else False)

# RBAC: viewer login in separate cookie jar
vc = {}
conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
conn.request("POST", "/api/auth/login", body=json.dumps({"email": VIEWER_EMAIL, "password": "Viewer1234"}).encode(), headers={"Content-Type": "application/json"})
r = conn.getresponse(); 
for k, v in r.getheaders():
    if k.lower() == "set-cookie":
        vc[v.split("=")[0]] = v.split(";")[0].split("=", 1)[1]
conn.close()
conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
conn.request("POST", "/api/plan/upgrade", body=json.dumps({"plan": "free"}).encode(),
             headers={"Content-Type": "application/json", "Cookie": "; ".join(f"{k}={v}" for k, v in vc.items())})
r2 = conn.getresponse(); code = r2.status; conn.close()
check("RBAC viewer blocked from billing (403)", code == 403, f"http={code}")

# unauth
conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
conn.request("GET", "/api/status")
rc = conn.getresponse().status; conn.close()
check("unauth /api/status -> 401", rc == 401, f"http={rc}")

# static dashboard served
conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
conn.request("GET", "/")
hc = conn.getresponse(); body = hc.read().decode(); conn.close()
check("dashboard HTML served", hc.status == 200 and "LucidFence" in body, f"http={hc.status}")

print(f"=== QA complete: {failures} failure(s) ===")
raise SystemExit(1 if failures else 0)
