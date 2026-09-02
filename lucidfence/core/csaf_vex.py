"""Local, offline ingestion of CSAF 2.0 advisories and VEX statements.

Issue #246 -- "Ingesta local de CSAF/VEX y aplicabilidad a software instalado".

Design contract (from the issue):
  * Ingest CSAF 2.0 documents and VEX statements from LOCAL files only. No
    mandatory cloud feed download. Stdlib-first, works fully offline.
  * Validate a minimal schema: product identity (purl / CPE / product id),
    VEX status, timestamps and hashes. Reject malformed docs without crashing
    the whole batch.
  * Relate purl/CPE/product ids to an inventory of INSTALLED software using
    EXPLICIT confidence (exact match, fuzzy match, no match). We never
    silently assume a CVE applies.
  * Keep justification and source. "affected", "not_affected", "fixed" and
    "under_investigation" are DISTINCT states.
  * An ambiguous match does NOT change risk: it is surfaced for human review
    and left at under_investigation rather than flipping the posture.
  * Reject impossible future timestamps and unknown VEX statuses without
    breaking compatibility with otherwise-valid documents.
  * The report links advisory -> product -> installed evidence -> decision.

This module is pure deterministic Python (stdlib only). It is the *ingester
and matcher*; it never acts on a device. The decision output is a structured
report a human (or the Coordinador / merge train) reviews.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# A timestamp more than this far in the future is impossible (clock skew guard).
MAX_FUTURE_SKEW_SECONDS = 31 * 24 * 3600  # ~1 month

# VEX statuses from the CSAF VEX profile / CISA minimum VEX.
class VexStatus(str, Enum):
    AFFECTED = "affected"
    NOT_AFFECTED = "not_affected"
    FIXED = "fixed"
    UNDER_INVESTIGATION = "under_investigation"
    UNKNOWN = "unknown"


# How strongly a VEX/SAF entry maps onto an installed package.
class MatchConfidence(str, Enum):
    EXACT = "exact"          # purl/CPE matched a real installed package
    FUZZY = "fuzzy"          # name matched but version/qualifiers uncertain
    NONE = "none"            # no installed package corresponds
    AMBIGUOUS = "ambiguous"  # matched more than one installed package -> human review


_UNKNOWN_STATUSES = {"unknown", "n/a", "na", "", None}


def _norm_status(raw: Any) -> VexStatus:
    """Normalize a raw status string to a VexStatus.

    Unknown or unrecognized statuses are rejected (caller turns them into a
    validation error) rather than silently coerced.
    """
    if raw is None:
        raise ValueError("missing VEX status")
    if not isinstance(raw, str):
        raise ValueError(f"VEX status must be a string, got {type(raw).__name__}")
    s = raw.strip().lower()
    if s in _UNKNOWN_STATUSES:
        raise ValueError(f"unknown/empty VEX status: {raw!r}")
    mapping = {
        "affected": VexStatus.AFFECTED,
        "vulnerable": VexStatus.AFFECTED,
        "not_affected": VexStatus.NOT_AFFECTED,
        "notaffected": VexStatus.NOT_AFFECTED,
        "not_affected__under_review": VexStatus.NOT_AFFECTED,
        "fixed": VexStatus.FIXED,
        "resolved": VexStatus.FIXED,
        "under_investigation": VexStatus.UNDER_INVESTIGATION,
        "under_investigation_": VexStatus.UNDER_INVESTIGATION,
    }
    if s not in mapping:
        raise ValueError(f"unrecognized VEX status: {raw!r}")
    return mapping[s]


def _parse_ts(raw: Any) -> datetime:
    """Parse an ISO-8601 timestamp; reject impossible-future dates.

    Raises ValueError on malformed or future-impossible input.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"missing/invalid timestamp: {raw!r}")
    s = raw.strip()
    # Accept trailing Z (UTC designator) and fractional seconds.
    iso = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        # Fall back to a tolerant parse for a few common layouts.
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unparseable timestamp: {raw!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if dt > now and (dt - now).total_seconds() > MAX_FUTURE_SKEW_SECONDS:
        raise ValueError(f"timestamp is impossibly in the future: {raw!r}")
    return dt


def _norm_purl(raw: Any) -> Optional[str]:
    """Normalize a purl to lowercase, no leading/trailing whitespace.

    Returns None when not a usable purl.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().lower()
    # A purl must look like pkg:type/name...
    if not s.startswith("pkg:"):
        return None
    return s


_CPE_RE = re.compile(r"^cpe:2\.3:[aoh]:[^:]+:[^:]+:", re.IGNORECASE)


def _norm_cpe(raw: Any) -> Optional[str]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    if not _CPE_RE.match(s):
        return None
    return s.lower()


def _product_ids(vuln: dict) -> list[dict]:
    """Extract candidate product identifiers from a CSAF vulnerability entry.

    Returns a list of {"purl", "cpe", "product_id"} dicts (each key optional).
    """
    out: list[dict] = []
    # CSAF: vulnerability/product_status references product_ids defined in
    # /product_tree/full_product_names; the actual identifiers live there.
    for pid in vuln.get("product_ids") or []:
        if isinstance(pid, str):
            out.append({"product_id": pid})
    # Some docs embed purl/cpe directly under the vulnerability.
    for key, norm in (("purl", _norm_purl), ("cpe", _norm_cpe)):
        val = vuln.get(key)
        if isinstance(val, str):
            n = norm(val)
            if n:
                out.append({key: n})
    return out


@dataclass
class InstalledPackage:
    """One installed package in the local inventory.

    At minimum a `name`; optionally a `version`, `purl` or `cpe` so we can match
    against advisories with explicit confidence.
    """

    name: str
    version: Optional[str] = None
    purl: Optional[str] = None
    cpe: Optional[str] = None
    evidence_source: str = "installed_inventory"

    def pk(self) -> str:
        return (self.purl or self.cpe or f"{self.name}@{self.version or '?'}").lower()


@dataclass
class VexStatement:
    """One parsed VEX/CSAF statement, unknown-safe and validated."""

    advisory_id: str
    product_id: str
    purl: Optional[str]
    cpe: Optional[str]
    status: VexStatus
    justification: Optional[str]
    action_statement: Optional[str]
    source: str           # which file/fixture produced this
    timestamp: Optional[datetime]
    # SHA-256 of the source document, when present (evidence integrity).
    doc_sha256: Optional[str] = None
    # Set when this statement could not be fully validated (kept for review).
    validation_error: Optional[str] = None

    def as_dict(self) -> dict:
        d = {
            "advisory_id": self.advisory_id,
            "product_id": self.product_id,
            "purl": self.purl,
            "cpe": self.cpe,
            "status": self.status.value,
            "justification": self.justification,
            "action_statement": self.action_statement,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "doc_sha256": self.doc_sha256,
        }
        if self.validation_error:
            d["validation_error"] = self.validation_error
        return d


@dataclass
class MatchResult:
    statement: VexStatement
    confidence: MatchConfidence
    installed: list[InstalledPackage] = field(default_factory=list)
    # When confidence is AMBIGUOUS or FUZZY, the human must confirm before the
    # risk posture changes. We never auto-promote these to affected/not_affected.
    needs_review: bool = False
    decision: str = "under_investigation"


def _match_statement(stmt: VexStatement, inventory: list[InstalledPackage]) -> MatchResult:
    """Relate one VEX statement to installed software with explicit confidence.

    Rules:
      * exact purl/cpe match -> EXACT
      * name-only match (fuzzy) -> FUZZY (needs review)
      * no match -> NONE
      * more than one ambiguous candidate -> AMBIGUOUS (needs review)
    An ambiguous or fuzzy match never flips the risk: decision stays
    under_investigation until a human confirms.
    """
    candidates: list[InstalledPackage] = []
    if stmt.purl:
        candidates = [p for p in inventory if p.purl and p.purl == stmt.purl]
    elif stmt.cpe:
        candidates = [p for p in inventory if p.cpe and p.cpe == stmt.cpe]

    if not candidates:
        # Try a name-based fuzzy match against product_id / purl tail.
        name = None
        if stmt.purl:
            name = stmt.purl.split("/")[-1].split("@")[0]
        elif stmt.product_id:
            name = stmt.product_id.split(":")[-1].split("/")[-1].lower()
        if name:
            fuzzy = [p for p in inventory if p.name and p.name.lower() == name]
            if len(fuzzy) > 1:
                return MatchResult(stmt, MatchConfidence.AMBIGUOUS, fuzzy, needs_review=True)
            if len(fuzzy) == 1:
                return MatchResult(stmt, MatchConfidence.FUZZY, fuzzy, needs_review=True)
        return MatchResult(stmt, MatchConfidence.NONE, [])

    if len(candidates) > 1:
        return MatchResult(stmt, MatchConfidence.AMBIGUOUS, candidates, needs_review=True)

    conf = MatchConfidence.EXACT
    # A fuzzy match (name from product_id, no purl/cpe) that hit exactly once.
    if not (stmt.purl or stmt.cpe) and candidates:
        conf = MatchConfidence.FUZZY
    needs_review = conf in (MatchConfidence.FUZZY, MatchConfidence.AMBIGUOUS)
    decision = _decide(stmt, conf)
    return MatchResult(stmt, conf, candidates, needs_review=needs_review, decision=decision)


def _decide(stmt: VexStatement, conf: MatchConfidence) -> str:
    """Map a matched statement to a decision, never silently downgrading risk."""
    if conf in (MatchConfidence.NONE, MatchConfidence.AMBIGUOUS):
        return "under_investigation"
    if conf == MatchConfidence.FUZZY:
        # We have a likely package but version/qualifiers are uncertain: hold.
        return "under_investigation"
    # EXACT match: trust the VEX status, but keep it human-readable.
    return {
        VexStatus.AFFECTED: "affected",
        VexStatus.NOT_AFFECTED: "not_affected",
        VexStatus.FIXED: "fixed",
        VexStatus.UNDER_INVESTIGATION: "under_investigation",
        VexStatus.UNKNOWN: "under_investigation",
    }[stmt.status]


def _extract_sha(doc: dict) -> Optional[str]:
    agg = doc.get("aggregate_severity") or doc.get("sha256") or doc.get("hash")
    if isinstance(agg, str) and re.fullmatch(r"[0-9a-fA-F]{64}", agg):
        return agg.lower()
    return None


def ingest_csaf(doc: dict, source: str = "csaf") -> list[VexStatement]:
    """Parse one CSAF/VEX document into validated statements.

    Malformed sub-entries are captured with `validation_error` instead of
    raising, so a single bad vulnerability does not abort the whole advisory.
    """
    out: list[VexStatement] = []
    if not isinstance(doc, dict):
        raise ValueError("CSAF document must be a JSON object")
    advisory_id = (
        doc.get("document", {}).get("tracking", {}).get("id")
        or doc.get("id")
        or source
    )
    doc_sha = _extract_sha(doc)
    vulns = doc.get("vulnerabilities") or []
    if not isinstance(vulns, list):
        raise ValueError("CSAF 'vulnerabilities' must be a list")
    for v in vulns:
        if not isinstance(v, dict):
            out.append(VexStatement(
                advisory_id=advisory_id, product_id="?", purl=None, cpe=None,
                status=VexStatus.UNKNOWN, justification=None, action_statement=None,
                source=source, timestamp=None, doc_sha256=doc_sha,
                validation_error="vulnerability entry is not an object",
            ))
            continue
        pid = (v.get("product_id") or (v.get("product_ids") or [None])[0] or "?")
        purl = _norm_purl(v.get("purl"))
        cpe = _norm_cpe(v.get("cpe"))
        # product_status style: 'affected' lists product_ids
        ps = v.get("product_status") or {}
        try:
            status = _norm_status(v.get("status") or ps.get("status"))
        except ValueError as exc:
            out.append(VexStatement(
                advisory_id=advisory_id, product_id=str(pid), purl=purl, cpe=cpe,
                status=VexStatus.UNKNOWN, justification=None,
                action_statement=None, source=source, timestamp=None,
                doc_sha256=doc_sha, validation_error=str(exc),
            ))
            continue
        ts = None
        try:
            if v.get("timestamp"):
                ts = _parse_ts(v["timestamp"])
        except ValueError as exc:
            out.append(VexStatement(
                advisory_id=advisory_id, product_id=str(pid), purl=purl, cpe=cpe,
                status=VexStatus.UNKNOWN, justification=None,
                action_statement=None, source=source, timestamp=None,
                doc_sha256=doc_sha, validation_error=str(exc),
            ))
            continue
        just = v.get("justification")
        if just is None and isinstance(v.get("scores"), list):
            just = (v["scores"] or [{}])[0].get("justify")
        action = v.get("action_statement")
        if action is None and isinstance(v.get("remediations"), list):
            action = (v["remediations"] or [{}])[0].get("category")
        out.append(VexStatement(
            advisory_id=advisory_id, product_id=str(pid), purl=purl, cpe=cpe,
            status=status, justification=just, action_statement=action,
            source=source, timestamp=ts, doc_sha256=doc_sha,
        ))
    return out


def ingest_file(path: str) -> list[VexStatement]:
    """Ingest a single local CSAF/VEX file. Raises on unreadable/invalid JSON."""
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    return ingest_csaf(doc, source=path)


def match_statements(
    statements: list[VexStatement], inventory: list[InstalledPackage]
) -> list[MatchResult]:
    """Match every statement to the installed inventory with explicit confidence."""
    return [_match_statement(s, inventory) for s in statements]


def build_report(
    statements: list[VexStatement],
    inventory: list[InstalledPackage],
) -> dict:
    """Build the report: advisory -> product -> installed evidence -> decision.

    Ambiguous/fuzzy matches are surfaced under `needs_review` and never counted
    as a risk change.
    """
    matches = match_statements(statements, inventory)
    by_decision: dict[str, int] = {}
    review: list[dict] = []
    rows: list[dict] = []
    for m in matches:
        by_decision[m.decision] = by_decision.get(m.decision, 0) + 1
        if m.needs_review:
            review.append({
                "advisory_id": m.statement.advisory_id,
                "product_id": m.statement.product_id,
                "status": m.statement.status.value,
                "confidence": m.confidence.value,
                "installed": [p.pk() for p in m.installed],
            })
        rows.append({
            "advisory_id": m.statement.advisory_id,
            "product_id": m.statement.product_id,
            "status": m.statement.status.value,
            "confidence": m.confidence.value,
            "decision": m.decision,
            "installed_evidence": [p.pk() for p in m.installed],
            "justification": m.statement.justification,
            "source": m.statement.source,
            "timestamp": m.statement.timestamp.isoformat() if m.statement.timestamp else None,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "statements_total": len(statements),
        "by_decision": by_decision,
        "needs_review": review,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Fixtures -- explicit, documented-signal-only local advisories.
# ---------------------------------------------------------------------------

FIXTURES: dict[str, dict] = {
    # A real affected component, matched exactly to an installed package.
    "affected_exact": {
        "document": {"tracking": {"id": "ADV-2026-001"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1001",
                "status": "affected",
                "purl": "pkg:deb/ubuntu/openssl@3.0.2-1",
                "timestamp": "2026-08-01T00:00:00Z",
                "justification": "Confirmed vulnerable version range",
            }
        ],
    },
    # A component explicitly NOT affected, with a justification preserved.
    "not_affected_with_justification": {
        "document": {"tracking": {"id": "ADV-2026-002"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1002",
                "status": "not_affected",
                "purl": "pkg:generic/log4j@2.17.1",
                "timestamp": "2026-08-02T00:00:00Z",
                "justification": "Version 2.17.1 includes the fix for CVE-2021-44228",
            }
        ],
    },
    # A fixed component.
    "fixed": {
        "document": {"tracking": {"id": "ADV-2026-003"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1003",
                "status": "fixed",
                "purl": "pkg:npm/left-pad@1.3.0",
                "timestamp": "2026-08-03T00:00:00Z",
            }
        ],
    },
    # Still under investigation.
    "under_investigation": {
        "document": {"tracking": {"id": "ADV-2026-004"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1004",
                "status": "under_investigation",
                "purl": "pkg:generic/curl@8.0.0",
                "timestamp": "2026-08-04T00:00:00Z",
            }
        ],
    },
    # A malformed document: unknown status + impossible future timestamp. Must be
    # captured as a validation error, not crash ingestion.
    "invalid_unknown_status_future_ts": {
        "document": {"tracking": {"id": "ADV-2026-005"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1005",
                "status": "maybe_vulnerable",  # unknown status -> rejected
                "purl": "pkg:generic/bad@1.0",
                "timestamp": "2099-01-01T00:00:00Z",  # impossible future -> rejected
            }
        ],
    },
    # Ambiguous: matches more than one installed package -> needs human review,
    # decision stays under_investigation (never silently flips risk).
    "ambiguous_match": {
        "document": {"tracking": {"id": "ADV-2026-006"}},
        "vulnerabilities": [
            {
                "cve": "CVE-2026-1006",
                "status": "affected",
                "purl": "pkg:generic/shared-lib@2.0",
                "timestamp": "2026-08-05T00:00:00Z",
            }
        ],
    },
}


def load_fixture(name: str) -> dict:
    if name not in FIXTURES:
        raise KeyError(f"unknown csaf_vex fixture: {name}")
    return FIXTURES[name]
