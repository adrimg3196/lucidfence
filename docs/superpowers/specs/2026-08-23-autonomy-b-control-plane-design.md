# Autonomy B control-plane bootstrap design

## Scope

This bootstrap establishes evidence and governance controls only. It does not
change LucidFence product behavior, release artifacts, deployment, marketing,
or the archived roadmap, and it does not remediate findings from #250, #261,
#262, or #263.

## Trust model

The repository pins `msitarzewski/agency-agents` at commit
`ebe9c99acb5c96f9468de368d8bead775387d1a7`. A deterministic lock records the
MIT license digest, all 270 Markdown profile paths and SHA-256 digests, and the
17 canonical divisions. `data/agency_catalog.json` embeds that exact lock.
Offline validation rejects any drift in the pin, license, counts, divisions,
paths, hashes, ordering, or embedded lock.

Night-shift evidence uses schema `lucidfence-night-shift-manifest/v1`. Every
manifest binds repository, base and head commit, workflow/ref, run ID and
attempt, objective, canonical participants, evidence producers, artifact
digests, generation time, expiry, and a deterministic digest of the manifest
itself. The digest is calculated over canonical JSON with the digest value
replaced by 64 zeroes, avoiding an impossible self-referential hash.

## Evidence flow

The evidence plane deliberately separates untrusted feedback, trusted
derivation, normalization, and signing:

1. `.github/workflows/autonomy-evidence.yml` runs on `pull_request`. It derives
   evidence without caller-supplied hashes, verdicts, or text. The workflow has
   `permissions: {}` and receives no GitHub token: exact base/head commits and
   the pinned public catalog source are fetched anonymously into separate
   directories. It has neither OIDC nor repository permissions. Its
   independent jobs provide early feedback. Ordinary
   preflight verdicts cannot become signed evidence directly; the only
   producer outputs admitted downstream are bounded receipts that trusted
   `main` code revalidates against the exact source job and context.
2. `.github/workflows/autonomy-attest.yml` runs on `workflow_run` after the
   producer completes. GitHub loads this workflow definition from `main`, so PR
   code cannot replace the verifier or obtain signing authority. A context job
   resolves the exact triggering run and one live PR through the GitHub API.
   The run head, its associated PR base/head snapshot, and the live PR
   base/head must all match. A producer `requested` event cancels an older
   signer for the same head branch; only `completed` runs enter derivation.
3. Candidate code is executed only in the unprivileged `pull_request`
   workflow, never in `workflow_run`. That producer checks out its supervisor
   and verifier from the exact base SHA. A root parent that never imports
   candidate modules starts `saas_server.py` as `nobody` with a sanitized
   environment, no GitHub token or OIDC variables, a read-only checkout and
   runtime, a private writable data directory and bounded resources. The
   parent probes only loopback HTTP, records bounded structural facts (not
   response bodies, cookies or tokens), kills the process group, and writes a
   canonical receipt outside candidate control. Candidate stdout, exit codes,
   command-line arguments and file descriptors are not evidence. Early exit,
   forged green output, timeout, malformed response, missing route, secret
   marker or context drift fails closed.
4. The trusted `workflow_run` jobs never check out the candidate head and
   never execute producer artifacts. They first require that the candidate
   producer and conventional CI workflow bytes exactly match their trusted
   base versions. All actions in that conventional CI source, the producer,
   and the signer are pinned to verified immutable commits. `ci` is derived
   from the exact completed conventional GitHub
   Actions run, attempt, head SHA, event, PR association and complete expected
   job inventory. `runtime` and `reality` are derived only after bounded,
   canonical parent-owned receipts and their exact producer jobs are validated.
   Other artifacts are parsed solely as bounded data with exact inventories.
5. Trusted base code restricts the runtime lock to nine reviewed
   distributions, downloads only hash-pinned wheels, and inspects every
   wheel's identity, digest, metadata and archive members before installation.
   Startup hooks, symlinks, traversal, duplicates and unexpected packages fail
   closed. Trusted tools and candidate dependencies use separate virtual
   environments created from the absolute `setup-python` output outside the
   checkout. Fresh normalization runners query the attempt-specific GitHub
   Jobs API, require one exact successful job and fixed-command step, verify
   parent-owned CI/black-box receipts, and hash retained logs for the other checks.
   GitHub API and git path inventories must agree, both rename paths are
   included, and removing or renaming a canonical trust-root asset is rejected.
   After this one-time bootstrap, any mutation of a canonical control-plane
   asset also fails trusted AppSec evidence and requires a separately authorized
   bootstrap; an ordinary PR cannot rewrite its future verifier and be attested
   by the old one.
   They derive `overlap` live with a read-only token. The
   OIDC/status job is separate: it
   never checks out or executes candidate bytes, enforces the exact receipt
   inventory, emits `final-review`, assembles and pre-verifies the manifest,
   and creates an official attestation with `actions/attest`. It retains the
   official Sigstore bundle, captures GitHub CLI's current trusted roots, runs
   `gh attestation verify` in offline mode with both explicit files, retains
   the resulting JSON, binds that result to every evidence byte, and posts the
   `autonomy-evidence` commit status on the exact PR head. Any failure posts
   failure and closes the gate.
   Immediately before publishing success it re-derives the live PR identity
   and overlap set again; any intervening head, metadata, ownership or open-PR
   change fails closed.

