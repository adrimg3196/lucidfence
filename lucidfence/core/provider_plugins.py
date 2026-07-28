"""Local provider plugin discovery for LucidFence's improvement loop.

A plugin is one Python file in ``plugins/providers`` exposing ``PROVIDER`` as a
plain dict with name/env/base/model. Discovery is explicit, bounded, and skips
invalid files without breaking the product.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Iterable

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def validate_provider(provider: dict) -> dict:
    required = {"name", "env", "base", "model"}
    if not isinstance(provider, dict) or not required.issubset(provider):
        raise ValueError(f"provider requires {sorted(required)}")
    clean = {key: str(provider[key]).strip() for key in required}
    if not _NAME.fullmatch(clean["name"]):
        raise ValueError("invalid provider name")
    if not clean["env"].startswith("LF_PROVIDER_") or not clean["env"].endswith("_API_KEY"):
        raise ValueError("provider env must be LF_PROVIDER_*_API_KEY")
    if not clean["base"].startswith("https://"):
        raise ValueError("provider base must use https")
    return clean


def discover_provider_plugins(directory: str | Path) -> list[dict]:
    root = Path(directory)
    if not root.is_dir():
        return []
    providers = []
    for path in sorted(root.glob("*.py"))[:100]:
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"lucidfence_provider_{path.stem}", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            providers.append(validate_provider(module.PROVIDER))
        except Exception:
            continue
    names = set()
    unique = []
    for provider in providers:
        if provider["name"] not in names:
            names.add(provider["name"])
            unique.append(provider)
    return unique


def merge_providers(builtin: Iterable[dict], plugins: Iterable[dict]) -> list[dict]:
    merged = {}
    for provider in [*builtin, *plugins]:
        try:
            clean = validate_provider(provider)
        except ValueError:
            continue
        merged.setdefault(clean["name"], clean)
    return list(merged.values())
