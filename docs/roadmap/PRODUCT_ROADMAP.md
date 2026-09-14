# LucidFence Product Roadmap

This roadmap outlines the evolution of LucidFence as a local-first, privacy-preserving, zero-telemetry multi-UEM geofencing and explainable risk platform.

## Horizons

### NOW (Current Releases)
- **LucidFence 2.0 Core Architecture (Go Single Binary)**:
  - Local-first runtime with embedded SPA dashboard (`internal/web`).
  - Core domain models: geofences, routes, POIs, risk evaluation, incident lifecycles, and playbooks.
  - Multi-UEM adapter integration (Applivery, Intune, Jamf, Fleet, Workspace ONE).
  - Webhook, ntfy, and OCSF notifications with egress allowlist enforcement.

### NEXT
- Enhanced posture signals integration (expanded osquery queries and device health vectors).
- Multi-organization RBAC and fine-grained API token scoping.
- Advanced CSV/GeoJSON analytical exports and reporting automation.

### LATER
- Native desktop agent daemon integrations for real-time local location hardware attestation.
- Expanded declarative policy generation across Linux (systemd-networkd / firewalld) and MacOS (DDM declarative profiles).

### EXPLORE (NOVA Visionary Proposals for Hermes)
The following visionary features represent high-impact, futuristic capabilities under active discovery. They strictly respect LucidFence's local-first, zero-telemetry, and Apache-2.0 core principles while unlocking unprecedented zero-trust perimeter security:

1. **P2P Mesh Proximity Attestation (`EXPLORE-P2P-01`)**:
   - Device-to-device Bluetooth LE / Wi-Fi Direct peer attestation to validate location consensus without central cloud GPS dependence.
2. **Autonomous Self-Healing SOAR Engine (`EXPLORE-SOAR-02`)**:
   - On-device local ML risk drift detection that auto-proposes preventative non-destructive containment playbooks before geofence violations occur.
3. **Quantum-Safe Audit Ledger (`EXPLORE-CRYPTO-03`)**:
   - Append-only Merkle tree audit log signed with post-quantum algorithms (Dilithium/Kyber) to guarantee tamper-proof evidence chains during regulatory audits.
4. **Air-Gapped Store-and-Forward Mesh Telemetry (`EXPLORE-AIRGAP-04`)**:
   - Disconnected local buffer and store-and-forward mesh routing for military/high-security air-gapped environments.
5. **Universal Multi-UEM Policy Synthesizer (`EXPLORE-SYNTH-05`)**:
   - Declarative policy compiler translating high-level intent into native Apple DDM, Windows DSC, Android AMAPI, and Fleet osquery specs with automated conflict detection.

---
*For detailed discovery specifications, see `docs/product/2026-09-visionary-features.md`.*
