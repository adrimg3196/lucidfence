# Loop budget & kill switch

Token/cost caps and the emergency stop for LucidFence improvement loops.
Enforced manually by the maintainer and (where possible) by CI.

## Caps

- **Per-loop-run prompt-token budget: ~500k tokens (MEASURED + ALERTED).**
  This is the *achieved product floor*, not an aspirational target: over the
  last 10 days of fleet operation, runs spanned ~507k–961k prompt tok/run and
  97.6% of all fleet tokens were INPUT (context). 81 of 124 recorded runs
  exceeded 500k. The number is treated as the current ceiling: any run above it
  is flagged in `~/.hermes/cron/usage_audit.jsonl` (kind=`budget_flag`) and
  alerted to Product + Finance by the `TOKEN-BUDGET-WATCHDOG-*` cron jobs
  (see `~/.hermes/scripts/token_budget_watchdog.py`, kanban t_9926eb60).
- **Per-run prompt-token STRETCH GOAL: 200k tokens (NOT enforced).**
  The original 200k/run figure was a design target that was never met and was
  documented as "report-only triage" with nothing measuring it. It remains a
  stretch goal to drive context discipline (diff-directed reading via the
  `context-efficiency` skill), but it is NOT a hard cap and runs are not blocked
  at 200k. Treat 200k as the efficiency target the fleet is working toward.
- **Per-day token cap: 500k tokens across all loops** (reporting only).
- **Max PRs reviewed per run:** 10.
- **Max attempts per fix:** 3 — after 3 failed verifier runs, escalate to human
  (do NOT keep retrying the same failing action).

## Measurement & alerting (since t_9926eb60)

- Source of truth: `~/.hermes/cron/usage_audit.jsonl`, written per fire by the
  Hermes cron scheduler.
- Post-run check: `token_budget_watchdog.py` runs hourly (no_agent), scans the
  audit log, and flags every run whose `prompt_tokens` exceed the 500k budget.
  Flags are durable (`kind=budget_flag`) and queryable forever.
- Alerting: over-budget runs are delivered to the Product and Finance bots via
  `bot-chat` (jobs `TOKEN-BUDGET-WATCHDOG-product` / `-finance`).
- The 500k budget is also the single source for the fleet diff-directed-reading
  rule (`~/.hermes/scripts/context_efficiency_rule.py`, `context-efficiency`
  skill): context discipline is the only cost lever that scales with bot count
  (23 jobs). Worst-case exposure if discipline is lost: ~$5.7k/mo (claude-opus-4).

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
