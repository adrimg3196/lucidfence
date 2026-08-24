# Autonomy B Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap a deterministic, fail-closed autonomy-B evidence plane with an official GitHub attestation and no product changes.

**Architecture:** A pinned catalog and a stdlib verifier form the offline trust root. A tokenless `pull_request` workflow uses anonymously fetched base-sourced code to observe candidate runtime behavior externally over loopback HTTP without OIDC or repository permissions. A separate trusted `workflow_run` definition loaded from `main` never checks out or executes the candidate; it validates exact producer/conventional-CI runs and bounded receipts, assembles a SHA-bound manifest in a candidate-free signer job, creates and verifies an official GitHub attestation, and posts the required status on the exact PR head. A main-only guard can invalidate stale or newly conflicting successes but can never publish success.

**Tech Stack:** Python 3.11 stdlib, JSON/JSONL, GitHub Actions, `actions/attest`, GitHub CLI bundle/trusted-root offline attestation verification.

**Spec:** `docs/superpowers/specs/2026-08-23-autonomy-b-control-plane-design.md`

## Global Constraints

- Repository is exactly `adrimg3196/lucidfence`; source pin is exactly `msitarzewski/agency-agents@ebe9c99acb5c96f9468de368d8bead775387d1a7`.
- License is MIT; profile count is 270; division count is 17; catalog schema is `lucidfence-agency-catalog/v1`.
- No product, roadmap, release, deployment, tenant-data, secret, bypass, force-push, or unrelated issue remediation.
- Maker, final reviewer, and both high-risk AppSec reviewers obey the independence rules.
- All new third-party Actions references use immutable commit SHAs.
- Candidate-controlled code never receives OIDC, explicit repository credentials, or repository write permissions; only the trusted signer loaded from `main` can attest or publish the required status.
- Producer verdicts are never accepted directly. Bounded receipts are treated only as data, revalidated by fixed `main` jobs, normalized on fresh runners, and signed only from a job that never checks out candidate bytes.
- Once bootstrapped, trusted AppSec rejects every canonical control-plane mutation; changing the future verifier requires a separately authorized bootstrap rather than an ordinary autonomous PR.
- There is no PR-head signing fallback, synthetic attestation receipt, administrative bypass, or temporary ruleset weakening for the circular bootstrap.
- Agents make routine technical and prioritization decisions autonomously within scope. Executive dailies escalate only a material ambiguity, an unresolved safe-operation stopper, or an action outside standing authorization.

---

### Task 1: Deterministic pinned catalog

**Files:**
- Create: `scripts/generate_agency_catalog.py`
- Create: `tests/test_agency_catalog.py`
- Create: `config/agency-agents.lock.json`
- Create: `data/agency_catalog.json`

**Interfaces:**
- Produces `build_documents(source: Path) -> tuple[dict, dict]` and `verify_repository(root: Path) -> list[str]`.
- CLI `--source PATH --write` generates canonical JSON; `--verify` validates committed documents offline.

- [x] Write tests for exact pin/license/count/divisions, deterministic output, embedded-lock equality, and every path/hash.
- [x] Run `python3 tests/test_agency_catalog.py` and observe failure because the generator does not exist.
- [x] Implement the minimal generator/verifier and generate both documents from the detached pinned checkout.
- [x] Run the catalog tests and both CLI modes to green.

### Task 2: Durable manifest verifier

**Files:**
- Create: `scripts/verify_autonomy_evidence.py`
- Create: `config/night-shift-manifest.schema.json`
- Create: `tests/test_autonomy_evidence.py`
- Create: `data/night_shift/runs/README.md`
- Create: `data/night_shift/trends.jsonl`

**Interfaces:**
- Produces `canonical_bytes`, `canonical_document`, `seal_manifest`, and `verify_manifest` for deterministic policy validation.
- The CLI accepts expected repository/base/head/run/workflow/ref plus the official bundle and an independently obtained trusted root; it invokes GitHub CLI itself and never accepts a caller-authored verification receipt.
- `scripts/verify.py` walks exact versioned bundles committed under `data/night_shift/runs/`, invokes cryptographic offline attestation verification, and rejects unknown, missing, altered, or expired durable evidence.

- [x] Write the valid-fixture test and each required negative test with literal expected failures.
- [x] Run the focused test file and observe missing-module failure.
- [x] Implement canonical hashing, full committed-schema enforcement, identity, freshness, independence, overlap, secret, artifact, and attestation-binding validation.
- [x] Run focused tests to green and mutation-check every validation branch.

### Task 3: Unprivileged evidence producer

**Files:**
- Create: `scripts/emit_autonomy_evidence.py`
- Create: `.github/workflows/autonomy-evidence.yml`
- Create: `.github/CODEOWNERS`
- Modify: `scripts/verify.py`
- Create: `tests/test_autonomy_evidence_producer.py`

