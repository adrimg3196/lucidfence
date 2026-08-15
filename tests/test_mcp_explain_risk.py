"""Tests de la tool MCP lucidfence_explain_risk (P2.8) — sin red ni servidor."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lucidfence.mcp import lucidfence_mcp as mcp

RISK_ROWS = [
    {"device_id": "dev-1", "device_name": "Tablet A", "score": 72.5, "level": "high",
     "fence_state": "outside",
     "factors": [{"points": 0, "label": "fuera de geocerca permitida", "severity": "high"},
                 {"points": 0, "label": "velocidad imposible entre reportes (40000 km/h): posible spoofing de ubicación", "severity": "high"}],
     "signals": {"location_integrity": {"suspicious": True, "checks": ["impossible_speed"]}},
     "matched_policies": ["pol-lock-outside"]},
    {"device_id": "dev-2", "device_name": "Portátil B", "score": 5.0, "level": "low",
     "fence_state": "inside", "factors": [], "signals": {}, "matched_policies": []},
]


def _with_fake_api(response):
    original = mcp._api
    mcp._api = lambda method, path, payload=None: response
    return original


def _payload(result) -> dict:
    return json.loads(result["content"][0]["text"])


def test_explain_risk_returns_focused_explanation() -> None:
    original = _with_fake_api(RISK_ROWS)
    try:
        result = mcp.tool_call("lucidfence_explain_risk", {"device_id": "dev-1"})
        assert result["isError"] is False
        data = _payload(result)
        assert data["score"] == 72.5 and data["level"] == "high"
        assert any("spoofing" in reason for reason in data["why"])
        assert data["matched_policies"] == ["pol-lock-outside"]
        assert data["signals"]["location_integrity"]["suspicious"] is True
    finally:
        mcp._api = original


def test_explain_risk_unknown_device_lists_known_ids() -> None:
    original = _with_fake_api(RISK_ROWS)
    try:
        result = mcp.tool_call("lucidfence_explain_risk", {"device_id": "dev-999"})
        assert result["isError"] is True
        data = _payload(result)
        assert "no encontrado" in data["error"]
        assert data["known_device_ids"] == ["dev-1", "dev-2"]
    finally:
        mcp._api = original


def test_explain_risk_requires_device_id() -> None:
    result = mcp.tool_call("lucidfence_explain_risk", {})
    assert result["isError"] is True
    assert "obligatorio" in _payload(result)["error"]


def test_explain_risk_propagates_backend_error() -> None:
    original = _with_fake_api({"ok": False, "status": 503, "error": "server caído"})
    try:
        result = mcp.tool_call("lucidfence_explain_risk", {"device_id": "dev-1"})
        assert result["isError"] is True
    finally:
        mcp._api = original


def test_contract_and_tools_list_expose_the_new_tool() -> None:
    assert "lucidfence_explain_risk" in mcp.CONTRACT["tools"]
    tools = {t["name"]: t for t in mcp.tools_list()["tools"]}
    schema = tools["lucidfence_explain_risk"]["inputSchema"]
    assert schema["required"] == ["device_id"]
