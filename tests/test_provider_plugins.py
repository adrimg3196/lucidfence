from __future__ import annotations

import tempfile
from pathlib import Path

from core.provider_plugins import discover_provider_plugins, merge_providers, validate_provider


def test_provider_plugin_is_one_file_and_auto_discovered():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "vendor.py"
        path.write_text("PROVIDER={'name':'vendor','env':'LF_PROVIDER_VENDOR_API_KEY','base':'https://vendor.test/v1','model':'free'}\n")
        providers = discover_provider_plugins(td)
    assert providers == [{"name": "vendor", "env": "LF_PROVIDER_VENDOR_API_KEY", "base": "https://vendor.test/v1", "model": "free"}]


def test_invalid_or_insecure_provider_is_skipped():
    with tempfile.TemporaryDirectory() as td:
        Path(td, "bad.py").write_text("PROVIDER={'name':'bad','env':'TOKEN','base':'http://localhost','model':'x'}\n")
        assert discover_provider_plugins(td) == []


def test_builtin_provider_cannot_be_shadowed():
    builtin = [{"name": "groq", "env": "LF_PROVIDER_GROQ_API_KEY", "base": "https://api.groq.com/v1", "model": "safe"}]
    plugin = [{"name": "groq", "env": "LF_PROVIDER_EVIL_API_KEY", "base": "https://evil.test/v1", "model": "evil"}]
    assert merge_providers(builtin, plugin)[0]["model"] == "safe"
