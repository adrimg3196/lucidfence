"""Regression coverage for the scheduled recon data pipeline.

The tests execute the real Git helpers against local bare repositories.  They
therefore catch the two production failures that matter: publishing to the
protected default branch and consuming the stale copy that happens to live on
that branch.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

import scripts.recon_social as recon_social


ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / "scripts" / "publish_recon_snapshot.sh"
LOAD = ROOT / "scripts" / "load_recon_snapshot.sh"
SNAPSHOT = Path("data/recon/latest_recon.txt")


def _run(*args: object, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _write(repo: Path, relative: Path, value: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _seed_remote(root: Path, *, with_state: bool) -> tuple[Path, Path]:
    remote = root / "remote.git"
    seed = root / "seed"
    _run("git", "init", "--bare", remote, cwd=root)
    _run("git", "init", "-b", "main", seed, cwd=root)
    _run("git", "config", "user.name", "Recon Test", cwd=seed)
    _run("git", "config", "user.email", "recon-test@lucidfence.local", cwd=seed)
    _write(seed, SNAPSHOT, "stale-main\n")
    _run("git", "add", ".", cwd=seed)
    _run("git", "commit", "-m", "seed main", cwd=seed)
    _run("git", "remote", "add", "origin", remote, cwd=seed)
    _run("git", "push", "-u", "origin", "main", cwd=seed)
    if with_state:
        _run("git", "switch", "-c", "recon-state", cwd=seed)
        _write(seed, SNAPSHOT, "fresh-state\n")
        _run("git", "add", ".", cwd=seed)
        _run("git", "commit", "-m", "seed recon state", cwd=seed)
        _run("git", "push", "-u", "origin", "recon-state", cwd=seed)
    return remote, seed


def test_snapshot_publisher_keeps_main_unchanged_and_updates_recon_state():
    """Publishing a fresh snapshot must never add a commit to protected main."""
    with tempfile.TemporaryDirectory(prefix="recon-publish-") as tmp:
        root = Path(tmp)
        remote, _seed = _seed_remote(root, with_state=False)
        runner = root / "runner"
        _run("git", "clone", "--branch", "main", remote, runner, cwd=root)
        _run("git", "config", "user.name", "github-actions[bot]", cwd=runner)
        _run(
            "git",
            "config",
            "user.email",
            "github-actions[bot]@users.noreply.github.com",
            cwd=runner,
        )
        _write(runner, SNAPSHOT, "new-snapshot\n")

        _run(PUBLISH, SNAPSHOT, "origin", "recon-state", cwd=runner)

        main_value = _run(
            "git", "--git-dir", remote, "show", f"main:{SNAPSHOT}", cwd=root
        ).stdout
        state_value = _run(
            "git", "--git-dir", remote, "show", f"recon-state:{SNAPSHOT}", cwd=root
        ).stdout
        assert main_value == "stale-main\n"
        assert state_value == "new-snapshot\n"

        _run("git", "switch", "main", cwd=runner)
        _write(runner, SNAPSHOT, "second-snapshot\n")
        _run(PUBLISH, SNAPSHOT, "origin", "recon-state", cwd=runner)

        second_state_value = _run(
            "git", "--git-dir", remote, "show", f"recon-state:{SNAPSHOT}", cwd=root
        ).stdout
        assert second_state_value == "second-snapshot\n"


def test_snapshot_loader_replaces_stale_main_copy_with_recon_state():
    """The daily analysis must consume recon-state, not main's stale artifact."""
    with tempfile.TemporaryDirectory(prefix="recon-load-") as tmp:
        root = Path(tmp)
        remote, _seed = _seed_remote(root, with_state=True)
        consumer = root / "consumer"
        _run("git", "clone", "--branch", "main", remote, consumer, cwd=root)
        assert (consumer / SNAPSHOT).read_text(encoding="utf-8") == "stale-main\n"

        _run(LOAD, SNAPSHOT, "origin", "recon-state", cwd=consumer)

        assert (consumer / SNAPSHOT).read_text(encoding="utf-8") == "fresh-state\n"


def test_snapshot_loader_removes_stale_copy_when_state_branch_is_unavailable():
    """A failed state fetch must be reported as absent, never as old evidence."""
    with tempfile.TemporaryDirectory(prefix="recon-missing-") as tmp:
        root = Path(tmp)
        remote, _seed = _seed_remote(root, with_state=False)
        consumer = root / "consumer"
        _run("git", "clone", "--branch", "main", remote, consumer, cwd=root)

        result = _run(LOAD, SNAPSHOT, "origin", "recon-state", cwd=consumer)

        assert result.returncode == 0
        assert not (consumer / SNAPSHOT).exists()


def test_youtube_marks_missing_agent_reach_python_unavailable():
    """A runner without agent-reach must produce evidence, not an exception."""
    previous = recon_social.PY
    try:
        recon_social.PY = "/definitely/missing/agent-reach-python"
        result = recon_social.yt("Applivery UEM", 1)
    finally:
        recon_social.PY = previous

    assert len(result) == 1
    assert result[0].startswith("(unavailable:")
    assert "agent-reach" in result[0]


def test_reddit_marks_missing_opencli_unavailable_without_traceback():
    """A runner without opencli must finish once with an explicit status."""
    previous_local = recon_social.LOCAL
    previous_path = os.environ.get("PATH")
    with tempfile.TemporaryDirectory(prefix="no-opencli-") as tmp:
        try:
            recon_social.LOCAL = tmp
            os.environ["PATH"] = tmp
            result = recon_social.reddit_search("UEM MDM")
        finally:
            recon_social.LOCAL = previous_local
            if previous_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = previous_path

    assert result.startswith("(unavailable:")
    assert "opencli" in result