Partial “re-run failed jobs” recovery is intentionally fail-closed because a
new run attempt may omit evidence jobs that already passed in a prior attempt.
Recovery uses “re-run all jobs”, preserving one complete attempt-specific job
inventory rather than mixing evidence across attempts.

The manifest distinguishes the evidence run identity from the trusted signer
run identity. The official attestation is bound to the repository, candidate
base and head SHA, producer workflow/ref/run ID/run attempt, signer
workflow/ref/run ID/run attempt and trusted source digest, plus the manifest
digest. A conventional green check cannot substitute for a missing artifact,
manifest binding, or official attestation.

The live overlap receipt binds a canonical digest of every open PR number,
head SHA, title/body digest, and changed-path digest; rename inventories include
both the old and new path. Metadata edits re-trigger the producer. Because the
set of open PRs is dynamic, `.github/workflows/autonomy-guard.yml`, loaded only
from `main`, immediately invalidates the affected head on PR changes or a new
producer request, then re-evaluates all open PR pairs after every producer run
and hourly. It can only replace an existing `autonomy-evidence` success with
failure; it never publishes success. It invalidates statuses older than five
days, leaving a conservative margin inside the seven-day manifest validity. A
scheduled workflow is defense in depth, not a fail-closed TTL primitive; merge
still requires a fresh attestation on the current head. The autonomous
merge actor must also repeat the live `/goal` overlap preflight immediately
before merge and compare it with the attested snapshot. An imported ruleset
that cannot enforce that final live boundary remains a stopper rather than an
assumption.

The bootstrap is classified high risk because it changes `.github/workflows/`,
`CODEOWNERS`, `config/`, and evidence verification code. The maker is
`engineering/engineering-api-platform-engineer.md`; the final reviewer is
`testing/testing-reality-checker.md`; AppSec reviewers are
`security/security-appsec-engineer.md` and `security/security-architect.md`.

## Fail-closed verification

The Python layer in `scripts/verify_autonomy_evidence.py` is Python 3.11
stdlib-only. It executes the complete Draft 2020-12 keyword subset used by the
committed manifest schema and fails if the schema introduces an unsupported
keyword. Cryptographic offline attestation verification is delegated to the
official GitHub CLI with `--bundle` and `--custom-trusted-root`; the public CLI
does not accept caller-provided `verificationResult` JSON. It rejects a
one-byte artifact mutation, missing required evidence, expired evidence,
incorrect base/head/run identity, non-canonical producers or aliases, maker and
final reviewer reuse, missing or non-independent AppSec reviewers, overlap or
conflict, incorrect attestation binding, malformed self-digests, and known test
secrets/private tenant markers. A durable run is an exact, versioned bundle
under `data/night_shift/runs/` containing the manifest, independent evidence
files, changed-path inventory, official Sigstore bundle, and captured trusted
root. `scripts/verify.py` walks every committed bundle, rejects unexpected
inventory, invokes the same cryptographic offline verifier, and validates every
manifest/artifact binding without changing its command-line interface. The
repository starts with no synthetic run history.

## Repository protection

`CODEOWNERS` assigns the control-plane paths to the existing owner
`@adrimg3196`; no user or team is invented. This is change visibility for the
trust root, not a routine human decision gate. The imported repository ruleset
is not modified by this change. After the bootstrap merge, a no-product-change
canary PR must demonstrate both rejection of incomplete evidence and acceptance
of complete, officially attested evidence. Any failed check, missing
attestation, unresolved P1/P2 conversation, or ineffective ruleset stops before
merge.

The trusted-root file retained with a run is evidence of what the trusted job
used, not a self-authenticating root. A portable offline consumer must import a
current trusted root through GitHub's independently authenticated/TUF channel,
as required by GitHub's offline-verification documentation. Replacing a bundle
and a co-packaged root together is never accepted as an independent trust
bootstrap.

The commit status itself is not accepted as a sufficient trust proof. The
effective ruleset must prevent unreviewed workflow/control-plane changes and
the canary must confirm that a same-name conventional status cannot substitute
for the official attestation path. If the imported ruleset does not enforce
that boundary, the bootstrap remains blocked rather than adding a bypass.

## Circular bootstrap boundary

`workflow_run` uses the workflow definition on the default branch. Therefore
the initial bootstrap PR cannot receive a trusted attestation until
`autonomy-attest.yml` already exists on `main`. This is an explicit trust
boundary, not a condition to work around: there is no PR-head OIDC signer, no
locally fabricated verification receipt, no administrative bypass, and no
temporary weakening of the imported ruleset.

The one-time bootstrap authorization is recorded as governance evidence, but
does not masquerade as an official attestation. If the effective ruleset or the
owner's current authorization requires the official attestation before that
first merge, the bootstrap stops as blocked. Once the trusted signer exists on
`main`, every subsequent candidate, including the canary, must satisfy the
complete official-attestation path.

## Autonomous operating model

Canonical agents own routine prioritization, implementation, review,
verification, and repository decisions within the granted autonomy-B scope.
They do not ask the owner to approve ordinary technical choices or to operate
GitHub on their behalf. A daily update is executive-facing: it states outcomes,
risk, confidence, and next action, and asks a concise question only when there
is a material strategic ambiguity, a stopper that cannot be resolved safely,
or an action outside the standing authorization. Security failures, missing
evidence, scope expansion, release or production actions, secret access, and
permission barriers remain hard stops rather than assumptions.
