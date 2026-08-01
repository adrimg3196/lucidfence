#!/usr/bin/env python3
"""Official LucidFence MCP server (stdio JSON-RPC, zero third-party dependencies).

Exposes the public REST API endpoints as MCP tools for AI agents to list,
create, and delete geofences, list devices, get device states, and list incidents and events.
"""
from __future__ import annotations

import http.client
import json
import os
import sys
from typing import Any, Dict, Optional
from urllib.parse import urlparse

BASE_URL = os.environ.get("LUCIDFENCE_URL", "http://127.0.0.1:8765").rstrip("/")


def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
             cookie: str = "", api_key: str = "", base_url: str = "") -> Dict[str, Any]:
    url = base_url or os.environ.get("LUCIDFENCE_URL", "http://127.0.0.1:8765").rstrip("/")
    parsed = urlparse(url)
    conn = http.client.HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 8765, timeout=30)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # Apply cookie authentication if supplied or in environment
    eff_cookie = cookie or os.environ.get("LUCIDFENCE_MCP_COOKIE", "")
    if eff_cookie:
        headers["Cookie"] = f"gf_session={eff_cookie}" if "gf_session=" not in eff_cookie else eff_cookie

    # Apply Bearer API Key auth if supplied or in environment
    eff_api_key = api_key or os.environ.get("LUCIDFENCE_API_KEY", "")
    if eff_api_key:
        headers["Authorization"] = f"Bearer {eff_api_key}" if not eff_api_key.startswith("Bearer ") else eff_api_key

    try:
        conn.request(method, (parsed.path or "") + path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read(2_000_000).decode("utf-8", "replace")
        cookies = [value.split(";", 1)[0] for key, value in response.getheaders() if key.lower() == "set-cookie"]
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {"raw": raw[:1000]}
        return {"ok": 200 <= response.status < 300, "status": response.status,
                "data": data, "cookie": "; ".join(cookies)}
    except Exception as exc:
        return {"ok": False, "status": 0, "data": {"error": "LucidFence local no disponible", "category": type(exc).__name__}}
    finally:
        conn.close()


def _execute_api(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
                 cookie: str = "", api_key: str = "", base_url: str = "") -> Dict[str, Any]:
    eff_api_key = api_key or os.environ.get("LUCIDFENCE_API_KEY", "")
    eff_cookie = cookie or os.environ.get("LUCIDFENCE_MCP_COOKIE", "")

    if not eff_api_key and not eff_cookie:
        # Fallback to demo login if no authentication is supplied
        demo_res = _request("POST", "/api/auth/demo", {}, base_url=base_url)
        if demo_res.get("ok"):
            eff_cookie = demo_res.get("cookie", "")

    return _request(method, path, payload, cookie=eff_cookie, api_key=eff_api_key, base_url=base_url)


def tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "list_fences",
                "description": "List all geofences configured in the active organization.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "additionalProperties": False
                }
            },
            {
                "name": "get_fence",
                "description": "Retrieve details of a specific geofence by ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The unique ID of the geofence"},
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "required": ["id"],
                    "additionalProperties": False
                }
            },
            {
                "name": "create_fence",
                "description": "Create a new geofence (requires appropriate role/permissions).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name of the geofence"},
                        "type": {"type": "string", "description": "Type of geofence, e.g. 'circle' or 'polygon'", "default": "circle"},
                        "lat": {"type": "number", "description": "Latitude (required for circle type unless address is provided)"},
                        "lng": {"type": "number", "description": "Longitude (required for circle type unless address is provided)"},
                        "radius_m": {"type": "number", "description": "Radius in meters (for circle type)"},
                        "address": {"type": "string", "description": "Optional physical address to be geocoded automatically"},
                        "coordinates": {
                            "type": "array",
                            "description": "Optional list of point objects with lat and lng (for polygon type)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "lng": {"type": "number"}
                                },
                                "required": ["lat", "lng"]
                            }
                        },
                        "actions": {
                            "type": "array",
                            "description": "Optional list of transition action specs",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "description": "UEM action, e.g., 'message', 'lock', 'wipe'"},
                                    "when": {"type": "string", "description": "When to fire: 'on_enter', 'on_exit', etc.", "default": "on_enter"},
                                    "enabled": {"type": "boolean", "default": True},
                                    "params": {"type": "object", "description": "Optional action parameter payload"}
                                },
                                "required": ["action"]
                            }
                        },
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "required": ["name"],
                    "additionalProperties": False
                }
            },
            {
                "name": "delete_fence",
                "description": "Delete an existing geofence by ID (requires appropriate role/permissions).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The unique ID of the geofence to delete"},
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "required": ["id"],
                    "additionalProperties": False
                }
            },
            {
                "name": "list_devices",
                "description": "List devices visible to the active tenant. Can be filtered by fence state.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string", "description": "Optional fence state to filter by: 'inside', 'outside', or 'unknown'"},
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "additionalProperties": False
                }
            },
            {
                "name": "get_device_state",
                "description": "Get detailed UEM state, trails, and recent events/actions for a specific device.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The unique ID of the device"},
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "required": ["id"],
                    "additionalProperties": False
                }
            },
            {
                "name": "list_incidents",
                "description": "List active and recent geofence risk incidents.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "additionalProperties": False
                }
            },
            {
                "name": "list_events",
                "description": "List recent system events from the engine status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "api_key": {"type": "string", "description": "Optional LucidFence API Key (starts with lf_)"},
                        "session_cookie": {"type": "string", "description": "Optional session cookie (gf_session=...)"},
                        "url": {"type": "string", "description": "Optional custom LucidFence URL (e.g. http://127.0.0.1:8765)"}
                    },
                    "additionalProperties": False
                }
            }
        ]
    }


