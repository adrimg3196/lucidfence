# Structural tech debt — tracked, not hidden

> Senior-review findings (2026-08-20) that are **too large for one safe change**.
> Recorded here so a deferral cannot rot into "later means never". Each item has
> a first increment already shipped or a concrete plan — never a big-bang.

## SD-1 · Monoliths: `saas_server.py`, `static/app.js`, `engine.py`

**Problem.** `saas_server.py` (~2.6k lines: HTTP server + routing + auth + ~40
endpoints as `if route == …` chains), `static/app.js` (~2.4k lines, the whole
frontend in one file), `engine.py` (~1.1k). Onboarding cost is real: adding an
endpoint means reading the whole `Handler` to learn the auth/tenant-scoping
pattern (tribal knowledge, not design).

**Why not a big-bang.** A single "split into modules" PR touching a 2.6k-line
request handler is the highest-risk change possible in this repo: every route
shares the `Handler`, auth, and tenant-scoping state; one missed guard is a
security regression the tests may not catch. Stdlib-first does **not** require
single-file — but the refactor must be incremental and each slice independently
verified by the runtime battery.

**Plan (one slice per Admin-value cycle, WIP=1):**
1. Extract a documented `route()` helper + an explicit route table (dict → handler
   fn) so the auth/tenant-scoping pattern is declared **once**, not copied. This
   is the enabling step: it makes every later extraction mechanical.
2. Move endpoint groups into `lucidfence/saas/routes/*.py` modules (devices,
   fences, coverage, members, providers…), one group per PR, battery green each.
3. `app.js`: split by view (`views/map.js`, `views/devices.js`, …) behind a tiny
   loader; no framework, no build step added.
4. `engine.py`: extract the signal-evaluation and action-dispatch halves once the
   route work proves the pattern.

**Acceptance per slice:** no endpoint changes behavior (battery N/N), no auth
guard removed (a diff-reviewed checklist), file count up / max-file-size down.

**Status:** planned. Owner loop: Admin-value. Not started — sequenced after the
2026-08-20 documentation pass.

## SD-2 · The autonomous-fleet code ships inside the product

**Problem.** `autonomous_company.py`, `loop_governance.py`, `roadmap_tooling.py`
live in `lucidfence/core/` — the meta-company (the AI loops that *build* the
product) mixed with the geofencing engine an admin installs. A senior asks: does
this ship in the tarball? Why does my MDM carry a "autonomous company" module?

**First increment (verify now).** `scripts/build.sh` already excludes
`loop_improve.py` from the tarball; confirm the fleet-only modules are likewise
excluded from what the admin installs, and **document the boundary**: `core/` is
mixed today, but the *shipped artifact* must contain only product runtime. If any
fleet-only module is currently in the tarball, that is the bug to fix first
(smallest change: extend the build exclude + a test asserting the tarball's
module list).

**Plan.** Move fleet-only modules to a top-level `fleet/` package (outside
`lucidfence/`) so the separation is physical, not a build-time exclude. Deferred
because it touches imports across `saas_server.py`, `roadmap_tooling.py` and
tests — same care as SD-1, sequenced after it.

**Status:** planned. Owner loop: fleet-architect. First increment (tarball
boundary audit + doc) is small and can go in an early cycle.

## HP-1 · Purging `data/cloud_state.json` from `main` history

**Context.** As of 2026-08-20 the live snapshot is published to a dedicated
`cloud-state` branch, so `main` no longer receives a commit every 15 minutes
(fixed going forward). But `main`'s **existing** history still contains ~thousands
of `cloud: actualizar estado en vivo` commits.

**Why not done autonomously.** Purging them requires rewriting `main` history
(`git filter-repo` + force-push), which breaks every existing clone, fork and
open PR, and invalidates commit SHAs referenced elsewhere. That is a destructive,
irreversible operation that must be an explicit **owner decision**, not an
autonomous one.

**Recommendation.** If a clean history is wanted, schedule a one-time
`git filter-repo --path data/cloud_state.json --invert-paths` during a quiet
window, announce it, and have contributors re-clone. Until then, the going-forward
fix (cloud-state branch) is the important half: the noise stops now.

**Status:** owner decision pending. Not blocking.
