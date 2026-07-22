"""Safety controls for autonomous improvement Loop levels 2/3."""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HIGH_RISK = {"saas/auth.py", "core/secrets.py", "core/api_keys.py", "saas_server.py", ".github/workflows"}
MEDIUM_RISK = {"core/", "saas/", "bin/", "scripts/"}


def classify_risk(paths: list[str]) -> str:
    clean = [str(Path(path)).replace("\\", "/").lstrip("./") for path in paths]
    if any(any(path == marker or path.startswith(marker + "/") for marker in HIGH_RISK) for path in clean):
        return "high"
    if any(any(path.startswith(marker) for marker in MEDIUM_RISK) for path in clean):
        return "medium"
    return "low"


class KillSwitch:
    def __init__(self, data_root: Path):
        self.path = Path(data_root) / "loop.disabled"

    @property
    def enabled(self) -> bool:
        return not self.path.exists()

    def disable(self, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"disabled_at": time.time(), "reason": reason}) + "\n", encoding="utf-8")

    def enable(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass(frozen=True)
class Verification:
    first: bool
    second: bool
    risk: str
    approved: bool

    @property
    def auto_merge(self) -> bool:
        return self.first and self.second and self.risk == "low" and self.approved


def verify_twice(check: Callable[[], bool], paths: list[str], approved: bool = False) -> Verification:
    first = bool(check())
    second = bool(check()) if first else False
    return Verification(first, second, classify_risk(paths), bool(approved))


def run_maker(command: list[str], cwd: Path, kill_switch: KillSwitch, timeout: int = 900) -> subprocess.CompletedProcess:
    """Run an explicitly configured maker without a shell.

    No command is inferred from model text. Operators must supply an argv list,
    and the persistent kill switch blocks execution before process creation.
    """
    if not kill_switch.enabled:
        raise RuntimeError("loop kill switch is disabled")
    if not command or not Path(command[0]).name:
        raise ValueError("maker command required")
    env = {key: value for key, value in os.environ.items() if not any(token in key.upper() for token in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
    return subprocess.run(command, cwd=Path(cwd), env=env, text=True, capture_output=True, timeout=timeout, shell=False)


def gated_merge(repo: Path, branch: str, verification: Verification, kill_switch: KillSwitch) -> subprocess.CompletedProcess:
    """Fast-forward a low-risk maker branch only after two independent PASSes."""
    if not kill_switch.enabled:
        raise RuntimeError("loop kill switch is disabled")
    if not verification.auto_merge:
        raise RuntimeError("auto-merge gate not satisfied")
    valid = subprocess.run(["git", "check-ref-format", "--branch", branch], cwd=repo, capture_output=True, text=True)
    if valid.returncode:
        raise ValueError("invalid branch")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True)
    if dirty.stdout.strip():
        raise RuntimeError("working tree is not clean")
    return subprocess.run(["git", "merge", "--ff-only", "--no-edit", branch], cwd=repo,
                          text=True, capture_output=True, timeout=120, shell=False)
