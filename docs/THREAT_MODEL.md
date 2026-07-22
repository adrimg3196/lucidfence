# LucidFence threat model

## Scope and assets

Assets: tenant location trails, device inventory, credentials, API keys, SOAR secrets, audit evidence and remediation authority. LucidFence is local-first; external adapters and explicitly configured webhooks are the only intended egress.

## Trust boundaries

1. Browser ↔ loopback HTTP server: authenticated HttpOnly session, SameSite strict, host validation and rate limiting.
2. Server ↔ tenant data directory: organization-specific paths, atomic writes and restrictive permissions.
3. Server ↔ UEM provider: opt-in credentials, TLS endpoint validation, dry-run by default.
4. SOAR caller ↔ webhook: tenant-specific HMAC, timestamp freshness and replay protection.
5. CI/repository: gitleaks, dependency audit, hash-locked dependencies and CycloneDX SBOM.

## STRIDE analysis

| Threat | Control | Verification |
|---|---|---|
| Spoofing | Sessions, high-entropy API keys, HMAC webhook | auth/RBAC/HMAC tests |
| Tampering | Atomic state writes; hash-chained audit | tamper regression test |
| Repudiation | Actor, request ID, timestamp and chained hash | `/api/audit` JSON/CEF |
| Information disclosure | Tenant stores, masked secrets, generic HTTP 500 | isolation and secret scan |
| Denial of service | Rate limits, 1 MiB payload cap, bounded histories | security/perf tests |
| Elevation of privilege | Capability RBAC; owner-only key/roadmap mutation | RBAC E2E |

## Abuse cases and residual risks

- A local OS administrator can read process memory and tenant files. OS account isolation and disk encryption remain operator responsibilities.
- A configured UEM/webhook endpoint can observe explicitly transmitted payloads. SSRF checks and allowlisted HTTPS endpoints reduce this risk.
- Multi-process file storage is protected by atomic replacement but is not a distributed database. Run one active writer per shared data root unless using the cluster lease documented below.
- Predictive movement is explainable extrapolation, not safety-critical ML; impossible jumps produce confidence zero.

## Release security gate

Before release: full tests including Chromium; gitleaks; `pip-audit -r requirements.lock`; SBOM generation; Docker build when Docker is available; API auth regression; audit-chain verification; backup/restore exercise. External notarization and live UEM tests require operator-owned credentials and must never be simulated as PASS.
