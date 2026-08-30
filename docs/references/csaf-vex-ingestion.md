# CSAF / VEX local ingestion (`lucidfence.core.csaf_vex`)

Issue #246 — "Ingesta local de CSAF/VEX y aplicabilidad a software instalado".

## What it does
Ingests **CSAF 2.0** advisories and **VEX** statements from **local files only**
(no mandatory cloud feed), validates a minimal schema, and relates
`purl`/`CPE`/`product_id` to an inventory of installed software with **explicit
confidence**. It never acts on a device — it produces a structured report a
human (or the merge train) reviews.

## Why it exists
A CVE associated with a product does **not** prove the concrete component on a
fleet endpoint is affected. Without VEX/CSAF we build noisy remediation queues.
This module turns "there is a CVE" into "this exact installed package is
affected / not affected / fixed / under investigation", with justification.

## Design contract (acceptance criteria)
- **Read-only, offline, stdlib-first.** No network at ingest time. `json`, `re`,
  `time`, `datetime`, `dataclasses`, `enum`, `typing` only.
- **Validated schema.** Product identity (purl/CPE/product id), VEX status,
  timestamps and hashes. Malformed sub-entries are captured with
  `validation_error` instead of aborting the whole advisory.
- **Distinct VEX states.** `affected`, `not_affected`, `fixed`,
  `under_investigation` are never collapsed. `not_affected` keeps its
  `justification`.
- **Explicit applicability confidence.** `EXACT` (purl/CPE match), `FUZZY`
  (name-only, uncertain version), `NONE` (no installed package),
  `AMBIGUOUS` (>1 candidate). Ambiguous/fuzzy matches are surfaced under
  `needs_review` and **never flip the risk posture** — decision stays
  `under_investigation` until a human confirms.
- **Rejects impossible input gracefully.** Timestamps more than ~1 month in the
  future and unknown VEX statuses raise `ValueError` per-entry (captured, not
  fatal).
- **Traceable report.** `build_report()` links advisory → product → installed
  evidence → decision, with `source` and `timestamp` on every row.

## Usage
```python
from lucidfence.core.csaf_vex import ingest_file, build_report, InstalledPackage

statements = ingest_file("data/advisories/adv-2026-001.csaf.json")
inventory = [InstalledPackage(name="openssl", version="3.0.2-1",
                              purl="pkg:deb/ubuntu/openssl@3.0.2-1")]
report = build_report(statements, inventory)
```

## Caveats
- This is the **ingester and matcher**, not an enforcement point. The decision
  output feeds human review; do NOT auto-remediate from `affected` rows.
- `FUZZY`/`AMBIGUOUS` matches MUST be confirmed by a human before any posture
  change. The module deliberately refuses to decide for them.
