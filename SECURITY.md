# Security

LucidFence processes device and fleet data on the client machine. Report security issues responsibly.

## Scope

This policy covers the code and infrastructure in this repository: the Python engine, adapters, SaaS server, MCP servers, Cloudflare Worker, and macOS app. It does **not** cover third-party UEM providers' own security issues — report those to the provider.

## How to report

1. Encrypt your report using the maintainers' public key (see below) **OR** open a private vulnerability report via GitHub's "Report a security vulnerability" button on this repo.
2. Include: what you found, the version/commit, steps to reproduce, and impact.
3. Do not open a public issue for the vulnerability until we've confirmed it and published a fix.

## What we do

- We aim to acknowledge within 5 business days and keep you updated on progress.
- We will not pursue legal action against good-faith researchers who follow this policy.
- When we fix a reported issue, we publish a coordinated disclosure in the release notes.

## Public key

TODO: add maintainer PGP key / SOTD link when the project is ready for external reporting.

## Security boundaries

- **No secrets in client state.** `data/cloud_state.json` is public by design (vitrina demo data, read via raw.githubusercontent with CORS `*`). Never put tokens, API keys, or real device data there.
- **Tenant data stays local.** BYOI: tokens UEM lives with the customer. The engine never stores or transmits UEM tokens to a LucidFence-owned backend.
- **Minimal surface.** Python stdlib-first; no web frameworks; HTTP propio en `saas_server.py`. Every dependency is a reason to audit.

## Contact

TODO: add maintainer contact (email or DM channel) when the project is ready for external reporting.
