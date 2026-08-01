#!/usr/bin/env python3
"""LucidFence local MCP server (stdio JSON-RPC, zero third-party deps).

The server connects only to the operator's local LucidFence HTTP instance. It
never accepts UEM/provider secrets as tool arguments and exposes read-only fleet
tools in v1.1.
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
             cookie: str = "") -> Dict[str, Any]:
    parsed = urlparse(BASE_URL)
    conn = http.client.HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 80, timeout=30)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
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


def _session() -> str:
    explicit = os.environ.get("LUCIDFENCE_MCP_COOKIE", "")
    if explicit:
        return explicit
    result = _request("POST", "/api/auth/demo", {})
    return result.get("cookie", "") if result.get("ok") else ""


def _api(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cookie = _session()
    if not cookie:
        return {"ok": False, "error": "No se pudo abrir una sesión local. Verifica que LucidFence esté activo en loopback."}
    result = _request(method, path, payload, cookie)
    if result.get("ok"):
        return result.get("data") or {}
    data = result.get("data") or {}
    return {"ok": False, "status": result.get("status"), "error": data.get("error", "request failed")}


CONTRACT = {
    "name": "lucidfence-mcp", "version": "1.1.0", "transport": "stdio",
    "setup": {"command": "lucidfence mcp", "url_env": "LUCIDFENCE_URL (default http://127.0.0.1:8765)"},
    "security": ["read-only fleet tools", "no UEM/API secrets accepted", "AI uses provider configured in LucidFence"],
    "tools": ["lucidfence_status", "lucidfence_list_devices", "lucidfence_list_incidents",
              "lucidfence_get_risk", "lucidfence_ask_ai", "lucidfence_learn"],
}


def tools_list() -> Dict[str, Any]:
    empty = {"type": "object", "properties": {}}
    return {"tools": [
        {"name": "lucidfence_learn", "description": "Return LucidFence local API/MCP setup and security contract.", "inputSchema": empty},
        {"name": "lucidfence_status", "description": "Get local fleet, geofence and compliance status.", "inputSchema": empty},
        {"name": "lucidfence_list_devices", "description": "List devices visible to the local LucidFence tenant.", "inputSchema": empty},
        {"name": "lucidfence_list_incidents", "description": "List geofence/risk incidents.", "inputSchema": empty},
        {"name": "lucidfence_get_risk", "description": "Get explainable risk scores and evidence.", "inputSchema": empty},
        {"name": "lucidfence_ask_ai", "description": "Ask the optional configured AI provider using a fleet question.",
         "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
    ]}


def _tool_result(value: Any, is_error: bool = False) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}],
            "isError": is_error}


def tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "lucidfence_learn":
        return _tool_result(CONTRACT)
    routes = {
        "lucidfence_status": "/api/status", "lucidfence_list_devices": "/api/devices",
        "lucidfence_list_incidents": "/api/incidents", "lucidfence_get_risk": "/api/risk",
    }
    if name in routes:
        result = _api("GET", routes[name])
        return _tool_result(result, result.get("ok") is False if isinstance(result, dict) else False)
    if name == "lucidfence_ask_ai":
        question = str(args.get("question") or "").strip()
        if not question:
            return _tool_result({"error": "question es obligatorio"}, True)
        messages = [{"role": "system", "content": "Eres un analista UEM/MDM. Responde de forma concreta y segura."},
                    {"role": "user", "content": question}]
        result = _api("POST", "/api/ai/chat", {"messages": messages})
        return _tool_result(result, result.get("ok") is False if isinstance(result, dict) else False)
    return _tool_result({"error": "unknown tool", "name": name}, True)


def _send(message: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except (ValueError, TypeError):
            continue
        method, request_id = message.get("method"), message.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "lucidfence-mcp", "version": "1.1.0"}}
        elif method == "tools/list":
            result = tools_list()
        elif method == "tools/call":
            params = message.get("params") or {}
            result = tool_call(str(params.get("name") or ""), params.get("arguments") or {})
        else:
            if request_id is None:
                continue
            result = {}
        _send({"jsonrpc": "2.0", "id": request_id, "result": result})


if __name__ == "__main__":
    main()
