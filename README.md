# LucidFence — Enterprise Open-Source Multi-UEM Geofencing

**Local-first. BYOI (Bring Your Own Infrastructure). Zero cloud dependencies.**

Your device data stays on your machine. You sign the UEM tokens. You control the deployment. No proprietary backend storing devices or credentials.


## What It Is

LucidFence is a multi-UEM geofencing and risk policy engine that connects to the device management platforms you already use (Applivery, Intune, Jamf, Fleet) and adds geofencing, risk evaluation, and automated response on top of what they manage.

It does **not** replace your UEMs. It complements them.


## Quick Start (5 minutes)

```bash
# Install
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run the guided onboarding (environment → app → dashboard → data source)
lucidfence quickstart

# Or start the server directly
lucidfence server
# → Open http://localhost:8765
```

`google-earth` Quickstart is the recommended path for a new admin: it checks your environment, starts the app, verifies the live dashboard, and tells you exactly how to connect your real UEM (Intune/Jamf/Applivery/Fleet), with concrete action if something is missing.


## What Works Today

- **Compliance engine + risk policy**: runs locally, reports devices inside/not-compliant/violations.
- **UEM adapters**: Applivery, Intune, Jamf, Fleet — local state after ingestion.
  UEM onboarding with least-privilege in [`docs/integrations/`](./docs/integrations/)
  (Intune, Jamf, Applivery, Fleet) and the [location matrix](./docs/integrations/LOCATION_MATRIX.md)
  with what each UEM actually provides.
- **Safe rollout for pilots**: `enforcement.mode: observe|enforce`, action gating and
  double-key for wipe. Runbook: [`docs/operations/ENFORCEMENT.md`](./docs/operations/ENFORCEMENT.md);
  day 2 (service, backup, upgrade): [`docs/operations/DAY2.md`](./docs/operations/DAY2.md).
- **Local dashboard on `:8765`**.
- **Optional osquery posture**: OS, storage, encryption, battery —
  correlated with geospatial risk. See [`docs/integrations/OSQUERY.md`](./docs/integrations/OSQUERY.md).
- **Cloud showcase**: `data/cloud_state.json` published, read by `static/cloud.html`.


## Architecture

```
[UEM Provider APIs] → [UEM Adapters] → [State Store] → [Engine]
                                                          ↓
                                                   [Policy Engine]
                                                          ↓
                                                 [Dashboard / CLI]
                                                          ↓
                                                 [Cloud Publisher] → [GitHub Pages]
```


## Stack

- **Python 3.11**, stdlib-first. Own HTTP server in `saas_server.py` (no web frameworks).
- Each UEM adapter is a plugin for `core/` — engine, policies, state_store, adapters, cve_feed_nvd, location_source (simulation).
- **Cloudflare Worker** optional for the UEM gateway (`apps/uem-gateway/`).
- **macOS Swift app** optional (`apps/macos/` + builder DMG).


## Project Structure

```
lucidfence/              # The only Python package (everything importable)
core/                    # engine, policies (risk), state_store, adapters, cve_feed_nvd, location_source
saas/                    # tenants, local auth, RBAC
mcp/                     # stdio read-only MCP servers
plugins/                 # verified-by-hash adapter index + third-party providers
cli.py / shell.py        # lifecycle CLI and interactive shell

apps/
  macos/                 # Swift app + builder DMG
  uem-gateway/           # Optional Cloudflare Worker

data/
  cloud_state.json       # Published state for the showcase (committed, served by Pages)
  cloud_tenants/<id>/data/  # Cloud tenants (real multi-tenant via saas-api)

static/
  dashboard.html         # Local SPA
  cloud.html             # Serverless showcase (reads data/cloud_state.json via raw.githubusercontent)
  app.js

docs/                    # All documentation; index in docs/README.md
tests/                   # Honest runner: tests/run_tests.py
```


## Enterprise-Ready

