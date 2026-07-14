---
description: Five-axis code review of LucidFence changes (correctness, readability, architecture, security, performance)
---

Invoke code-review-and-quality adapted to LucidFence (Python).

Review the staged changes / recent commits across five axes:
1. **Correctness** — behaviors verified at runtime? edge cases? error paths?
2. **Readability** — names reveal intent? no redundant comments?
3. **Architecture** — fits `SPEC.md` structure? no duplicated business logic?
4. **Security** — untrusted input? auth on every endpoint? no secrets? (see `references/security-checklist.md`)
5. **Performance** — engine loops, DB snapshots, SVG render — any hot path regression?

Output the standard template with severity labels:
- **Critical** (blocks merge): breaks runtime, loses data, exposes secret.
- **Required** (blocks merge): misses acceptance criteria, test gap, regression.
- **Recommended**: polish, naming, doc.
- **Nit**: style.

The runner `tests/run_tests.py` must stay green. Flag any test that hides failures.