**Interfaces:**
- Evidence CLI derives context from GitHub environment variables, the live GitHub API, and git state, never workflow inputs.
- The `pull_request` workflow has `permissions: {}`, anonymously fetches the exact base and PR head from the public repository, emits independent evidence artifacts, and never receives a GitHub token, OIDC, or status-write authority.

- [x] Add behavioral tests for context derivation, empty workflow permissions, absence of tokens/OIDC/write authority, immutable action pins, independent artifacts, and `verify.py` integration.
- [x] Run focused tests and observe the missing producer/workflow failures.
- [x] Implement evidence emission and the unprivileged high-risk preflight DAG.
- [x] Run `python3 scripts/verify.py --docs-only`, workflow lint, and focused tests to green.

### Task 4: Trusted signer and official Actions attestation

**Files:**
- Create: `.github/workflows/autonomy-attest.yml`
- Create: `.github/workflows/autonomy-guard.yml`
- Modify: `.github/workflows/ci.yml`
- Create: `config/autonomy-tools.lock`
- Modify: `scripts/emit_autonomy_evidence.py`
- Modify: `scripts/verify_autonomy_evidence.py`
- Modify: `config/night-shift-manifest.schema.json`
- Modify: `tests/test_autonomy_evidence.py`
- Modify: `tests/test_autonomy_evidence_producer.py`

**Interfaces:**
- The trusted workflow runs only as `workflow_run`, with its definition and verifier checked out from `main`.
- Every action used by the producer, signer, and conventional CI evidence source is pinned to one verified immutable commit without changing the established CI job names.
- It resolves one live open PR and exact producer run, rejects a stale run/PR SHA snapshot, and derives changed paths from GitHub.
- The unprivileged producer validates the candidate lock with exact-base code. `runtime` and `reality` are external loopback observations by that base-sourced parent, which never imports candidate modules and owns all verdict/receipt bytes. Candidate stdout, exit codes and control channels are not evidence. Trusted `workflow_run` jobs never check out or execute candidate bytes: `ci` validates an exact successful conventional GitHub Actions run and complete job inventory, changed producer/CI workflows fail closed, and bounded producer receipts are normalized only as data. Fresh main-only jobs obtain live overlap evidence.
- Trusted Python tools are installed wheel-only from `config/autonomy-tools.lock` with exact SHA-256 hashes and then installed offline in a disposable environment. Candidate runtime dependencies pass the same wheel-only download/offline-install boundary.
- The overlap receipt binds the live open-PR metadata/path snapshot; PR metadata edits re-run evidence, and the autonomous merge actor repeats `/goal` immediately before merge to close the dynamic cross-PR boundary.
- A main-only `pull_request_target`/`workflow_run` plus hourly guard immediately invalidates changing heads and re-evaluates live overlap and evidence age for every open PR. It has failure-only status authority and cannot manufacture success.
- A separate signer job with no candidate checkout emits `final-review`, seals and pre-verifies the manifest, invokes the pinned official `actions/attest`, retains the raw `gh attestation verify --format json` result, re-verifies every binding, and publishes the exact `autonomy-evidence` status on the candidate head.

- [x] Add negative tests for privilege separation, trigger identity, stale/live SHA mismatch, signer workflow/ref/run/digest mismatch, malformed GitHub verification JSON, and bounded inventories.
- [x] Run focused tests and observe failures before implementing each trusted boundary.
- [x] Implement trusted derivation, conventional-CI run validation, black-box runtime observation, job-API receipt normalization, the candidate-free signer, official attestation, cryptographic bundle/trusted-root offline verification, raw verification receipt retention, complete binding verification, and success/failure commit-status publication.
- [x] Verify action pins against current official documentation; run workflow lint, shell lint, focused tests, and `git diff --check`.

### Task 5: Repository and GitHub verification

**Files:** all files above only.

- [x] Run `python3 tests/run_tests.py`, `python3 scripts/runtime_validation.py`, and `python3 scripts/verify.py` in a sanitized copy; record baseline-equivalent environment-only failures explicitly and rely on GitHub-hosted CI for authoritative execution.
- [ ] Commit once on the isolated bootstrap branch and publish through the GitHub connector.
- [ ] Open one bootstrap PR linked to #234 and document both the exceptional circular-bootstrap authorization and the fact that it is governance evidence, not an official attestation.
- [ ] Resolve all failures and review conversations without bypassing controls.
- [ ] Confirm through the effective imported ruleset whether the initial bootstrap may merge under the explicit one-time authorization. If an official attestation is required before that first merge, stop as blocked; do not introduce a PR-head/OIDC fallback or weaken the ruleset.
- [ ] If and only if the authorized bootstrap merge completes without a failed control, verify fresh `main`, the trusted signer definition, and effective protection through GitHub.
- [ ] Create the non-functional canary PR and demonstrate that incomplete evidence is rejected and complete evidence with an official attestation is accepted. Do not merge the canary unless every gate passes and its change is worth retaining.
- [ ] Produce executive daily/handoff language: outcome, risk, confidence, next action, and at most one concise question for a material ambiguity, unresolved stopper, or out-of-authorization action.
