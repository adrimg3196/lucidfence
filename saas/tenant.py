#!/usr/bin/env python3
"""Multi-tenant layer for the local LucidFence SaaS.

Each organization (tenant) gets its own isolated data directory under
``data/tenants/<org_id>/`` and its own engine instance. This is what turns the
single-fleet MVP into a multi-tenant SaaS while staying 100% local.

Inspired by Fleet's "teams" isolation model: a tenant owns devices, fences,
users, and a plan. Nothing leaves the machine.
"""
from __future__ import annotations

import json
import re
import secrets
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "org"


@dataclass
class Org:
    id: str
    name: str
    slug: str
    plan: str = "free"          # free | pro | enterprise
    created_at: str = ""
    owner_id: str = ""
    settings: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class TenantStore:
    """Persists organizations and maps them to isolated data directories."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.tenants_dir = self.root / "tenants"
        self.tenants_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.tenants_dir / "_orgs.json"
        self._orgs: dict[str, Org] = {}
        self._by_slug: dict[str, str] = {}
        self._load()

    # ---- persistence ----------------------------------------------------
    def _load(self):
        if self.index_path.exists():
            try:
                raw = json.loads(self.index_path.read_text(encoding="utf-8"))
                for o in raw:
                    org = Org(**o)
                    self._orgs[org.id] = org
                    self._by_slug[org.slug] = org.id
            except Exception:
                self._orgs = {}

    def _save(self):
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps([o.to_dict() for o in self._orgs.values()],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.index_path)

    # ---- CRUD -----------------------------------------------------------
    def create(self, name: str, owner_id: str, plan: str = "free") -> Org:
        org_id = f"org_{uuid.uuid4().hex[:10]}"
        slug = slugify(name)
        # ensure unique slug
        base, i = slug, 1
        while slug in self._by_slug:
            slug = f"{base}-{i}"
            i += 1
        org = Org(id=org_id, name=name, slug=slug, plan=plan,
                  created_at=now_iso(), owner_id=owner_id,
                  limits=PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]))
        # create isolated data dir
        (self.tenants_dir / org_id).mkdir(parents=True, exist_ok=True)
        (self.tenants_dir / org_id / "data").mkdir(parents=True, exist_ok=True)
        self._orgs[org_id] = org
        self._by_slug[slug] = org_id
        self._save()
        return org

    def get(self, org_id: str) -> Optional[Org]:
        return self._orgs.get(org_id)

    def get_by_slug(self, slug: str) -> Optional[Org]:
        oid = self._by_slug.get(slug)
        return self._orgs.get(oid) if oid else None

    def list_for_user(self, user_id: str) -> list[Org]:
        # In a real SaaS this is a membership query; here owner_id is the link.
        return [o for o in self._orgs.values() if o.owner_id == user_id]

    def update_plan(self, org_id: str, plan: str) -> Optional[Org]:
        org = self._orgs.get(org_id)
        if not org:
            return None
        org.plan = plan
        org.limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        self._save()
        return org

    def data_dir(self, org_id: str) -> Path:
        return self.tenants_dir / org_id / "data"

    def all(self) -> list[Org]:
        return list(self._orgs.values())


# Plan catalogue (mock billing — no real payment, 100% local).
# Free limits reconciled with the GTM pricing (docs/revenue-model.md +
# static/PRICING.md + landing index.html): the Freemium/self-hosted tier
# is advertised as "hasta 25 dispositivos" with geocercas ilimitadas.
# The truly-unlimited self-hosted product ships via scripts/lucidfence_saas_seed.sh
# (Docker, no PLAN_LIMITS enforcement); these caps govern the managed SaaS free trial.
PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "max_devices": 25,
        "max_fences": 1000,
        "retention_days": 30,
        "features": ["map", "devices", "basic_actions", "risk_center"],
        "label": "Freemium",
        "price": "0€/mes",
    },
    "pro": {
        "max_devices": 250,
        "max_fences": 50,
        "retention_days": 90,
        "features": ["map", "devices", "all_actions", "risk_center", "policies",
                     "compliance", "export", "webhooks", "sso_mock"],
        "label": "Pro",
        "price": "49€/mes",
    },
    "enterprise": {
        "max_devices": 10000,
        "max_fences": 1000,
        "retention_days": 365,
        "features": ["map", "devices", "all_actions", "risk_center", "policies",
                     "compliance", "export", "webhooks", "sso_mock",
                     "audit_log", "multi_region_mock", "priority_support"],
        "label": "Enterprise",
        "price": "Bajo demanda",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
