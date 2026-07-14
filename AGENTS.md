# AGENTS.md — LucidFence project rules (context-engineering)

Apply these rules on every task in this repo. They describe the REAL conventions,
not the wiki.

## Stack & commands
- Python 3.11, stdlib-first. No web frameworks (HTTP propio en `saas_server.py`).
- Test: `python3 tests/run_tests.py` (honest runner; 105 pass = green).
- Cloud vitrina: `python3 cloud_publisher.py --cycles 2` → `data/cloud_state.json`.
- Local SaaS: `python3 saas_server.py` (`:8765`).
- Client install: `./install.sh` or `docker compose up -d`.

## Directory meaning
- `core/` — engine, policies (risk), state_store, adapters (Applivery/Intune/Jamf),
  cve_feed_nvd, location_source (simulation).
- `static/` — `dashboard.html` (SPA local, habla con `:8765`), `cloud.html` (vitrina
  serverless que lee `data/cloud_state.json` vía raw.githubusercontent), `app.js`.
- `data/cloud_state.json` — estado publicado para la vitrina (commiteado, lo sirve Pages).
- `data/cloud_tenants/<id>/data/` — tenants de la nube (multi-tenant real vía saas-api).
- `.github/workflows/` — engine-cron (backend serverless 15min), deploy-pages,
  saas-api (operaciones), deploy-fly (listo, requiere FLY_API_TOKEN del cliente).

## Known landmines
- `tests/run_tests.py` MUST stay honest. A `test_*.py` that does `raise SystemExit`
  at import used to abort discovery of all later files, hiding 11 failures. The
  runner catches SystemExit per-module — never reintroduce the hiding bug.
- `cloud_publisher.py` processes only `data/cloud_tenants/<id>/data/` that have
  BOTH `fleet_seed.json` AND `fences.json`. Don't mix with `data/tenants/` (basura de tests).
- GitHub Pages serves under `/lucidfence/` subpath → use relative links in static/,
  never absolute `/app`, `/cloud.html`, `/static/...` (causaba 404).
- The vitrina reads state from `raw.githubusercontent.com` (CORS `*`). Don't put
  secrets there. cloud_state.json is public by design (demo data).
- macOS caches directory listings — `os.listdir` may miss a freshly-created test
  file; `touch` the dir to invalidate before re-running the runner.

## Boundaries (delegated decision 2026-07-14)
- ALWAYS: verify at runtime; runner honest; $0 (free tiers only); tenant data stays
  on the client's machine.
- ASK FIRST: any paid dependency; any always-on backend needing OUR token (Fly/HF).
- NEVER: hardcode secrets; expose a token in the Pages client; use `flyctl auth
  login` headless (fails silently); leave zombie processes between sessions.

## Quality floor
- Definition of Done: `references/definition-of-done.md`.
- Testing: `references/testing-patterns.md`.
- Security: `references/security-checklist.md`.
