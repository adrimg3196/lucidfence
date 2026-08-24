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

LucidFence does not currently publish a PGP key for encrypted reports. Use either
channel below instead — both are monitored and satisfy responsible disclosure:

- **GitHub Security Advisory (preferred):** open a private vulnerability report via
  the "Report a security vulnerability" button on this repo
  (https://github.com/adrimg3196/lucidfence/security/advisories/new). This stays
  end-to-end private until we publish a fix.
- **Direct contact:** DM `@adrimg3196` on GitHub
  (https://github.com/adrimg3196) with the subject "LucidFence security report".
  Expect an acknowledgement within 5 business days.

If you need PGP for a high-sensitivity report, ask via either channel above and a
maintainer will provide a key or a mutually agreed secure channel.

## Security boundaries

- **No secrets in client state.** `data/cloud_state.json` is public by design (vitrina demo data, read via raw.githubusercontent with CORS `*`). Never put tokens, API keys, or real device data there.
- **Tenant data stays local.** BYOI: tokens UEM lives with the customer. The engine never stores or transmits UEM tokens to a LucidFence-owned backend.
- **Minimal surface.** Python stdlib-first; no web frameworks; HTTP propio en `saas_server.py`. Every dependency is a reason to audit.

## Outbound webhook egress (threat model)

LucidFence delivers incident notifications to operator-configured webhook URLs
(`incident_webhook_url`, the multi-channel `incident_webhooks` list, and the SOAR
webhook). These are **outbound** connections from the appliance to a URL the tenant
admin supplied. The threat is SSRF / SSRF-adjacent pivoting: a webhook URL that
resolves to an internal, loopback, link-local, or cloud-metadata address at send
time could be used to reach infra the appliance can reach but the caller cannot
(e.g. `169.254.169.254` cloud metadata, `127.0.0.1` admin services).

Defense in depth (combined across the 2026-08-18 and 2026-08-20 audits + this
follow-up, task `t_cd79333c`):

1. **URL admission guard (`_safe_webhook_url`, config time).** The URL must be
   `https`, on the explicit outbound port allowlist `{443, 8443}`, with no
   userinfo. Numeric-IP encodings (decimal/hex/octal/dotless, e.g. `2130706433`,
   `0x7f000001`, `127.1`) are canonicalized and hit the same filter as canonical
   IPs. A public hostname is resolved and **every** returned address is validated;
   if any is loopback / link-local (incl. cloud metadata `169.254.0.0/16`) /
   reserved / multicast the URL is rejected. Internal public-suffix TLDs
   (`.local`/`.internal`/`.lan`/`.home`, `localhost`) are rejected outright.
2. **Pinned-IP connect (send time — closes the DNS-rebinding TOCTOU).** The legacy
   path validated the hostname at config time but re-resolved it via the socket at
   send time, leaving a TOCTOU: an attacker controlling DNS could return a public
   IP at validation and an internal/metadata IP on connect. The webhook transport
   now resolves **once**, validates the whole snapshot, and connects to the
   validated IP with `Host`/SNI pinned to the original hostname (`_PinnedHTTPConnection`,
   mirroring the OIDC `PublicEgressPolicy` pattern in `lucidfence/core/oidc.py`).
   DNS is never consulted again on that delivery, so a rebinding flip cannot pivot.
   Regression coverage: `tests/test_webhook_toctou_pinning.py`.
3. **Literal-IP and unresolvable-LAN fast paths.** A URL the admin set as a literal
   IP bypasses DNS entirely (no rebinding surface) and is connected as-is — this
   preserves self-hosted / on-prem use (internal SIEM, local harness). An
   unresolvable LAN name (resolves only inside the customer network) is allowed
   through; the customer resolver handles it, and since it was never admitted as a
   "public" target there is no TOCTOU window.

### Deliberate trade-off: RFC1918 is NOT blocked

LucidFence is a **local-first UEM appliance**. Its own configured UEM endpoints
(Intune/Jamf/Workspace ONE/Applivery) and a self-hosted operator's webhook receiver
are routinely on RFC1918 / internal hostnames the operator legitimately configures.
Blocking RFC1918 on webhook egress would break on-prem UEM. Therefore RFC1918 and
unresolvable LAN names remain **allowed**; only the genuine SSRF pivots
(loopback / link-local / cloud-metadata / reserved / multicast) are blocked. This is
documented behaviour, not a defect.

### Shipped (opt-in): per-tenant egress allow/deny-list  ·  task `t_f33e2f23`

**Status: SHIPPED (opt-in).** Per the product decision (`t_316b8ec5`, APROBADA), a
tenant-scoped allow/deny-list for **outgoing webhooks** is implemented in
`lucidfence/core/notifier.py` (`EgressAllowListPolicy`) and wired through
`build_incident_notifiers`, `Engine.status()`, and the dashboard wizard.

- **Default `permissive`** (current behaviour) — existing deployments are
  unaffected. The admission guard (layer 1) still always runs.
- **Opt-in `strict`** via `egress_policy` in the tenant `integration.json`
  (chmod 0600). In `strict`, delivery additionally requires the destination
  host to be on the `allow` list:
  - exact hostname (`hooks.slack.com`),
  - domain suffix (`.slack.com` — covers subdomains),
  - literal IP (`10.20.30.40` for a fixed SIEM).
  - A global wildcard `*` is **rejected** (it would be an allow-all that
    nullifies the policy).
- **`allow_private`** (default `false`) governs RFC1918 in `strict`: `false`
  denies private egress even when the host is listed (closes the residual H-3
  RFC1918 gap); `true` permits internal SIEMs / locked-down networks.
- A delivery denied by the policy returns an **explicit, non-silent**
  `{"ok": False, "result": "denied_by_egress_policy", ...}` that is surfaced in
  the dashboard (`engine.status()` → `webhook_delivery`), never swallowed.
- **Scope:** only outgoing webhooks (`incident_webhook_url`,
  `incident_webhooks[]`, SOAR webhook). UEM adapters (Intune/Jamf/Workspace
  ONE/Applivery/Fleet) are **out of scope** by product decision.
- **Defense in depth:** the allow-list is a layer *on top of* the admission
  guard — loopback / link-local / cloud-metadata `169.254.0.0/16` remain always
  blocked. In `strict`: admission guard **AND** allow-list must both pass.

Regression coverage: `tests/test_egress_allowlist.py`.

## Contact

Report security issues to **`@adrimg3196` on GitHub** (DM or the Security Advisory
form linked in the Public key section above). Do not open a public issue for the
vulnerability until we've confirmed it and published a fix.
