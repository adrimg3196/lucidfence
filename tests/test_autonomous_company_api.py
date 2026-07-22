from __future__ import annotations

import http.client
import json
import re
import time


def _request(method: str, path: str, body=None, cookie: str = ""):
    conn = http.client.HTTPConnection("127.0.0.1", 8765, timeout=15)
    headers = {"Content-Type": "application/json"}
    if cookie: headers["Cookie"] = cookie
    conn.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=headers)
    response = conn.getresponse(); raw = response.read(); response_headers = response.getheaders(); conn.close()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"raw": raw.decode("utf-8", errors="replace")}
    return response.status, payload, response_headers


def _demo_cookie() -> str:
    status, _, headers = _request("POST", "/api/auth/demo", {})
    assert status == 200
    cookies = []
    for key, value in headers:
        if key.lower() == "set-cookie": cookies.append(value.split(";", 1)[0])
    return "; ".join(cookies)


def _cookies(headers) -> str:
    return "; ".join(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie")


def test_company_api_goal_cycle_pause_and_owner_gates():
    status, _, _ = _request("GET", "/api/company")
    assert status == 401
    cookie = _demo_cookie()
    status, initial, _ = _request("GET", "/api/company", cookie=cookie)
    assert status == 200 and initial["schema"] == "lucidfence-autonomous-company/v1"
    status, goal, _ = _request("POST", "/api/company/goals", {
        "title": "Reducir riesgo de salidas", "outcome": "Menos dispositivos outside",
        "metrics": [{"name": "outside", "target": 0}], "priority": "p0", "autonomy": "simulate"
    }, cookie)
    assert status == 201 and goal["id"].startswith("goal_")
    status, cycle, _ = _request("POST", "/api/company/cycle", {}, cookie)
    assert status == 200 and cycle["cycle"] == 1 and cycle["created_tasks"]
    assert all(task["evidence"] for task in cycle["created_tasks"])
    medium = next(task for task in cycle["created_tasks"] if task["risk"] == "medium")
    status, handoff, _ = _request("POST", f"/api/company/tasks/{medium['id']}/approve", {"reason": "CVE y rollback comprobados"}, cookie)
    assert status == 200 and handoff["status"] == "ready_for_handoff"
    assert handoff["result"]["side_effects"] is False
    status, duplicate, _ = _request("POST", f"/api/company/tasks/{medium['id']}/approve", {"reason": "duplicado"}, cookie)
    assert status == 409 and "already approved" in duplicate["error"]
    suffix = time.time_ns()
    status, _, headers = _request("POST", "/api/auth/signup", {
        "email": f"company-{suffix}@tenant.test", "password": "tenant-pass-123",
        "name": "Second Owner", "org_name": f"Isolated {suffix}",
    })
    assert status == 200
    other_cookie = _cookies(headers)
    status, isolated, _ = _request("GET", "/api/v2/company", cookie=other_cookie)
    assert status == 200 and isolated["goals"] == [] and isolated["tasks"] == []
    status, _, _ = _request("POST", f"/api/company/tasks/{medium['id']}/approve", {"reason": "cross tenant"}, other_cookie)
    assert status == 404
    status, paused, _ = _request("POST", "/api/company/pause", {"reason": "QA"}, cookie)
    assert status == 200 and paused["paused"] is True
    status, blocked, _ = _request("POST", "/api/company/cycle", {}, cookie)
    assert status == 409 and "paused" in blocked["error"]
    status, resumed, _ = _request("POST", "/api/company/resume", {}, cookie)
    assert status == 200 and resumed["paused"] is False
