import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.mcp.server import run_stdio_server, tools_list, tool_call


def _rpc(messages):
    stdin_data = "\n".join(json.dumps(m) for m in messages) + "\n"
    stdin = io.StringIO(stdin_data)
    stdout = io.StringIO()
    run_stdio_server(stdin, stdout)
    stdout.seek(0)
    return [json.loads(line) for line in stdout.readlines() if line.strip()]


def test_mcp_official_initialize_and_tools_list():
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    assert len(rows) == 2
    assert rows[0]["result"]["serverInfo"]["name"] == "lucidfence-official-mcp"

    tools = rows[1]["result"]["tools"]
    names = {t["name"] for t in tools}
    expected_tools = {
        "list_fences", "get_fence", "create_fence", "delete_fence",
        "list_devices", "get_device_state", "list_incidents", "list_events"
    }
    assert expected_tools == names


def test_mcp_official_fences_lifecycle_and_details():
    # 1. List fences initially
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {
            "name": "list_fences", "arguments": {}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    initial_fences = json.loads(rows[0]["result"]["content"][0]["text"])["fences"]
    assert isinstance(initial_fences, list)

    # 2. Create a new fence
    fence_name = f"mcp-test-fence"
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {
            "name": "create_fence", "arguments": {
                "name": fence_name,
                "type": "circle",
                "lat": 40.7128,
                "lng": -74.0060,
                "radius_m": 500,
                "actions": [
                    {"action": "message", "when": "on_enter", "enabled": True}
                ]
            }
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    created_data = json.loads(rows[0]["result"]["content"][0]["text"])
    assert created_data["ok"] is True
    new_fence = created_data["fence"]
    assert new_fence["name"] == fence_name
    fence_id = new_fence["id"]

    # 3. Get the created fence details
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {
            "name": "get_fence", "arguments": {"id": fence_id}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    fetched_fence = json.loads(rows[0]["result"]["content"][0]["text"])
    assert fetched_fence["name"] == fence_name
    assert fetched_fence["radius_m"] == 500

    # 4. Try to get a non-existent fence
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {
            "name": "get_fence", "arguments": {"id": "non-existent-id"}
        }}
    ])
    assert rows[0]["result"]["isError"] is True
    assert "no encontrada" in json.loads(rows[0]["result"]["content"][0]["text"])["error"]

    # 5. Delete the fence
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {
            "name": "delete_fence", "arguments": {"id": fence_id}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    deleted_data = json.loads(rows[0]["result"]["content"][0]["text"])
    assert deleted_data["ok"] is True

    # 6. Verify it was deleted
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {
            "name": "get_fence", "arguments": {"id": fence_id}
        }}
    ])
    assert rows[0]["result"]["isError"] is True


def test_mcp_official_devices_and_status():
    # 1. List devices
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {
            "name": "list_devices", "arguments": {}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    devices = json.loads(rows[0]["result"]["content"][0]["text"])
    assert isinstance(devices, list)

    # If there are devices, test get_device_state
    if devices:
        device_id = devices[0]["device_id"]
        rows = _rpc([
            {"jsonrpc": "2.0", "id": 21, "method": "tools/call", "params": {
                "name": "get_device_state", "arguments": {"id": device_id}
            }}
        ])
        assert rows[0]["result"]["isError"] is False
        state = json.loads(rows[0]["result"]["content"][0]["text"])
        assert "device" in state
        assert state["device"]["device_id"] == device_id


def test_mcp_official_incidents_and_events():
    # 1. List incidents
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {
            "name": "list_incidents", "arguments": {}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    inc_data = json.loads(rows[0]["result"]["content"][0]["text"])
    assert "incidents" in inc_data

    # 2. List events
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {
            "name": "list_events", "arguments": {}
        }}
    ])
    assert rows[0]["result"]["isError"] is False
    events = json.loads(rows[0]["result"]["content"][0]["text"])
    assert isinstance(events, list)
