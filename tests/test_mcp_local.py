import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rpc(messages):
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "mcp" / "lucidfence_mcp.py")],
        input=payload, text=True, capture_output=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_mcp_initialize_list_and_learn():
    rows = _rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lucidfence_learn", "arguments": {}}},
    ])
    assert rows[0]["result"]["serverInfo"]["name"] == "lucidfence-mcp"
    names = {item["name"] for item in rows[1]["result"]["tools"]}
    assert {"lucidfence_status", "lucidfence_list_devices", "lucidfence_list_incidents",
            "lucidfence_get_risk", "lucidfence_ask_ai", "lucidfence_learn"} <= names
    text = rows[2]["result"]["content"][0]["text"]
    assert "read-only" in text
    assert "api_key" not in text.lower()


def test_cli_exposes_mcp_command():
    proc = subprocess.run([sys.executable, str(ROOT / "bin" / "lucidfence"), "--help"],
                          text=True, capture_output=True, timeout=10)
    assert proc.returncode == 0
    assert "mcp" in proc.stdout
