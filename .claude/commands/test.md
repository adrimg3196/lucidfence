---
description: Run LucidFence tests honestly and report the real tally
---

Invoke test-driven-development adapted to LucidFence.

Run the project's honest test runner:
```
python3 tests/run_tests.py
```
- It discovers every `test_*.py`, runs each `test_*`, catches `SystemExit`
  (modules that run their own suite at import), and prints a real tally.
- Green = `105 passed, 0 failed` and exit 0. A non-zero failure count or exit 1 = RED.
- NEVER mask failures; if a test hides an error, fix the test (see history:
  test_it_admin_features.py used to abort discovery).

For new behavior: write the test first (fails without change), implement, confirm green.
