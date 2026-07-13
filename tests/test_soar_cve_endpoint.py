"""Regression: /api/soar returns the playbook library + live matches, and
/api/cve returns a populated CVE summary for the demo fleet.

Run: python3 tests/run_tests.py
Assumes `python3 saas_server.py` is running on 127.0.0.1:8765.
"""
import http.client
import json
import time

H, P = "127.0.0.1", 8765


def req(method, path, cookie=None):
    c = http.client.HTTPConnection(H, P, timeout=10)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    c.request(method, path, headers=headers)
    r = c.getresponse()
    raw = r.read().decode("utf-8", "replace")
    try:
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {"raw": raw}
    return r.status, body, r.getheader("Set-Cookie")


def demo_cookie():
    _, _, ck = req("POST", "/api/auth/demo")
    if not ck:
        raise RuntimeError("no Set-Cookie from /api/auth/demo")
    for part in ck.split(","):
        part = part.strip()
        if part.startswith("gf_session="):
            token = part.split(";", 1)[0].split("=", 1)[1]
            return f"gf_session={token}"
    if "gf_session=" in ck:
        token = ck.split("gf_session=", 1)[1].split(";", 1)[0]
        return f"gf_session={token}"
    raise RuntimeError(f"gf_session not found in Set-Cookie: {ck!r}")


def test_soar_and_cve_endpoints():
    # ensure a cycle has populated enriched apps + SOAR state
    ck = demo_cookie()
    req("POST", "/api/run-once", cookie=ck)

    st, cve, _ = req("GET", "/api/cve", cookie=ck)
    assert st == 200, f"/api/cve -> {st}"
    assert cve.get("cve_summary", {}).get("apps_total", 0) > 0, "cve_summary must list scanned apps"
    assert cve.get("cve_summary", {}).get("vulnerable_apps", 0) > 0, "fleet has vulnerable apps"

    st, soar, _ = req("GET", "/api/soar", cookie=ck)
    assert st == 200, f"/api/soar -> {st}"
    pbs = soar.get("playbooks") or []
    ids = {p["id"] for p in pbs}
    for expected in ("soar-cve-critical", "soar-cve-outside", "soar-rooted-outside"):
        assert expected in ids, f"missing playbook {expected}"
    # At least one playbook must match the seeded vulnerable fleet.
    assert len(soar.get("matched") or []) >= 1, "expected >=1 SOAR match on demo fleet"
    print(f"  CVE: {cve['cve_summary']}")
    print(f"  SOAR playbooks={[p['id'] for p in pbs]} matched={len(soar.get('matched', []))}")


if __name__ == "__main__":
    test_soar_and_cve_endpoints()
    print("\nSOAR/CVE endpoint tests passed")
