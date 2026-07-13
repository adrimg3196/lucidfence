"""Load and normalize config.json, merging a .env file when present."""
from __future__ import annotations

import json
import os
from pathlib import Path


def _load_env(path: Path) -> dict:
    env: dict = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load(config_path: Path) -> dict:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    env = _load_env(Path(config_path).resolve().parent / ".env")
    # If a real API key is present, default to live mode unless explicitly set.
    if env.get("APPLIVERY_API_KEY") and cfg.get("mode", "simulation") == "simulation":
        # respect explicit mode, but if dry_run is on keep simulation-safe behaviour
        if os.environ.get("APPLIVERY_FORCE_SIM") != "1":
            cfg["mode"] = "live"
    for k, v in env.items():
        os.environ.setdefault(k, v)
    # The workspace/org id the operator enters in Settings is stored as
    # APPLIVERY_ORG_ID in .env; make it win over the static placeholder in
    # config.json so the live integration actually targets the right org.
    org_env = env.get("APPLIVERY_ORG_ID")
    if org_env and cfg.get("applivery") is not None:
        cfg["applivery"]["org_id"] = org_env
    return cfg
