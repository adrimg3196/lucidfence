# Loop budget & kill switch

Token/cost caps and the emergency stop for LucidFence improvement loops.
Enforced manually by the maintainer and (where possible) by CI.

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

- If a fix attempt fails the verifier 3×, write a short note to `loop-run-log.md`
  and stop. A human decides next steps.
- If readiness score drops >10 points week-over-week, open a maintenance issue.

## Allowlist (auto-merge)

Only these are auto-mergeable by a loop:
- Loop scaffolding docs (STATE.md, LOOP.md, loop-budget.md, loop-run-log.md).
- `loop-audit` CI workflow and dependabot patches for loop tooling.

Everything else (adapters, engine, desktop, security) requires human merge.
