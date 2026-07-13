"""Helper para tests herméticos: construye un Engine de LucidFence en un
directorio temporal, SIN depender de data/ ni config.json del repo.

Esto arregla los fallos de CI (IndexError/KeyError) donde los tests asumían
que el CWD tenía data/tenants y config.json poblados. En CI el repo está limpio.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config_loader  # noqa: E402
from saas.tenant import TenantStore  # noqa: E402
from core.engine import Engine  # noqa: E402


def make_temp_engine(cooldown_seconds: int = 3600, org_name: str = "test-org") -> Engine:
    """Devuelve un Engine aislado en tempdir con fences/routes/policies vacíos
    y un tenant de prueba. No toca el CWD ni data/ del repo."""
    tmp = Path(tempfile.mkdtemp(prefix="lucidfence-test-"))
    (tmp / "fences.json").write_text(json.dumps({"fences": []}), encoding="utf-8")
    (tmp / "routes.json").write_text("[]", encoding="utf-8")
    (tmp / "policies.json").write_text("[]", encoding="utf-8")

    ts = TenantStore(tmp)
    org = ts.create(name=org_name, owner_id="owner-test", plan="free")
    tdir = ts.data_dir(org.id)

    cfg: dict = {
        "mode": "simulation",
        "autostart": False,
        "data_dir": str(tdir),
        "org_id": org.id,
        "fences_path": str(tmp / "fences.json"),
        "routes_path": str(tmp / "routes.json"),
        "policies_path": str(tmp / "policies.json"),
        "action_cooldown_seconds": cooldown_seconds,
        "incident_webhook_url": "https://hooks.example.com/test",
    }
    return Engine(cfg)
