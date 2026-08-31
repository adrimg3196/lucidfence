# Constitution — LucidFence

The Constitution defines the non-negotiable principles of the LucidFence project. Every technical decision, architectural choice, and operational practice must be consistent with these principles. When in doubt, the Constitution wins.

## Article I: Local-first, zero cloud dependency

**Principle:** LucidFence runs entirely on the client's infrastructure. No data leaves the machine unless the operator explicitly configures it to do so.

**Implications:**
- All device data, credentials, and policies reside on the operator's machine
- The cloud state (`data/cloud_state.json`) is demo/public data only, never real tenant data
- There is no "LucidFence cloud" that stores or processes user data
- Offline operation is a first-class use case

**Rationale:** This is a core differentiator vs. cloud-only MDM/UEM solutions. It enables air-gapped deployments, regulatory compliance, and operator sovereignty.

---

## Article II: $0 — free as a requirement, not a feature

**Principle:** LucidFence must remain usable at zero cost. Any dependency that introduces a mandatory paid tier is rejected.

**Implications:**
- No API calls to paid services as a hard requirement
- No vendor lock-in to paid plans
- All adapters must work with free tier or self-hosted alternatives
- The `loop_free_guard` test enforces this in CI

**Guardrails:**
- If a feature requires a paid dependency, it must be optional and degrade gracefully
- Documentation must be clear about what is free and what requires payment
- The project does not accept sponsorships that compromise this principle

---

## Article III: Open source, Apache 2.0

**Principle:** All code, documentation, and artifacts are open source under Apache 2.0.

**Implications:**
- No proprietary blobs, no closed-source plugins
- No patents or trade secrets that restrict use
- Contributions must be compatible with Apache 2.0
- Forks and derivatives are encouraged

**Edge cases:**
- Adapter credentials are user-provided and never stored in the repo
- Configuration examples may contain placeholders; real secrets never appear in docs

---

## Article IV: Stdlib-first, dependency-minimized

**Principle:** Prefer Python stdlib over third-party packages. Add dependencies only when there is a clear, justified need.

**Implications:**
- The `verify.py` gate enforces stdlib-only operation
- Each new dependency must be justified in the PR description
- Dependencies are pinned to specific versions in `pyproject.toml`
- The project targets Python 3.11+ (stdlib `tomllib`), but provides fallback for 3.9 via `tomli`

**Justification threshold for new dependencies:**
- Does the stdlib do this? If yes, use stdlib
- Is this a security/correctness requirement that stdlib can't meet? If yes, add dependency
- Is this convenience? If yes, don't add

---

## Article V: Honest verification, no false greens

**Principle:** The test suite and verification gate must be honest. A passing test suite that misses real bugs is worse than a failing one.

**Implications:**
- `tests/run_tests.py` is the honest runner; it must not hide failures
- The `verify.py` gate runs 4 checks: version consistency, doc links, runtime battery, and test suite
- Known flaky tests (e.g., OIDC baseline) are documented and isolated
- False positives in risk evaluation (`risk: fallo de evaluación en silencio`) are P0 bugs

**What this forbids:**
- Skipping tests without explanation
- Mocking away the very behavior being tested
- Green CI with known undiagnosed failures

---

## Article VI: Multi-UEM, not single-vendor

**Principle:** LucidFence is designed for heterogeneous fleets. A single-UEM deployment is a special case, not the target.

**Implications:**
- The `multiuem.py` domain provides normalized device representation across UEM sources
- Adapters abstract UEM-specific APIs behind a common contract
- Policies and geofencing work across provider boundaries
- The orchestrator merges identity signals from multiple sources

**Why this matters:**
- Real fleets are mixed: iPhones via Jamf, laptops via Intune, IoT via Fleet
- A single-UEM solution forces the operator to choose one vendor
- Multi-UEM is harder to build but dramatically more valuable

---

## Article VII: Autonomous operation, human-gated only for outreach

**Principle:** The project operates as an autonomous software company. Humans intervene only for business decisions (outreach, partnerships) and emergency escalation.

**Implications:**
- The 9 loops defined in `docs/internal/LOOP.md` run on their own schedules
- The loop-run-log (`docs/internal/loop-run-log.md`) is append-only evidence of activity
- Agent identity is consistent (Hermes commits as `Hermes CTO <hermes@lucidfence.local>`)
- The owner (Adri) receives the weekly Dirección digest and approves outreach only

**What this does NOT mean:**
- Humans can't review or override agent work (they can, but the goal is autonomy)
- Every decision needs human approval (most don't)
- Agents are infallible (they're not; they self-correct and log failures)

---

## Article VIII: Security is not optional

**Principle:** Security is a built-in property, not a feature toggle. The system is designed to minimize the blast radius of any single compromise.

**Implications:**
- Credentials are isolated per-tenant
- Thedenylist in `loop-constraints.md` forbids secret commits
- The threat model (`docs/architecture/THREAT_MODEL.md`) is maintained and reviewed
- CVE feeds are ingested and evaluated (not just collected)
- Declarative governance (`docs/internal/loop-constraints.md`) blocks dangerous patterns

**Security practices:**
- Secrets never in code, config, or docs
- Credential transport over encrypted channels only
- Audit log is append-only and integrity-protected
- RBAC enforced at API and UI layers

---

## Amendments

The Constitution can be amended by:

1. A PR that modifies this document
2. Approval by the owner (Adri) via merge
3. Publication in the loop-run-log as a constitutional event

Amendments require a clear rationale. Changes that weaken a principle require a higher bar of justification than changes that strengthen one.

---

*Last amended: 2026-01-15. Ratified by Adri on 2026-01-15.*
