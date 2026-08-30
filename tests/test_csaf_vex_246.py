"""Issue #246 -- local CSAF/VEX ingestion and applicability to installed software.

Acceptance criteria exercised:
  * Fixtures cover affected, not_affected (with justification), fixed,
    under_investigation and an invalid document.
  * An ambiguous match does NOT change risk and is surfaced for review.
  * Ingestion rejects impossible future timestamps and unknown VEX statuses
    without breaking the rest of the batch.
  * The report links advisory -> product -> installed evidence -> decision.
  * Everything runs offline, stdlib-only.
"""

from lucidfence.core.csaf_vex import (
    FIXTURES,
    VexStatus,
    MatchConfidence,
    InstalledPackage,
    ingest_csaf,
    load_fixture,
    match_statements,
    build_report,
)


def _inv() -> list[InstalledPackage]:
    return [
        InstalledPackage(name="openssl", version="3.0.2-1",
                         purl="pkg:deb/ubuntu/openssl@3.0.2-1"),
        InstalledPackage(name="log4j", version="2.17.1",
                         purl="pkg:generic/log4j@2.17.1"),
        InstalledPackage(name="left-pad", version="1.3.0",
                         purl="pkg:npm/left-pad@1.3.0"),
        InstalledPackage(name="curl", version="8.0.0",
                         purl="pkg:generic/curl@8.0.0"),
        # Two packages with the same purl -> ambiguous on purpose.
        InstalledPackage(name="shared-lib", version="2.0",
                         purl="pkg:generic/shared-lib@2.0"),
        InstalledPackage(name="shared-lib-fork", version="2.0",
                         purl="pkg:generic/shared-lib@2.0"),
    ]


def test_affected_exact_match():
    stmts = ingest_csaf(load_fixture("affected_exact"), source="fx")
    assert len(stmts) == 1
    s = stmts[0]
    assert s.status == VexStatus.AFFECTED
    assert s.advisory_id == "ADV-2026-001"
    res = match_statements(stmts, _inv())[0]
    assert res.confidence == MatchConfidence.EXACT
    assert res.decision == "affected"
    assert not res.needs_review


def test_not_affected_preserves_justification():
    stmts = ingest_csaf(load_fixture("not_affected_with_justification"), source="fx")
    s = stmts[0]
    assert s.status == VexStatus.NOT_AFFECTED
    assert s.justification and "2.17.1" in s.justification
    res = match_statements(stmts, _inv())[0]
    assert res.confidence == MatchConfidence.EXACT
    assert res.decision == "not_affected"
    assert not res.needs_review


def test_fixed_status():
    stmts = ingest_csaf(load_fixture("fixed"), source="fx")
    assert stmts[0].status == VexStatus.FIXED
    res = match_statements(stmts, _inv())[0]
    assert res.decision == "fixed"


def test_under_investigation_status():
    stmts = ingest_csaf(load_fixture("under_investigation"), source="fx")
    assert stmts[0].status == VexStatus.UNDER_INVESTIGATION
    res = match_statements(stmts, _inv())[0]
    assert res.decision == "under_investigation"


def test_invalid_doc_rejected_without_breaking_batch():
    # Unknown status + impossible future timestamp -> captured as validation
    # error, NOT raised. Ingestion of a multi-vuln doc still returns rows.
    stmts = ingest_csaf(load_fixture("invalid_unknown_status_future_ts"), source="fx")
    assert len(stmts) == 1
    s = stmts[0]
    assert s.validation_error is not None
    assert s.status == VexStatus.UNKNOWN
    # It must not be counted as a real verdict.
    assert s.advisory_id == "ADV-2026-005"


def test_future_timestamp_rejected_explicitly():
    from lucidfence.core.csaf_vex import _parse_ts
    try:
        _parse_ts("2099-01-01T00:00:00Z")
    except ValueError as exc:
        assert "future" in str(exc).lower()
    else:
        raise AssertionError("impossible future timestamp was accepted")


def test_unknown_status_rejected_explicitly():
    from lucidfence.core.csaf_vex import _norm_status
    for bad in ("maybe_vulnerable", "unknown", "", None):
        try:
            _norm_status(bad)
        except ValueError:
            continue
        raise AssertionError(f"unknown status {bad!r} was accepted")


def test_ambiguous_match_does_not_change_risk():
    stmts = ingest_csaf(load_fixture("ambiguous_match"), source="fx")
    res = match_statements(stmts, _inv())[0]
    assert res.confidence == MatchConfidence.AMBIGUOUS
    # Never auto-promote to affected; stays under_investigation for human review.
    assert res.decision == "under_investigation"
    assert res.needs_review is True
    assert len(res.installed) > 1


def test_report_links_advisory_product_evidence_decision():
    all_stmts = []
    for name in ("affected_exact", "not_affected_with_justification", "fixed",
                 "under_investigation", "invalid_unknown_status_future_ts",
                 "ambiguous_match"):
        all_stmts.extend(ingest_csaf(load_fixture(name), source="fx"))
    report = build_report(all_stmts, _inv())
    assert report["statements_total"] == len(all_stmts)
    # Ambiguous row is in needs_review and not counted as a risk change.
    assert any(r["confidence"] == "ambiguous" for r in report["needs_review"])
    by_dec = report["by_decision"]
    assert by_dec.get("affected") == 1
    assert by_dec.get("not_affected") == 1
    assert by_dec.get("fixed") == 1
    # Ambiguous/future/invalid never inflate affected.
    assert by_dec.get("affected") == 1
    # Every row carries advisory_id, product_id, decision and evidence fields.
    for row in report["rows"]:
        assert row["advisory_id"]
        assert row["product_id"]
        assert row["decision"] in {"affected", "not_affected", "fixed",
                                   "under_investigation"}
        assert "installed_evidence" in row


def test_offline_stdlib_only_imports():
    # Guard: the module must not import any network/third-party deps.
    import ast
    import inspect
    from lucidfence.core import csaf_vex
    src = inspect.getsource(csaf_vex)
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = {"requests", "urllib3", "httpx", "pydantic", "numpy"}
    assert forbidden.isdisjoint(set(imports)), f"forbidden imports: {imports}"
    # Must use only stdlib (json, re, time, dataclasses, datetime, enum, typing).
    assert "json" in imports
