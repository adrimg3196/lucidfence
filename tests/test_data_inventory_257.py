"""Issue #257 — data inventory transparency, retention and field minimization.

Acceptance criteria exercised:
  * Fields without purpose/retention declared are rejected (not persisted).
  * Fixtures older than the configured boundary are purged EXACTLY at the limit.
  * The before/after purge report shows counts, per-category counts and a hash
    of the operation — never the deleted values.
  * RBAC prevents roles without the inventory-read capability from consulting it.
  * Export never exposes secret-field markers.
"""
from lucidfence.core.data_inventory import (
    FieldMetadata,
    FieldCategory,
    RetentionClass,
    DataInventoryPolicy,
    ingest,
    purge,
    inventory_export,
    PurgeReport,
)


def _field(name, cls=RetentionClass.STANDARD, age=0.0, **kw) -> FieldMetadata:
    return FieldMetadata(
        field_name=name,
        device_id="dev-1",
        tenant_id="t-a",
        category=(kw.pop("category", FieldCategory.LOCATION.value)),
        purpose=kw.pop("purpose", "policy enforcement"),
        source=kw.pop("source", "uem-pull"),
        collected_at=kw.pop("collected_at", 1_000_000.0 - age),
        retention_class=cls.value if isinstance(cls, RetentionClass) else cls,
        **kw,
    )


def test_undeclared_field_is_rejected():
    bad = FieldMetadata(
        field_name="raw_telemetry",
        device_id="dev-1", tenant_id="t-a", category=FieldCategory.OTHER.value,
        purpose=None, source=None, collected_at=None, retention_class=None,
    )
    accepted, dropped = ingest([bad])
    assert accepted == []
    assert dropped == [bad]


    # Purpose present but no retention class -> still rejected.
    no_ret = FieldMetadata(
        field_name="x", device_id="dev-1", tenant_id="t-a",
        category=FieldCategory.LOCATION.value, purpose="why",
        source="uem", collected_at=1_000_000.0, retention_class=None,
    )
    acc2, drop2 = ingest([no_ret])
    assert acc2 == [] and drop2 == [no_ret]


def test_declared_field_is_accepted_with_purge_boundary():
    f = _field("city", RetentionClass.SHORT)
    accepted, dropped = ingest([f])
    assert dropped == []
    assert len(accepted) == 1
    # SHORT = 7d; boundary = collected_at + 7d.
    assert accepted[0].purge_at == f.collected_at + 7 * 24 * 3600


def test_purge_runs_exactly_at_limit():
    # Collected 7d ago with SHORT retention -> boundary = now exactly.
    age = 7 * 24 * 3600
    f = _field("city", RetentionClass.SHORT, age=age)
    now = f.collected_at + 7 * 24 * 3600  # == purge_at
    accepted, _ = ingest([f])
    kept, report = purge(accepted, now=now)
    assert report.purged == 1
    assert kept == []
    assert report.counts_before == 1 and report.counts_after == 0
    # Just before the limit, NOT purged.
    kept2, report2 = purge(accepted, now=now - 1.0)
    assert report2.purged == 0 and len(kept2) == 1


def test_purge_report_is_count_and_hash_not_values():
    age = 90 * 24 * 3600
    f1 = _field("posture_snap", RetentionClass.STANDARD, age=age, category=FieldCategory.POSTURE.value)
    f2 = _field("city", RetentionClass.STANDARD, age=age, category=FieldCategory.LOCATION.value)
    now = f1.collected_at + 90 * 24 * 3600
    accepted, _ = ingest([f1, f2])
    kept, report = purge(accepted, now=now)
    assert isinstance(report, PurgeReport)
    assert report.purged == 2
    assert report.by_category == {"posture": 1, "location": 1}
    assert len(report.op_hash) == 64  # sha256 hex
    # The report dict must not carry deleted values.
    rd = report.__dict__
    assert all("posture_snap" not in str(v) and "city" not in str(v) for v in rd.values())


def test_forever_fields_never_purged():
    f = _field("compliance_archive", RetentionClass.FOREVER)
    accepted, _ = ingest([f])
    assert accepted[0].purge_at is None
    kept, report = purge(accepted, now=f.collected_at + 10_000 * 24 * 3600)
    assert report.purged == 0 and len(kept) == 1


def test_rbac_blocks_viewer_from_inventory():
    metas = [_field("city", RetentionClass.SHORT)]
    # viewer has no report:export/audit:read -> denied
    denied = inventory_export(metas, role="viewer")
    assert denied["denied"] is True and denied["fields"] == []
    # auditor may read
    ok = inventory_export(metas, role="auditor")
    assert ok["denied"] is False and ok["count"] == 1


def test_export_strips_secrets():
    # A field whose name looks secret is stripped even for an authorized role.
    sec = FieldMetadata(
        field_name="device_api_key", device_id="dev-1", tenant_id="t-a",
        category=FieldCategory.IDENTITY.value, purpose="enrollment",
        source="uem", collected_at=1_000_000.0, retention_class=RetentionClass.LONG.value,
    )
    pub = _field("city", RetentionClass.SHORT)
    out = inventory_export([sec, pub], role="auditor")
    names = {f["field_name"] for f in out["fields"]}
    assert "device_api_key" not in names
    assert "city" in names
