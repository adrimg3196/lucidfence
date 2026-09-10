# LucidFence Product Roadmap

This document outlines the strategic product roadmap for LucidFence across execution horizons.

---

## Horizon Overview

```
+-------------------------------------------------------------------------+
| NOW (LucidFence 2.0 Go Rewrite M1-M5)                                    |
| Single static Go binary, React dashboard, local-first engine, multi-UEM |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| NEXT (Post-2.0 Multi-Tenant & Granular Enforcement)                      |
| Enterprise RBAC extensions, OIDC federation, advanced report formats    |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| LATER (High-Availability & Edge Performance)                            |
| Peer-to-peer sync, multi-region local store replicas, hardware enclave   |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
| EXPLORE (NOVA Product Discovery Proposals)                              |
| Visionary features for agentic implementation (Hermes / AI agents)       |
+-------------------------------------------------------------------------+
```

---

## 1. NOW: LucidFence 2.0 Go Rewrite (Milestones M0 – M5)

- **M0 (Day 0 Cutover):** Clean cutover from legacy Python codebase to single Go binary architecture.
- **M1 (Core Engine & Simulation):** Core geometry domain, JSON/JSONL store, evaluation engine, simulated fleet, and React SPA embedded UI.
- **M2 (Risk & Actions):** Policy matching, risk verdict engine, guardrails (observe by default, live allowlist, double-key wipe), webhooks, OCSF findings, SOAR playbooks & handoffs.
- **M3 (UEM Adapters):** Live connectors for Applivery, Microsoft Intune, Jamf Pro, Fleet, and VMware Workspace ONE; osquery posture ingestion and NVD CVE matching.
- **M4 (Reports & Full Auth):** Executive reports, evidence vault with offline hash verification, RBAC (owner, admin, operator, viewer, auditor), API keys, OIDC, MCP server.
- **M5 (Public Launch & Distribution):** Landing page, showcase website, Homebrew tap, Docker images, GoReleaser artifacts.

---

## 2. NEXT: Enterprise Multi-Tenant & Granular Policy

- **Multi-Tenant Isolation Enhancements:** Organization-level resource quotas and custom egress allowlist scoping.
- **Enhanced OIDC Role Mapping:** Dynamic group-to-role mappings from Identity Providers (Azure AD / Entra ID, Okta, Keycloak).
- **Custom Report Designer:** User-defined HTML/CSV report templates with scheduled delivery via ntfy/webhook.

---

## 3. LATER: Scaled Local-First Architecture

- **Air-Gapped Replicas:** Local JSON/JSONL store streaming replication between failover nodes using local mutual TLS.
- **Hardware Enclave Signatures:** Hardware-backed signature keys (TPM / Secure Enclave) for audit logs and evidence exports.

---

## 4. EXPLORE: NOVA Product Discovery Proposals (For Hermes Agentic Execution)

The `EXPLORE` horizon houses visionary, ultra-necessary feature proposals designed to push local-first, privacy-preserving geofencing to the technological frontier. These proposals are ready for future agentic implementation:

1. **PROPOSAL-01: Zero-Knowledge Location Attestation (ZK-Geofence)**
   - *File:* `docs/product/PROPOSAL-01-zk-location-attestation.md`
   - *Goal:* Generates zero-knowledge proofs on endpoint devices to attest compliance zone presence without exfiltrating raw coordinates.

2. **PROPOSAL-02: Autonomous Air-Gap Drift Remediation & Offline Policy Enforcer**
   - *File:* `docs/product/PROPOSAL-02-autonomous-drift-remediation.md`
   - *Goal:* Predictive directional trajectory modeling that pre-caches offline enforcement triggers for endpoints approaching unauthorized boundaries in signal dead zones.

3. **PROPOSAL-03: Multi-UEM Consensus Mesh & Cross-Adapter Trust Synthesis**
   - *File:* `docs/product/PROPOSAL-03-cross-uem-consensus-mesh.md`
   - *Goal:* Synthesizes divergent telemetry across Intune, Jamf, Fleet, Applivery, and Workspace ONE into a Byzantine-fault-tolerant trust score.

4. **PROPOSAL-04: Spatial-Temporal Risk Graph & Impossible Velocity Engine**
   - *File:* `docs/product/PROPOSAL-04-spatial-temporal-risk-graph.md`
   - *Goal:* Extends `internal/domain/integrity` to detect location spoofing and impossible velocity travels across temporal check-ins.