- **100% free and open-source (Apache-2.0)**. No pricing, no enterprise edition, no paid features, no telemetry. The entire product is free to use, modify, and distribute.
- **Local-first security**: credentials never leave your machine; no proprietary backend collects device data.
- **Full CI pipeline**: Python tests, frontend syntax check, dependency audit (pip-audit + CycloneDX SBOM), runtime-artifacts gate (rejects cloud_state.json changes in PRs), secret scan (gitleaks). See `.github/workflows/ci.yml`.
- **GitHub Releases**: v1.5.0 published with description and asset; `release.yml` builds, installs, and runs the artifact before publishing.
- **Docker support**: `docker compose up -d` runs LucidFence always-on on localhost:8765. `internet-facing` profile lifts Caddy for TLS.
- **Security disclosure**: `SECURITY.md` with disclosure path; the Centinela loop attacks LucidFence itself on localhost (Strix method) and records findings with PoC.


## Honest Gaps (what's not done yet)

This section is reality, not marketing. Updated when a gap is closed.

| Area | Status | What's missing |
|------|--------|----------------|
| **Public README / external onboarding** | Complete — external getting started guide | [`docs/GETTING_STARTED.md`](./docs/GETTING_STARTED.md): what you need, how to install, how to verify it works, first real step (connect UEM), FAQ, and how to report bugs/security. Linked from above. |
| **Real CI (not just state cron)** | Functional — full CI already exists | GitHub Actions already gates: python tests, frontend syntax check, dependency audit (pip-audit + CycloneDX SBOM), runtime-artifacts (rejects cloud_state.json changes in PRs), secret-scan (gitleaks). See `.github/workflows/ci.yml`. |
| **Release tags / version publishing** | Complete — GitHub Releases published | v1.5.0 published as a GitHub Release with description and asset; `release.yml` builds, installs, and runs the artifact before publishing. See CHANGELOG.md and the Releases tab. |
| **Docker / compose for third parties documented** | Complete — docker-compose.yml + Dockerfile exist | `docker compose up -d` runs LucidFence always-on on localhost:8765. `internet-facing` profile lifts Caddy for TLS. See `docker-compose.yml`. |
| **UEM adapter docs for contributors** | Complete — public guide | [`docs/contributing/new-adapter-guide.md`](./docs/contributing/new-adapter-guide.md): how to add a new UEM adapter with the `MDMAdapter` contract and the mock offline path. Scaffolding with `lucidfence adapter new`. |
| **Live public showcase / demo** | Complete — showcase + demo walkthrough | `cloud.html` reads raw.githubusercontent, functional. Step-by-step demo without code in [`docs/demo-walkthrough.md`](./docs/demo-walkthrough.md). |
| **Pricing / business model declared** | Declared — 100% free OSS | **No pricing.** LucidFence is free and open-source software under Apache-2.0: no paid tier, no enterprise edition, no paid features, no telemetry. The whole product is free to use, modify, and distribute. See §Model below. |
| **Support channels / issue triage** | Functional | `CONTRIBUTING.md` with the flow; third-party issues triaged by the fleet (labeling + response), external authors never auto-merged. |


## Model (Free & Open-Source)

LucidFence is **free and open-source software, 100% free**. There is no paid business model:

- **No pricing, no tiers.** There is no "pro", "enterprise", or "paid cloud" edition. The entire product — engine, UEM adapters, dashboard, local multi-tenant SaaS, MCP — is in this repo under Apache-2.0.
- **No paid features or upsell.** Nothing is behind a paywall. Nothing requires a commercial license.
- **No telemetry, no exfiltration.** Tenant data lives on your machine; there is no proprietary backend that collects it.
- **BYOI (Bring Your Own Infrastructure).** You run the deployment with your own UEM credentials and your free tiers; the project does not charge or intermediate.

Apache-2.0 allows anyone — person or company — to use, modify, and distribute this without cost or restriction. If someone builds a paid service on top, that's their business; the project itself is and will remain free.


## Credits

See `AGENTS.md` for who works on this (agents + Adri). This is concurrent multi-agent development + human owner, commits under different names.


## License

Apache-2.0 — see `LICENSE` for full terms. No use, modification, or distribution restrictions. Corporations can adopt this without legal review of copyleft.


---

*Full-local. No credentials. No proprietary data backend.*
