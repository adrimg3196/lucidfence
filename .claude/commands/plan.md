---
description: Plan LucidFence work into tasks with acceptance criteria and a build order
---

Invoke planning-and-task-breakdown adapted to LucidFence.

Read `SPEC.md` first (the project's standing spec). Break the work into tasks:
- Each task: objective, acceptance criteria, files touched, verification (how to
  confirm done at runtime — e.g. `python3 tests/run_tests.py`, open cloud.html).
- Order tasks by dependency. Mark what can run test-driven.
- Respect `references/definition-of-done.md` as the standing gate.

Save as `tasks/plan.md`. Confirm with the user. Brownfield note: LucidFence is
established code — write characterization tests before changing untested legacy
behavior (see references/testing-patterns.md).
