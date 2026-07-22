from __future__ import annotations

import sys
import subprocess
import os
import tempfile
from pathlib import Path

from core.loop_governance import KillSwitch, classify_risk, gated_merge, run_maker, verify_twice


def test_loop_risk_double_verification_and_auto_merge_gate():
    calls = []
    result = verify_twice(lambda: calls.append(1) is None, ["docs/README.md"], approved=True)
    assert result.first and result.second and len(calls) == 2 and result.auto_merge
    assert classify_risk(["saas_server.py"]) == "high"
    assert classify_risk(["core/product.py"]) == "medium"
    high = verify_twice(lambda: True, ["saas/auth.py"], approved=True)
    assert high.auto_merge is False
    unapproved = verify_twice(lambda: True, ["docs/a.md"], approved=False)
    assert unapproved.auto_merge is False


def test_loop_maker_obeys_kill_switch_and_strips_secret_environment():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); switch = KillSwitch(root)
        previous_key = os.environ.get("DEMO_API_KEY")
        previous_data = os.environ.get("LUCIDFENCE_DATA_DIR")
        os.environ["DEMO_API_KEY"] = "must-not-leak"
        command = [sys.executable, "-c", "import os; print(os.getenv('DEMO_API_KEY', 'clean'))"]
        result = run_maker(command, root, switch, timeout=10)
        assert result.returncode == 0 and result.stdout.strip() == "clean"
        switch.disable("operator stop")
        os.environ["LUCIDFENCE_DATA_DIR"] = td
        import loop_improve
        assert loop_improve.run_loop(max_iter=1, dry_run=True) == 4
        try:
            run_maker(command, root, switch, timeout=10)
            raise AssertionError("maker ran while disabled")
        except RuntimeError as exc:
            assert "kill switch" in str(exc)
        switch.enable(); assert switch.enabled
        if previous_key is None: os.environ.pop("DEMO_API_KEY", None)
        else: os.environ["DEMO_API_KEY"] = previous_key
        if previous_data is None: os.environ.pop("LUCIDFENCE_DATA_DIR", None)
        else: os.environ["LUCIDFENCE_DATA_DIR"] = previous_data


def test_low_risk_branch_is_really_fast_forwarded_only_after_double_pass():
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td); switch = KillSwitch(repo / ".state")
        def git(*args):
            return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True)
        git("init", "-b", "main"); git("config", "user.email", "loop@localhost"); git("config", "user.name", "Loop QA")
        (repo / "README.md").write_text("base\n"); git("add", "README.md"); git("commit", "-m", "base")
        git("checkout", "-b", "maker/docs"); (repo / "README.md").write_text("base\nverified docs\n")
        git("add", "README.md"); git("commit", "-m", "maker docs"); git("checkout", "main")
        verification = verify_twice(lambda: True, ["README.md"], approved=True)
        result = gated_merge(repo, "maker/docs", verification, switch)
        assert result.returncode == 0 and "verified docs" in (repo / "README.md").read_text()
