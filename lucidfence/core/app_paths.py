"""Portable filesystem locations for the LucidFence local application."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping, Optional

APP_NAME = "LucidFence"


def data_dir(
    env: Optional[Mapping[str, str]] = None,
    *,
    platform: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the user-writable application state directory.

    Explicit ``LUCIDFENCE_DATA_DIR`` always wins. macOS follows the native
    Application Support convention; Linux and other Unix systems follow XDG.
    The function is pure to keep packaging and platform behavior testable.
    """
    values = os.environ if env is None else env
    override = (values.get("LUCIDFENCE_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    actual_home = Path.home() if home is None else Path(home)
    actual_platform = sys.platform if platform is None else platform
    if actual_platform == "darwin":
        return actual_home / "Library" / "Application Support" / APP_NAME

    xdg = (values.get("XDG_STATE_HOME") or "").strip()
    base = Path(xdg).expanduser() if xdg else actual_home / ".local" / "state"
    return base / "lucidfence"


def ensure_data_dir(**kwargs) -> Path:
    path = data_dir(**kwargs)
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path
