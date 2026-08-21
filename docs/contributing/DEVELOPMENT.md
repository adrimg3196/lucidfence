# Development guide — how this repo works and why

The **technical why** behind LucidFence development. It complements
[CONTRIBUTING.md](../../CONTRIBUTING.md) (the how-to and etiquette) by explaining
the choices that will otherwise surprise a first-time contributor and sink a
first PR. Read both.

The house rules below are not style preferences — they are load-bearing, and the
gate (`scripts/verify.py`) enforces them.

---

## Stdlib-first: a dependency is an architecture decision

LucidFence is **standard-library only**. The engine, the HTTP server
(`saas_server.py`), the test runner, the risk engine, the adapters — all of it
is written against Python's stdlib with **no third-party runtime dependencies**.

This is deliberate: the product ships as something an admin can read end-to-end
and run anywhere Python runs, with no supply chain to vet. So:

- **Adding a dependency is a design decision, not a convenience.** It needs a
  real justification in the PR, not "it was easier with `requests`." The default
  answer is "use `http.client` / `urllib` / `json` / `dataclasses`."
- The one place non-stdlib tooling appears is **development tooling** (e.g.
  `ruff` for linting), never the runtime.

Target runtime is **Python 3.11+** (the test runner refuses to run below 3.11).

---

## The test runner: no pytest, no fixtures

Tests run through `tests/run_tests.py`, a **zero-dependency runner** that mirrors
just enough of pytest to keep the product stdlib-only. It:

1. discovers every `tests/test_*.py` file,
2. imports it, and
3. calls every top-level `test_*` function, counting pass/fail.

There are **no fixtures, no conftest, no parametrize, no markers.** A test is a
plain function that sets up its own world and asserts. Because there is no
fixture injection, tests build their own tenants/temp dirs and tear them down.

### The minimal test pattern

A real, runnable test looks like this — a plain function with a bare `assert`,
and (so the file also runs standalone) a `sys.path` insert to reach the package:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lucidfence.core.policies import _cmp


def test_cmp_gte_coerces_numbers():
    assert _cmp("70", "gte", 55) is True
    assert _cmp(10, "gt", 99) is False
```

Notes that will save you a confusing failure:

- The runner already inserts the repo root on `sys.path`, but keep the insert at
  the top of the file so the test is also runnable on its own.
- Anything needing the live server or temp state creates a `tempfile.mkdtemp()`
  data dir and passes it as `data_dir` in the engine config (see
  `tests/test_perf_engine.py` for a full worked example that builds a tenant).
- **Never `raise SystemExit` at import time or inside a test.** A module that
  exits during import kills discovery of every file after it. The runner defends
  against this, but it is still a way to silently drop coverage — see
  [testing-patterns.md](../references/testing-patterns.md).

Run the suite:

```bash
python3 tests/run_tests.py
```

The runner boots a real `saas_server.py` on `:8765` for integration tests and
tears it down after — so the suite is hermetic, but the port must be free when
it starts.

---

## The runtime battery: a claim that doesn't start live blocks the merge

Unit tests are necessary but **not sufficient** here. `scripts/runtime_validation.py`
is a separate gate that starts the **real** server, a **real** webhook receiver,
and the **real** MCP over stdio, then exercises each advertised feature through
its public interface. It prints `RUNTIME: N/M claims` and must be `N/N`.

The rule: **if a feature does not work live, it is not done — even with green
unit tests.** A green unit test that mocks away the thing the claim is about does
not earn the claim. New behavior that is user-facing needs a runtime check, not
just a unit test.

---

## `python3 scripts/verify.py` is the definition of "done"

"Done" is not a feeling or a passing local test — it is one command. `verify.py`
runs, in order:

1. **Version consistency** — `cli.VERSION` == `pyproject.toml` == `.release-version`.
2. **Doc links** — every relative link in the repo's `*.md` (root + `docs/`)
   resolves to a file that exists.
3. **Runtime battery** — `runtime_validation.py` must report `N/N`.
4. **Honest test suite** — `tests/run_tests.py` with zero real failures (only the
   known OIDC container baseline is tolerated).

```bash
python3 scripts/verify.py             # full gate; exit 0 == APTO
python3 scripts/verify.py --fast      # skip the runtime battery (checks 1,2,4)
python3 scripts/verify.py --docs-only # version + links only (instant)
```

`=== VERIFY: APTO ===` (exit 0) is the bar. Anything else is not mergeable. Note
that check #2 means **a broken relative link in any Markdown file fails the whole
gate** — when you add a doc, link only to files that exist. See
[definition-of-done.md](../references/definition-of-done.md).

---

## Lint gate: ruff, F and E9 only

Linting is `ruff` configured by [`.ruff.toml`](../../.ruff.toml) to select **only
`F` (pyflakes: flow, names, imports) and `E9` (syntax errors)** — real bugs, not
style.

The house style is intentionally **not** linted: compact one-liners like
`score += 10; reasons.append(...)` and imports placed after a module docstring in
scripts are deliberate and must stay lintable. Do not "fix" them, and do not add
lint rules that would flag them. `__init__.py` files are exempt from `F401`
because they re-export public surface on purpose.

---

## The full local flow

```bash
# 1 — clone
git clone https://github.com/<owner>/lucidfence.git
cd lucidfence

# 2 — establish the baseline BEFORE you touch anything
python3 scripts/verify.py            # should already be APTO

# 3 — write the change AND its test together
#     (a new user-facing claim also needs a runtime check)

# 4 — prove it
python3 scripts/verify.py            # must be === VERIFY: APTO ===

# 5 — open the PR
```

The delivery rail is automated: a push to a `claude/**` branch opens a PR and it
auto-merges **only** on a green gate. So the gate is the reviewer of record —
`verify.py` being APTO is what makes the change mergeable. Get it green locally
first.

### MCP servers wired into this repo

`.mcp.json` (project-scoped, so it travels with the checkout) declares the
servers the fleet uses:

| Server | Purpose | Auth |
|---|---|---|
| `github` | PRs, issues, CI status | `${GITHUB_PERSONAL_ACCESS_TOKEN}` from your env — never committed |
| `exa` | Web search and page fetch (`web_search_exa`, `web_fetch_exa`) for the Trends / Growth / Radar loops | none |

The Exa entry is deliberately **credential-free**. Those two tools answer
without any auth (verified live against `https://mcp.exa.ai/mcp`), which is what
lets the *unattended* night crons research the sector — an OAuth browser flow is
impossible there. Exa's advanced tools (`web_search_advanced_exa`, `agent_run`)
DO require auth: the server answers
`-32000 Authentication required. Use OAuth or provide an API key.` To opt into
them locally, add the key as a header and the tools to the URL:

```jsonc
"exa": {
  "type": "http",
  "url": "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa,agent_run",
  "headers": { "x-api-key": "${EXA_API_KEY}" }
}
```

Keep the key in your environment (`export EXA_API_KEY=...`), never in the file —
same rule as the GitHub token. Restart the MCP client after editing `.mcp.json`;
servers are loaded at startup.

### Where to go next

- Writing a new UEM adapter → [new-adapter-guide.md](new-adapter-guide.md).
- Writing policies against the engine → [POLICY_DSL.md](../reference/POLICY_DSL.md).
- Test conventions and pitfalls → [testing-patterns.md](../references/testing-patterns.md).
- What "done" formally means → [definition-of-done.md](../references/definition-of-done.md).
