from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from lucidfence.shell import LucidFenceShell

ROOT = Path(__file__).resolve().parents[1]


def test_cli_exposes_shell_command():
    result = subprocess.run([sys.executable, str(ROOT / "bin" / "lucidfence"), "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "shell" in result.stdout


def test_shell_commands_are_scriptable_without_network():
    output = []
    shell = LucidFenceShell(ROOT, output.append)
    shell.onecmd("status")
    assert json.loads(output[-1])["mode"] == "local"
    shell.onecmd("simulate 2")
    assert json.loads(output[-1])["cycles"] == 2
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "roadmap.json"
        shell.onecmd(f"export {target}")
        assert target.exists()
        assert json.loads(target.read_text())["plan"]["phases"]
