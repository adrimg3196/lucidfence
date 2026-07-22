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
    config_path = Path(config_path)
    if not config_path.exists():
        # No config file yet (fresh clone / first run): start from safe defaults
        # instead of crashing. The server runs in simulation mode out of the box.
        cfg: dict = {"mode": "simulation"}
        env = _load_env(config_path.resolve().parent / ".env")
        for k, v in env.items():
            os.environ.setdefault(k, v)
        org_env = env.get("APPLIVERY_ORG_ID")
        if org_env:
            cfg.setdefault("applivery", {})["org_id"] = org_env
        return cfg
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    env = _load_env(config_path.resolve().parent / ".env")
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
    if org_env:
        cfg.setdefault("applivery", {})["org_id"] = org_env

    # Intune (Microsoft Graph) live mode — only constructed on demand by
    # build_intune_adapter_from_config(). Mirrors the intune env-var contract
    # so a minimal config.json + .env enables live mode without code changes.
    intune_cfg = cfg.setdefault("mdm", {}).setdefault("intune", {})
    intune_cfg.setdefault("live", bool(env.get("INTUNE_TENANT_ID")))
    intune_cfg.setdefault("tenant_id", env.get("INTUNE_TENANT_ID", ""))
    intune_cfg.setdefault("client_id", env.get("INTUNE_CLIENT_ID", ""))
    intune_cfg.setdefault("client_secret", env.get("INTUNE_CLIENT_SECRET", ""))
    intune_cfg.setdefault(
        "endpoint_template",
        env.get("INTUNE_ENDPOINT", "https://graph.microsoft.com/v1.0"),
    )

    # Jamf Pro (Jamf Pro API) live mode — only constructed on demand by
    # build_jamf_adapter_from_config(). Mirrors the intune env-var contract
    # so a minimal config.json + .env enables live mode without code changes.
    jamf_cfg = cfg.setdefault("mdm", {}).setdefault("jamf", {})
    jamf_cfg.setdefault("live", bool(env.get("JAMF_BASE_URL")))
    jamf_cfg.setdefault("base_url", env.get("JAMF_BASE_URL", ""))
    jamf_cfg.setdefault("client_id", env.get("JAMF_CLIENT_ID", ""))
    jamf_cfg.setdefault("client_secret", env.get("JAMF_CLIENT_SECRET", ""))

    # VMware Workspace ONE UEM live mode. Secrets stay in environment/tenant
    # config and the adapter performs no network call during construction.
    workspace_cfg = cfg.setdefault("mdm", {}).setdefault("workspace_one", {})
    workspace_cfg.setdefault("live", bool(env.get("WORKSPACE_ONE_BASE_URL")))
    workspace_cfg.setdefault("base_url", env.get("WORKSPACE_ONE_BASE_URL", ""))
    workspace_cfg.setdefault("tenant_code", env.get("WORKSPACE_ONE_TENANT_CODE", ""))
    workspace_cfg.setdefault("username", env.get("WORKSPACE_ONE_USERNAME", ""))
    workspace_cfg.setdefault("password", env.get("WORKSPACE_ONE_PASSWORD", ""))

    return cfg
