---
description: Build LucidFence slices test-driven, one at a time, committing atomically
---

Invoke incremental-implementation + test-driven-development adapted to LucidFence.

For each task in `tasks/plan.md`:
1. Write the test first (fails without the change). See `references/testing-patterns.md`.
2. Implement the minimal change to make it pass.
3. Run `python3 tests/run_tests.py` — must stay green (105 pass today).
4. Commit atomically (~100 lines), message `feat(scope): ...`.

Never skip runtime verification. Never let the test runner hide failures
(don't reintroduce the old SystemExit-aborts-discovery bug). When done, run
`/review` before merge.