def _tool_result(value: Any, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}],
            "isError": is_error}


def tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    url = str(args.get("url") or "").strip()
    api_key = str(args.get("api_key") or "").strip()
    session_cookie = str(args.get("session_cookie") or "").strip()

    if name == "list_fences":
        res = _execute_api("GET", "/api/fences", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", {}))

    elif name == "get_fence":
        fence_id = args.get("id")
        res = _execute_api("GET", "/api/fences", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        fences = res.get("data", {}).get("fences", [])
        for f in fences:
            if f.get("id") == fence_id:
                return _tool_result(f)
        return _tool_result({"error": f"Geovalla {fence_id} no encontrada"}, is_error=True)

    elif name == "create_fence":
        payload = {
            "name": args.get("name"),
            "type": args.get("type") or "circle",
        }
        if "lat" in args:
            payload["lat"] = args["lat"]
        if "lng" in args:
            payload["lng"] = args["lng"]
        if "radius_m" in args:
            payload["radius_m"] = args["radius_m"]
        if "address" in args:
            payload["address"] = args["address"]
        if "coordinates" in args:
            payload["coordinates"] = args["coordinates"]
        if "actions" in args:
            payload["actions"] = args["actions"]

        res = _execute_api("POST", "/api/fences", payload=payload, api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", {}))

    elif name == "delete_fence":
        fence_id = args.get("id")
        res = _execute_api("DELETE", f"/api/fences/{fence_id}", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", {}))

    elif name == "list_devices":
        state = args.get("state")
        path = "/api/devices"
        if state:
            path += f"?state={state}"
        res = _execute_api("GET", path, api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", []))

    elif name == "get_device_state":
        device_id = args.get("id")
        res = _execute_api("GET", f"/api/devices/{device_id}", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", {}))

    elif name == "list_incidents":
        res = _execute_api("GET", "/api/incidents", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        return _tool_result(res.get("data", {}))

    elif name == "list_events":
        res = _execute_api("GET", "/api/status", api_key=api_key, cookie=session_cookie, base_url=url)
        if not res.get("ok"):
            return _tool_result({"error": res.get("data", {}).get("error", "Error desconocido"), "status": res.get("status")}, is_error=True)
        events = res.get("data", {}).get("recent_events", [])
        return _tool_result(events)

    return _tool_result({"error": "unknown tool", "name": name}, is_error=True)


def _send(message: Dict[str, Any], stdout: Any) -> None:
    stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    stdout.flush()


def run_stdio_server(stdin: Any = None, stdout: Any = None) -> None:
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except (ValueError, TypeError):
            continue
        method, request_id = message.get("method"), message.get("id")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "lucidfence-official-mcp", "version": "1.0.0"}
            }
        elif method == "tools/list":
            result = tools_list()
        elif method == "tools/call":
            params = message.get("params") or {}
            result = tool_call(str(params.get("name") or ""), params.get("arguments") or {})
        else:
            if request_id is None:
                continue
            result = {}
        _send({"jsonrpc": "2.0", "id": request_id, "result": result}, stdout)


def main() -> None:
    run_stdio_server()


if __name__ == "__main__":
    main()
