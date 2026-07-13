#!/usr/bin/env python3
"""Applivery MCP server (stdio, JSON-RPC, zero extra deps).

Exposes the REAL Applivery UEM API surface (verified live 2026-07-07) as MCP
tools so an agent can /learn the API and operate against a real service
account. Runs 100% locally; never publishes anything.

Tools:
  applivery_learn            -> returns the learned API contract (endpoints,
                                auth, response shapes, gotchas)
  applivery_test_token       -> validate a Bearer token against the API
  applivery_list_devices     -> GET /v1/orgs/{org_id}/devices (paginated)
  applivery_get_device       -> GET /v1/orgs/{org_id}/devices/{device_id}
  applivery_send_command     -> POST /v1/orgs/{org_id}/devices/{device_id}/commands

Auth: Authorization: Bearer <APPLIVERY_API_KEY>
Base: https://api.applivery.io/v1
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("APPLIVERY_API_BASE", "https://api.applivery.io/v1").rstrip("/")
TOKEN = os.environ.get("APPLIVERY_API_KEY", "")
ORG = os.environ.get("APPLIVERY_ORG_ID", "")

API_CONTRACT = {
    "base_url": "https://api.applivery.io/v1",
    "auth": "Authorization: Bearer <APPLIVERY_API_KEY> (service account token)",
    "env": {"APPLIVERY_API_KEY": "service account token",
            "APPLIVERY_ORG_ID": "workspace / organization id",
            "APPLIVERY_API_BASE": "override base url (testing)"},
    "endpoints": {
        "test_token": "GET /v1  (or any org call; 200 => valid)",
        "list_devices": "GET /v1/orgs/{org_id}/devices  (pagination via Link: rel=next header)",
        "get_device": "GET /v1/orgs/{org_id}/devices/{device_id}",
        "send_command": "POST /v1/orgs/{org_id}/devices/{device_id}/commands",
    },
    "device_response_shape": {
        "id": "string", "name": "string", "platform": "android|ios|windows|chromeos",
        "status": "active|inactive", "is_compliant": "bool",
        "last_location": {"latitude": "float", "longitude": "float",
                           "accuracy": "float", "timestamp": "ISO8601"},
        "last_seen_at": "ISO8601",
    },
    "command_body": {"command": "lock|wipe|message|locate|reboot|clear_passcode",
                     "params": {}},
    "gotchas": [
        "Pagination is via HTTP 'Link: <url>; rel=\"next\"' header, NOT a body field.",
        "Device list is wrapped (data.items / data.devices / data.data); inspect envelope.",
        "401/403 => token invalid or org_id wrong; do NOT raise_for_status blindly.",
        "Service-account auth is Bearer, not X-Api-Token (that is a different API).",
    ],
}


def _req(method: str, path: str, token: str = None, body: dict = None) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token or TOKEN}",
               "Accept": "application/json",
               "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            link = r.headers.get("Link", "")
        return {"ok": True, "status": r.status, "json": _safe_json(raw), "link": link}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "json": _safe_json(e.read().decode()),
                "error": e.reason}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": 0, "json": None, "error": f"{type(e).__name__}: {e}"}


def _safe_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return {"_raw": s[:500]}


def _paginate(path: str, token: str):
    items, url, seen = [], path, 0
    while url and seen < 50:
        res = _req("GET", url, token)
        if not res["ok"]:
            return res
        data = res["json"] or {}
        for key in ("items", "devices", "data", "results"):
            if isinstance(data.get(key), list):
                items.extend(data[key]); break
        link = res.get("link", "")
        nxt = _next_link(link)
        if not nxt:
            break
        url = nxt; seen += 1
    return {"ok": True, "status": 200, "items": items}


def _next_link(link_header: str):
    for part in link_header.split(","):
        if 'rel="next"' in part:
            return part[part.find("<") + 1: part.find(">")]
    return None


# ---- MCP protocol -------------------------------------------------------
def tools_list():
    return {
        "tools": [
            {"name": "applivery_learn", "description": "Return the learned Applivery API contract (endpoints, auth, response shapes, gotchas). Use this to /learn the API.", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "applivery_test_token", "description": "Validate an Applivery Bearer token (or the one in APPLIVERY_API_KEY).", "inputSchema": {"type": "object", "properties": {"api_key": {"type": "string"}, "org_id": {"type": "string"}}}},
            {"name": "applivery_list_devices", "description": "List devices for an org (paginated via Link header).", "inputSchema": {"type": "object", "properties": {"org_id": {"type": "string"}, "api_key": {"type": "string"}}}},
            {"name": "applivery_get_device", "description": "Get one device by id.", "inputSchema": {"type": "object", "properties": {"org_id": {"type": "string"}, "device_id": {"type": "string"}, "api_key": {"type": "string"}}}},
            {"name": "applivery_send_command", "description": "Send a MDM command to a device (lock, wipe, message, locate, reboot, clear_passcode).", "inputSchema": {"type": "object", "properties": {"org_id": {"type": "string"}, "device_id": {"type": "string"}, "command": {"type": "string"}, "api_key": {"type": "string"}, "params": {"type": "object"}}}},
        ]
    }


def tool_call(name: str, args: dict) -> dict:
    if name == "applivery_learn":
        return {"content": [{"type": "text", "text": json.dumps(API_CONTRACT, indent=2, ensure_ascii=False)}]}
    tk = args.get("api_key") or TOKEN
    org = args.get("org_id") or ORG
    if name == "applivery_test_token":
        res = _req("GET", "/orgs/" + (org or "self") + "/devices", tk)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]}
    if name == "applivery_list_devices":
        if not org:
            return {"content": [{"type": "text", "text": json.dumps({"ok": False, "error": "org_id requerido"}, ensure_ascii=False)}]}
        res = _paginate("/orgs/" + org + "/devices", tk)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]}
    if name == "applivery_get_device":
        res = _req("GET", f"/orgs/{org}/devices/{args.get('device_id')}", tk)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]}
    if name == "applivery_send_command":
        res = _req("POST", f"/orgs/{org}/devices/{args.get('device_id')}/commands",
                   tk, {"command": args.get("command"), "params": args.get("params", {})})
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]}
    return {"content": [{"type": "text", "text": json.dumps({"error": "unknown tool"})}]}


def _send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "applivery-mcp", "version": "1.0.0"}}})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": mid, "result": tools_list()})
        elif method == "tools/call":
            params = msg.get("params", {})
            res = tool_call(params.get("name", ""), params.get("arguments", {}))
            _send({"jsonrpc": "2.0", "id": mid, "result": res})
        else:
            if mid is not None:
                _send({"jsonrpc": "2.0", "id": mid, "result": {}})


if __name__ == "__main__":
    main()
