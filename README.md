# LucidFence

**Multi-UEM, local-first. BYOI (Bring Your Own Infrastructure).** Your data lives
on your machine, you sign the UEM tokens, you control the deployment. There is no
proprietary backend storing devices or credentials.

> 🇬🇧 **English** · [🇪🇸 Español](docs/README.es.md)

## What it is

A geofencing engine + risk policy that talks to the UEM adapters you already run
(Applivery, Intune, Jamf, Fleet, and more). It produces a compliance state, shows
it on a local dashboard, and optionally publishes a public snapshot for the
showcase.

Local-first: fleet state lives on your machine. The cloud is only an optional demo
JSON snapshot for the showcase → raw.githubusercontent (CORS `*`, no secrets by design).

## Quick start

```bash
# 1 — install
./install.sh
# or
docker compose up -d

# 2 — from install to seeing your fleet, in self-verifying steps
lucidfence quickstart             # env → app → dashboard → data source
# (equivalent to: python3 saas_server.py on :8765 + checks)

# 3 — tests (honest)
python3 tests/run_tests.py
```

`lucidfence quickstart` is the recommended path for a new admin: it checks the
environment, starts the app, verifies the live dashboard, and tells you exactly
how to connect your real UEM (Intune/Jamf/Applivery/Fleet) — with the concrete
action if something is missing.

> 📖 **Manual de uso** (con capturas): [español](docs/manual/MANUAL_DE_USO.md) ·
> [English](docs/manual/USER_GUIDE.md) · interactivo en `/static/manual.html`
> de tu instalación (selector ES/EN).
>
> ¿Primera vez? Empieza por **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)**:
> qué necesitas, cómo instalar, cómo comprobar que funciona, FAQ y cómo reportar
> un bug. (Este README es la vista técnica del proyecto.)

Dashboard: `http://localhost:8765` → `static/dashboard.html` (local SPA talking to `:8765`).

## Stack

- Python 3.11, stdlib-first. Own HTTP in `saas_server.py` (no web frameworks).
- Each UEM adapter is a plugin under `core/` — engine, policies (risk),
  state_store, adapters, cve_feed_nvd, location_source (simulation).
- Optional Cloudflare Worker for the UEM gateway (`apps/uem-gateway/`).
- Optional macOS Swift app (`apps/macos/` + DMG builder).

## Files that matter

```
lucidfence/          # the only Python package (everything importable)
core/                # engine, policies (risk), state_store, adapters, cve_feed_nvd, location_source
saas/                # tenants, local auth, RBAC
mcp/                 # read-only stdio MCP servers
plugins/             # hash-verified adapter index + third-party providers
cli.py / shell.py    # lifecycle CLI and interactive shell

apps/
  macos/             # Swift app + DMG builder
  uem-gateway/       # optional Cloudflare Worker

data/
  cloud_state.json           # published showcase state (committed, served by Pages)
  cloud_tenants/<id>/data/   # cloud tenants (real multi-tenant via saas-api)

static/
  dashboard.html     # local SPA
  cloud.html         # serverless showcase (reads data/cloud_state.json via raw.githubusercontent)
  app.js

docs/                # all documentation; index in docs/README.md
tests/               # honest runner: tests/run_tests.py
```

## What works today

- Compliance engine + risk policy: runs locally, reports in/no-compliant/violation devices.
- UEM adapters available: Applivery, Intune, Jamf, Fleet (local state after ingest).
  Per-UEM minimum-privilege onboarding in [`docs/integrations/`](docs/integrations/)
  (Intune, Jamf, Applivery, Fleet) and the [location matrix](docs/integrations/LOCATION_MATRIX.md)
  with what each UEM really provides.
- **Simultaneous multi-UEM per tenant:** Applivery live by default; Intune
  (Microsoft Graph) and Jamf Pro go live when you connect your tenant token
  (they fall back to simulation without one). Zero data exfiltration. See the
  [multi-UEM matrix](docs/integrations/MULTI_UEM.md) and
  [PRODUCT_SPEC](docs/architecture/PRODUCT_SPEC.md).
- **Declarative SOAR:** 4 frontline playbooks (critical CVE, CVE + out-of-perimeter,
  non-compliant + out, high EPSS) with per-device audit (`matched_fields`).
- Safe rollout for pilots: `enforcement.mode: observe|enforce`, per-action gating,
  double-key wipe. Runbook: [`docs/operations/ENFORCEMENT.md`](docs/operations/ENFORCEMENT.md);
  day-2 (service, backup, upgrade): [`docs/operations/DAY2.md`](docs/operations/DAY2.md).
- Local dashboard on `:8765`.
- Optional osquery posture: OS, storage, encryption, battery — correlated with
  geospatial risk. See [`docs/integrations/OSQUERY.md`](docs/integrations/OSQUERY.md).
- Cloud showcase: `data/cloud_state.json` published, read by `static/cloud.html`.
- Honest test runner (`python3 tests/run_tests.py`): real gates, no stubs; the
  tally lives in CI, not here (prose numbers go stale).
- Local state cron: `geofence_daily_report.sh` produces the summary with no network.
- License: Apache-2.0 (`LICENSE`), aligned with `pyproject.toml` and the Homebrew formula.

## Model (free & open-source)

LucidFence is **free, libre, and open-source — 100% free**. There is no paid
business model:

- **No pricing, no tiers.** There is no "pro", "enterprise", or "paid cloud"
  edition. The whole product — engine, UEM adapters, dashboard, local
  multi-tenant SaaS, MCP — is in this repo under Apache-2.0.
- **No paid features or upsell.** Nothing sits behind a wall. Nothing requires a
  commercial license.
- **No telemetry, no exfiltration.** Tenant data lives on your machine; there is
  no proprietary backend collecting it.
- **BYOI (Bring Your Own Infrastructure).** You run the deployment with your own
  UEM credentials and free tiers; the project charges nothing and intermediates nothing.

Apache-2.0 lets anyone — person or company — use, modify, and distribute it at no
cost or restriction. If someone builds a paid service on top, that's their call;
the project itself is and will remain free.

## Credits

See `AGENTS.md` for who builds this (agents + Adri). This is concurrent
multi-agent development + a human owner, with commits under different names.

## License

Apache-2.0 — see `LICENSE` for the full terms. No restriction on use,
modification, or distribution. Corporations can adopt this without copyleft legal review.

---

*Full-local. No credentials. No proprietary data backend.*
