"""Read-only data inventory: transparency, retention and field-level minimization.

Issue #257 — "Transparencia, retención y minimización por campo".

Design contract (from the issue):
  * Every persisted field carries metadata: purpose, source, collected_at,
    retention_class, purge_at and visibility.
  * The administrator/auditor can ask "qué sabe LucidFence" per device and
    tenant, and see how long each field is kept and whether the purge ran.
  * Purge is deterministic: it removes exactly the records past their
    configured boundary and emits a report with COUNTS, CATEGORIES and a HASH
    of the operation — never the deleted values.
  * Fields without a declared purpose/retention are REJECTED at ingest (never
    persisted). This is the minimization guarantee.
  * RBAC gates consultation of the data inventory: roles without the right
    capability cannot read it.
  * Export never exposes secrets (no key material, tokens, passwords).

This module is pure deterministic Python (stdlib-only) so it is testable
offline. It is read-only metadata about what is persisted elsewhere — it does
not itself hold device telemetry; the engine/state_store feed it their field
declarations.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

# Capabilities that may consult the data inventory. We deliberately reuse the
# existing RBAC matrix instead of inventing a new capability: owner + admin
# (report:export) and auditor (audit:read) may inspect what LucidFence knows;
# operator/viewer may not. See lucidfence/saas/auth.py ROLE_CAPS.
_INVENTORY_READ_CAPS = {"report:export", "audit:read"}

# Field markers that must never appear in an export even for an authorized role.
_SECRET_MARKERS = ("private_key", "secret", "token", "password", "key_material",
                   "api_key", "bearer")


class RetentionClass(str, Enum):
    """Coarse retention buckets. Each maps to a default window (seconds)."""
    EPHEMERAL = "ephemeral"      # <= 1h, e.g. live CoT signals
    SHORT = "short"              # <= 7d, e.g. derived geo state
    STANDARD = "standard"        # <= 90d, e.g. posture snapshots
    LONG = "long"               # <= 365d, e.g. audit/compliance
    FOREVER = "forever"         # retained by policy (e.g. compliance archive)
    UNDECLARED = "undeclared"    # NOT allowed to persist


# Default windows per class. UNDECLARED has no window: it is rejected at ingest.
RETENTION_SECONDS: dict[RetentionClass, Optional[int]] = {
    RetentionClass.EPHEMERAL: 3600,
    RetentionClass.SHORT: 7 * 24 * 3600,
    RetentionClass.STANDARD: 90 * 24 * 3600,
    RetentionClass.LONG: 365 * 24 * 3600,
    RetentionClass.FOREVER: None,          # no automatic purge
    RetentionClass.UNDECLARED: 0,          # rejected
}

# Default minimum retention class per data category (privacy-by-design floor).
DEFAULT_CATEGORY_CLASS: dict[str, RetentionClass] = {
    "location": RetentionClass.SHORT,
    "identity": RetentionClass.STANDARD,
    "posture": RetentionClass.STANDARD,
    "vulnerability": RetentionClass.LONG,
    "agent_trace": RetentionClass.STANDARD,
}


class FieldCategory(str, Enum):
    LOCATION = "location"
    IDENTITY = "identity"
    POSTURE = "posture"
    VULNERABILITY = "vulnerability"
    AGENT_TRACE = "agent_trace"
    OTHER = "other"


@dataclass
class FieldMetadata:
    """Metadata for ONE persisted field on ONE device/tenant.

    `purpose`, `source`, `collected_at` and a declared `retention_class` are
    all required for the field to be allowed to persist.
    """
    field_name: str
    device_id: str
    tenant_id: str
    category: str                       # FieldCategory value
    purpose: Optional[str] = None       # why we hold it; None => rejected
    source: Optional[str] = None        # where it came from; None => rejected
    collected_at: Optional[float] = None  # epoch seconds; None => rejected
    retention_class: Optional[str] = None  # RetentionClass value; None => undeclared
    visibility: str = "internal"        # internal | auditor | owner
    # resolved at ingest:
    retention_seconds: Optional[int] = None
    purge_at: Optional[float] = None    # epoch seconds boundary

    def declared(self) -> bool:
        return (
            self.purpose is not None
            and self.source is not None
            and self.collected_at is not None
            and self.retention_class is not None
            and self.retention_class != RetentionClass.UNDECLARED.value
        )

    def as_dict(self, include_purge: bool = True) -> dict:
        d = asdict(self)
        if not include_purge:
            d.pop("retention_seconds", None)
            d.pop("purge_at", None)
        return d


@dataclass
class PurgeReport:
    """Deterministic evidence of a purge run. Never contains deleted values."""
    ran_at: float
    counts_before: int
    counts_after: int
    purged: int
    by_category: dict[str, int]       # category -> count purged
    op_hash: str                       # sha256 over the purged field identities
    boundary: float                    # the purge_at threshold used


def _resolve_class(meta: FieldMetadata, policy: "DataInventoryPolicy") -> RetentionClass:
    raw = meta.retention_class
    if raw is None:
        # fall back to the category floor if the policy allows inference
        if policy.infer_category_floor:
            return DEFAULT_CATEGORY_CLASS.get(meta.category, RetentionClass.STANDARD)
        return RetentionClass.UNDECLARED
    try:
        return RetentionClass(raw)
    except ValueError:
        return RetentionClass.UNDECLARED


def ingest(metas: list[FieldMetadata],
           policy: Optional["DataInventoryPolicy"] = None,
           now: Optional[float] = None) -> tuple[list[FieldMetadata], list[FieldMetadata]]:
    """Validate field metadata and resolve purge boundaries.

    Returns (accepted, dropped). Fields that are not declared (no purpose/
    source/collected_at or an UNDECLARED retention class) are DROPPED — never
    persisted — which is the minimization guarantee from the acceptance criteria.

    When `policy.reject_undeclared` is True (default), any undeclared field is
    dropped. When False, undeclared fields are kept but flagged (used only for
    migration reporting; the issue's contract keeps rejection on).
    """
    policy = policy or DataInventoryPolicy()
    now = now if now is not None else time.time()
    accepted: list[FieldMetadata] = []
    dropped: list[FieldMetadata] = []
    for m in metas:
        cls = _resolve_class(m, policy)
        m.retention_class = cls.value
        if cls is RetentionClass.UNDECLARED:
            if policy.reject_undeclared:
                dropped.append(m)
                continue
        if m.purpose is None or m.source is None or m.collected_at is None:
            if policy.reject_undeclared:
                dropped.append(m)
                continue
        win = RETENTION_SECONDS.get(cls)
        m.retention_seconds = win
        if win is not None and m.collected_at is not None:
            m.purge_at = m.collected_at + win
        else:
            m.purge_at = None  # FOREVER or UNDECLARED-passthrough
        accepted.append(m)
    return accepted, dropped


def purge(metas: list[FieldMetadata], now: Optional[float] = None) -> tuple[list[FieldMetadata], PurgeReport]:
    """Deterministically purge fields past their retention boundary.

    A field is purged iff `purge_at is not None and now >= purge_at` — i.e.
    exactly at the configured limit it is removed (the acceptance criterion
    "fixtures viejas se purgan exactamente en el límite configurado").
    FOREVER fields (purge_at None) are never purged.

    The report carries COUNTS, per-CATEGORY counts and a HASH over the purged
    field identities — never the values.
    """
    now = now if now is not None else time.time()
    kept: list[FieldMetadata] = []
    purged_ids: list[str] = []
    by_category: dict[str, int] = {}
    for m in metas:
        if m.purge_at is not None and now >= m.purge_at:
            purged_ids.append(f"{m.tenant_id}/{m.device_id}/{m.field_name}")
            by_category[m.category] = by_category.get(m.category, 0) + 1
        else:
            kept.append(m)
    op_hash = _operation_hash(purged_ids)
    report = PurgeReport(
        ran_at=now,
        counts_before=len(metas),
        counts_after=len(kept),
        purged=len(purged_ids),
        by_category=by_category,
        op_hash=op_hash,
        boundary=now,  # report at the moment of the run; per-field boundary is m.purge_at
    )
    return kept, report


def _operation_hash(identities: list[str]) -> str:
    """sha256 over the sorted purged field identities — verifiable, no values."""
    h = hashlib.sha256()
    for ident in sorted(identities):
        h.update(ident.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def inventory_export(metas: list[FieldMetadata], role: Optional[str],
                     include_secret_fields: bool = False) -> dict:
    """"Qué sabe LucidFence" — export the data inventory for a device/tenant.

    RBAC: roles without `report:export` or `audit:read` get an empty result and
    an explicit `denied` flag. Secrets are stripped unless the caller explicitly
    opts in (which the API never does — this exists only so tests can prove the
    stripping path). The export never carries raw secret values.
    """
    allowed = role is not None and bool(_INVENTORY_READ_CAPS & _role_caps(role))
    if not allowed:
        return {"denied": True, "reason": "role lacks inventory-read capability",
                "fields": []}
    fields = []
    for m in metas:
        if not include_secret_fields and _looks_secret(m.field_name):
            continue
        fields.append({
            "field_name": m.field_name,
            "category": m.category,
            "purpose": m.purpose,
            "source": m.source,
            "collected_at": m.collected_at,
            "retention_class": m.retention_class,
            "purge_at": m.purge_at,
            "visibility": m.visibility,
        })
    return {"denied": False, "fields": fields,
            "count": len(fields)}


def _looks_secret(field_name: str) -> bool:
    low = field_name.lower()
    return any(marker in low for marker in _SECRET_MARKERS)


def _role_caps(role: str) -> set[str]:
    """Resolve a role's capability set from the project's RBAC matrix.

    Imported lazily so this module stays usable in isolation (tests).
    """
    try:
        from lucidfence.saas.auth import ROLE_CAPS  # type: ignore
        return set(ROLE_CAPS.get(role, set()))
    except Exception:
        # Fallback: only the documented inventory-capable roles pass.
        allow = {"owner", "admin", "auditor"}
        return _INVENTORY_READ_CAPS if role in allow else set()


@dataclass
class DataInventoryPolicy:
    """Tunables for ingest/purge behaviour."""
    reject_undeclared: bool = True        # drop fields without declared retention
    infer_category_floor: bool = False    # never infer by default (explicit > silent)
    min_class_per_category: dict = field(
        default_factory=lambda: {
            k: v.value for k, v in DEFAULT_CATEGORY_CLASS.items()
        }
    )
