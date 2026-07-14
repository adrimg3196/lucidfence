---
description: Pre-launch go/no-go for LucidFence via parallel fan-out to specialist personas
---

Invoke shipping-and-launch adapted to LucidFence. `/ship` is a fan-out orchestrator.

## Phase A — Parallel fan-out
Run three personas against the current change, then merge into go/no-go:

1. **code-reviewer** — five-axis review (correctness, readability, architecture,
   security, performance) on staged changes. Use `agents/code-reviewer.md`.
2. **security-auditor** — OWASP Top 10, secrets, auth, deps CVEs. `agents/security-auditor.md`.
3. **test-engineer** — coverage gaps: happy path, edge, error, concurrency. `agents/test-engineer.md`.

Issue all three in one turn (parallel). If subagents unavailable, run sequentially
and merge in main context.

## Phase B — Merge
Synthesize: Code Quality (Critical/Required + failing tests), Security (Critical/High
→ blockers), Performance, Accessibility, Infrastructure (env, migrations, monitoring),
Documentation (README, ADRs, CLIENTE.md).

## Phase C — Decision
```markdown
## Ship Decision: GO | NO-GO
### Blockers (must fix)
### Recommended fixes
### Acknowledged risks
### Rollback plan (trigger, procedure, RTO)
### Specialist reports
```

Rules: parallel fan-out never sequential; rollback plan mandatory; Critical → default NO-GO
unless user accepts risk. Skip fan-out only if change <2 files, <50 lines, no auth/data/config.
