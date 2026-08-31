# Threat Model — LucidFence

This document describes the threat model for LucidFence. It is maintained as part of the security program and reviewed regularly by the Centinela loop.

## Scope

LucidFence is a local-first multi-UEM geofencing and risk policy engine. This threat model covers:

- The core engine and its components
- The SaaS server (local API + dashboard)
- The UEM adapters (Applivery, Intune, Jamf, Fleet)
- The CLI and configuration
- The cloud publisher (optional, for public demo)

## Trust Boundaries

### 1. Operator ↔ LucidFence

The operator (administrator) controls the LucidFence deployment. They provide UEM credentials and configure policies.

**Threats**:
- Operator misconfigures policies (e.g., overly broad geofences)
- Operator provides incorrect or expired credentials

**Mitigations**:
- Policy validation (`lucidfence validate`)
- Dry-run mode for testing
- Credential scoping (least privilege)
- Audit log of configuration changes

### 2. LucidFence ↔ UEM Providers

LucidFence connects to external UEM APIs (Applivery, Intune, Jamf, Fleet) to fetch device data and trigger actions.

**Threats**:
- Credential theft (API keys, OAuth tokens)
- API rate limiting or abuse
- Data exposure via UEM API responses
- Man-in-the-middle attacks on API connections

**Mitigations**:
- Credentials stored locally, never transmitted to third parties
- HTTPS for all API connections
- Bearer token auth with scoped permissions
- Error handling that never exposes credentials in logs or responses
- Rate limit awareness in adapter implementations

### 3. LucidFence ↔ Devices

LucidFence evaluates device location against geofences and risk policies. Device data comes from UEM providers, not directly from devices.

**Threats**:
- Location spoofing (device reports false location)
- Device compromise (attacker controls device)
- Privacy violations (location data mishandled)

**Mitigations**:
- Location data is at rest only in local state
- No location data leaves the operator's machine unless explicitly published
- Risk engine uses multiple signals (not just location)
- Policy actions are gated and audited

### 4. Dashboard (local web UI)

The dashboard is a single-page application served locally on localhost:8765.

**Threats**:
- XSS via unsanitized device data
- CSRF (less relevant on localhost, but considered)
- Information disclosure via browser dev tools

**Mitigations**:
- All data is local, no external network requests from dashboard
- Content Security Policy (CSP) headers
- No eval() or inline scripts
- Authentication required for sensitive operations

### 5. Cloud Publisher (optional)

The cloud publisher optionally publishes a snapshot of fleet state to GitHub Pages for public demo.

**Threats**:
- Publishing sensitive data (credentials, device IDs, real locations)
- Exposure of internal network information

**Mitigations**:
- Only demo data is published (no real tenant data)
- Strict invariant: `data/cloud_state.json` contains only synthetic/demo data
- CI rejects changes to `cloud_state.json` in PRs (runtime-artifacts check)
- CORS wildcard is intentional for demo, but no secrets ever included

## Data Flow

```
[UEM Provider APIs] --> [UEM Adapters] --> [State Store] --> [Engine]
                                                                     |
                                                                     v
                                                            [Policy Engine]
                                                                     |
                                                                     v
                                                            [Dashboard / CLI]
                                                                     |
                                                                     v
                                                            [Cloud Publisher] --> [GitHub Pages]
```

## Threat Matrix

### T1: Credential Theft from Local Machine

**Severity**: High
**Description**: An attacker with access to the operator's machine steals UEM API credentials from the config file or environment variables.
**Impact**: Unauthorized access to UEM management APIs, potential device compromise.
**Mitigation**:
- Use environment variables for sensitive credentials (not config file)
- Restrict file permissions on config (chmod 600)
- Use OIDC device flow where possible (no long-lived secrets)
- Encrypt disk at rest

### T2: SSRF via UEM Adapter Webhooks

**Severity**: High
**Description**: A malicious UEM provider or compromised adapter configuration causes LucidFence to make requests to internal services.
**Impact**: Internal network scanning, data exfiltration.
**Mitigation**:
- Webhook URLs validated with `_safe_webhook_url` (HTTPS only, external hosts only)
- No internal IP ranges allowed (RFC 1918 blocked)
- Numeric IP encoding bypass fixed (AI_NUMERICHOST)
- See `docs/operations/ENFORCEMENT.md`

### T3: Location Data Leak

**Severity**: Medium
**Description**: Device location data is exposed through the dashboard, logs, or cloud publisher.
**Impact**: Privacy violation, physical security risk.
**Mitigation**:
- Location data stays local by default
- Cloud publisher uses only demo/synthetic data
- Dashboard requires authentication for location details
- No location in logs by default

### T4: Policy Bypass via Geofence Manipulation

**Severity**: Medium
**Description**: An attacker manipulates geofence definitions or device location to bypass policy enforcement.
**Impact**: Security policy ineffective, unauthorized access.
**Mitigation**:
- Geofence definitions require admin privileges to modify
- Risk engine uses multiple signals (not just location)
- Enforcement mode requires explicit opt-in
- Audit log of all policy changes

### T5: Denial of Service via Large Device fleets

**Severity**: Low
**Description**: A large device fleet causes performance degradation or resource exhaustion.
**Impact**: Slow dashboard, delayed sync, potential crash.
**Mitigation**:
- Pagination in all UEM adapters
- Rate limiting awareness
- Dry-run mode for testing
- Configurable sync intervals

### T6: Supply Chain Attack via Dependencies

**Severity**: Medium
**Description**: A malicious dependency is introduced via pip install.
**Impact**: Code execution, data exfiltration.
**Mitigation**:
- `pip-audit` in CI checks for known vulnerabilities
- CycloneDX SBOM generated in CI
- Stdlib-first approach minimizes dependencies
- No external web frameworks (own HTTP server in saas_server.py)

### T7: Dashboard XSS via Device Name

**Severity**: Low
**Description**: A device with a maliciously crafted name (e.g., containing `<script>`) could execute JavaScript in the dashboard.
**Impact**: Session hijacking, data disclosure (though data is local).
**Mitigation**:
- CSP headers on dashboard
- Input sanitization in dashboard rendering
- Device names from UEM providers are treated as untrusted input

## Security Checklist

- [x] No secrets in config files by default (env vars preferred)
- [x] HTTPS for all external API connections
- [x] Webhook URL validation (HTTPS + external only)
- [x] No internal network access from adapters
- [x] Audit log for policy changes
- [x] RBAC for dashboard access
- [x] Dry-run mode for safe testing
- [x] Cloud publisher uses only demo data
- [x] CI secret scanning (gitleaks)
- [x] CI dependency audit (pip-audit + SBOM)
- [x] CSP headers on dashboard
- [x] No eval() or unsafe dynamic code execution

## Review History

- 2026-08-16: Centinela loop verified 8 Strix findings, 5 fixed, 2 mitigated, 1 accepted (TLS default valid)
- 2026-08-18: Centinela loop fixed SSRF bypass via numeric IP encoding
- 2026-08-20: Guardian loop fixed CI schema validation for cloud_state.json

## Related Documents

- [Security Disclosure Policy](https://github.com/adrimg3196/lucidfence/blob/main/SECURITY.md)
- [ENFORCEMENT.md](./ENFORCEMENT.md) — enforcement mode and safety guards
- [DAY2.md](./DAY2.md) — day 2 operations including backup and monitoring
- [PRODUCTION.md](./PRODUCTION.md) — production deployment guide
