# Loop budget & kill switch

Token/cost caps and the emergency stop for LucidFence improvement loops.
Enforced manually by the maintainer and (where possible) by CI.

## Aggregator policy (2026-08-22, decision t_bae7f2e4)

The `/loop` MoA improvement loop MUST stay 100%-free, consistent with the
SOAR/Multi-UEM claim (#188/#110) and the 100%-free posture of 2026-08-16.

- **Default aggregator ($0):** the local MoA server at `127.0.0.1:8085`, called
  with `moa_dry=true` (free local synthesis, no API keys, no cost). Same server
  already consumed by `lucidfence/core/ai.py`.
- **Fallback ($0):** deterministic local heuristic merge when MoA is down.
- **Opus 4.8 (PAID, opt-in ONLY):** used solely when an operator sets
  `LUCIDFENCE_CLAUDE_CLI=<absolute path to the claude binary>`. Auto-discovery
  of `claude` in PATH is intentionally DISABLED so the loop can never silently
  incur Opus spend. Enabling Opus requires explicit Product sign-off (business-
  model impact) recorded here; it breaks 100%-free.

This resolves the Finance & Ops alert of 2026-08-22: `loop_improve.py` previously
auto-selected `claude` (Opus 4.8, paid) as the aggregator, the only paid component
in the fleet. It is now the free local MoA by default.

## Caps

- **Per-loop-run token cap:** 200k tokens (report-only triage).
- **Per-day token cap:** 500k tokens across all loops.
- **Max PRs reviewed per run:** 10.
- **Max attempts per fix:** 3 — after 3 failed verifier runs, escalate to human
  (do NOT keep retrying the same failing action).

## Kill switch

- Set the `loop-pause` label on any PR → loop stops commenting/acting on it.
- CI: set `LOOP_PAUSE=1` (repo secret or workflow input) to skip loop jobs.
- Manual: delete or pause the scheduled workflow.

## No-progress detection

- If a fix attempt fails the verifier 3×, write a short note to `docs/internal/loop-run-log.md`
  and stop. A human decides next steps.
- If readiness score drops >10 points week-over-week, open a maintenance issue.

## Allowlist (auto-merge)

Only these are auto-mergeable by a loop:
- Loop scaffolding docs (docs/internal/STATE.md, docs/internal/LOOP.md, docs/internal/loop-budget.md, docs/internal/loop-run-log.md).
- `loop-audit` CI workflow and dependabot patches for loop tooling.

Everything else (adapters, engine, desktop, security) requires human merge.
