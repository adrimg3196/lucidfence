---
description: Simplify LucidFence code without changing behavior (Chesterton's Fence)
---

Invoke code-simplification adapted to LucidFence (Python).

Reduce complexity without changing behavior:
1. Understand WHY code exists before removing (Chesterton's Fence). In legacy
   `core/`, the weird retry/loop may be load-bearing.
2. Behavior-preserving only. Add a characterization test first if the area is
   untested (see `references/testing-patterns.md`).
3. Remove dead code, duplicated business logic, debug output.

Verify after each change: `python3 tests/run_tests.py` stays green. Never simplify
untested code without a test first — that's the most expensive shortcut in brownfield.
