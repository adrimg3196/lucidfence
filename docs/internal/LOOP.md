# docs/internal/LOOP.md — Improvement loop for LucidFence

LucidFence is a local-first, free, open-source geofencing / UEM product. This
file documents the improvement loop used to maintain it, adapting the
[loop-engineering](https://github.com/cobusgreyling/loop-engineering) patterns.

## Active loops

### Admin-value (L2 — asistido, cadencia semanal)
- **Patrón completo:** `docs/internal/loop-admin-value.md`.
- **Objetivo:** empujar el producto a "imprescindible para el admin IT"
  (onboarding sin fricción, rollout seguro, claims siempre validados).
- **Trigger:** Routine semanal (lunes 05:00 UTC) que lanza una sesión nueva;
  también ejecutable a mano pidiendo "ejecuta un ciclo del loop admin-value".
- **Gate:** hasta 1 PR por run, merge solo con el gate QA del repo (CI verde
  + runtime battery + `VEREDICTO QA: APTO`); la lista de gates humanos de
  `loop-constraints.md` sigue intacta. Esta excepción al "no auto-merge" de
  abajo la mandató el propietario (sesiones 2026-08-15) y aplica SOLO a este
  loop.
- **Estado/memoria:** sección "Loop admin-value" de `STATE.md` + run-log.

### Contributor PR triage (L1 — human-gated)
- **Trigger:** new PR or issue on `adrimg3196/lucidfence`.
- **Maker:** contributor (or maintainer) proposes the change.
- **Verifier (checker / maker-split):** the change is verified by the honest test
  runner `python3 tests/run_tests.py`, a `gitleaks` secret scan, and a
  frozen-contract check (`lucidfence/core/adapters/base.py` must not change). All three MUST
  pass before human merge. This file itself is the verifier contract.
- **Checks (verifier):** secrets scan (`gitleaks`), frozen `MDMAdapter` contract
  (`lucidfence/core/adapters/base.py` must NOT change), offline mode preserved, tests green
  without real credentials, `.env.example` only placeholders.
- **Gate:** NO auto-merge. Maintainer reviews and merges.
- **Duplicate/spam policy:** close duplicate PRs; reject PRs that embed wallet
  addresses, credentials, or off-topic changes.

### Daily quality dogfood (L1 — report-only)
- **Trigger:** on push / PR via `.github/workflows/loop-audit.yml`.
- **Action:** run `loop-audit` and post the readiness score as a PR check.
- **Human review:** weekly review of drift below L1.

## Safety & gates

- **No auto-merge to `main`** except trivial doc/loop-scaffolding changes.
- **Denylist:** secrets in `config.json`/`data/`; modifications to
  `lucidfence/core/adapters/base.py` without a major version bump; publish of
  `data/cloud_state.json` with real tenant data.
- **Least privilege:** CI uses read-only `GITHUB_TOKEN`; no deploy secrets in
  loop workflows.
- **MCP usage:** not required for this loop. If a connector is added later, it
  MUST be read-only (issue/PR discovery) and scoped in `docs/internal/LOOP.md` before use.
- **Worktree isolation:** every unattended code-change experiment runs in an
  isolated git worktree; one worktree per fix, discarded after a failed verifier
  or human escalation.
- **No-progress / circuit breaker:** after 3 failed verifier attempts on the
  same fix, stop and escalate to a human (see `docs/internal/loop-budget.md`). Never repeat the
  same failing action — write a note to `docs/internal/loop-run-log.md` instead.
- **Human escalation:** any PR touching the adapter contract, the Desktop build,
  or security posture MUST be reviewed by the maintainer before merge.

## Budget & observability

- Token caps and kill switch: `docs/internal/loop-budget.md`.
- Run history: `docs/internal/loop-run-log.md` (append-only).
- `loop-audit` is the readiness signal; score regressions are reviewed, not
  auto-reverted.

## How to run locally

```bash
npx @cobusgreyling/loop-audit . --suggest
npx @cobusgreyling/loop-audit . --badge
```
