# LucidFence 2.0 — Product Roadmap

This document outlines the product evolution and feature pipeline for LucidFence 2.0, categorized into three strategic horizons: **NOW**, **NEXT**, and **EXPLORE**.

---

## Strategic Horizons Overview

```
+-----------------------------------+-----------------------------------+-----------------------------------+
|               NOW                 |               NEXT                |              EXPLORE              |
|        (Core Delivery)            |        (Enterprise & Auth)        |         (NOVA Discovery)          |
+-----------------------------------+-----------------------------------+-----------------------------------+
| • Single Go binary architecture   | • Executive & Evidence Reports    | • ZK-Privacy Geofencing (ZK-Fence)|
| • Explaining Risk Motor (0-100)   | • Multi-tenant RBAC & OIDC        | • Dynamic P2P Mesh Geofencing     |
| • Guardrails & Action Dedupe      | • Local-first MCP Server          | • Post-Quantum Location Attest    |
| • Live UEM Adapters               | • Public Showcase & Landing       | • Autonomous Threat-Hunting AI    |
| • React 19 + TypeScript Dashboard | • Systemd / Launchd Services      | • Spatio-Temporal Telemetry Fusion|
|                                   |                                   | • IoT Physical Access GateKeeper  |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

---

## 1. Horizon: NOW (M1 - M3)

Focus: High-performance Go rewrite, multi-UEM engine, safety guardrails, and responsive dashboard.

- [x] **Go Single Binary Architecture:** Static binary (`CGO_ENABLED=0`) embedding React frontend assets (`embed.FS`).
- [x] **Explicable Risk Engine:** 0-100 risk verdict with clear textual reasons and signal producers.
- [x] **Action Guardrails & Cooldowns:** Observe-by-default execution, dry-run mode, and double-key wipe protections.
- [x] **Multi-UEM Adapters:** Connectors for Applivery, Microsoft Intune, Jamf Pro, Fleet REST, and Workspace ONE.
- [x] **Modern React 19 Frontend:** Tailwind v4, MapLibre GL, and shadcn UI components.

---

## 2. Horizon: NEXT (M4 - M5)

Focus: Compliance reporting, audit capabilities, authentication, and distribution.

- [ ] **Compliance & Audit Reports:** Blind spots coverage, UEM second-opinion, and cryptographically verifiable evidence reports.
- [ ] **Multi-Tenant RBAC & OIDC:** Granular role matrix (`owner`, `admin`, `operator`, `viewer`, `auditor`) and generic OIDC SSO support.
- [ ] **Model Context Protocol (MCP):** Read-only local MCP server via stdio for AI agent queries.
- [ ] **Public Showcase & Documentation:** Static site generator for interactive showcase and multi-language manuals.
- [ ] **GoReleaser Pipeline:** Cross-platform static builds, Homebrew tap integration, and Docker distroless images.

---

## 3. Horizon: EXPLORE (NOVA Product Discovery)

Focus: Visionary, ultra-necessary next-generation features for future development by Hermes.

### [NOVA-01] Zero-Knowledge Privacy Geofencing (ZK-Fence)
- **Concept:** Mathematically prove that a device resides within an authorized geofence polygon using ZK-SNARKs without ever transmitting or storing raw GPS latitude/longitude.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-01-zero-knowledge-privacy-geofencing-zk-fence`

### [NOVA-02] Dynamic P2P Mesh Geofencing (MeshFence)
- **Concept:** Peer-to-peer ad-hoc proximity validation using BLE/UWB/Wi-Fi Direct to maintain geofence validity during GPS jamming or internet connectivity loss.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-02-dynamic-p2p-mesh-geofencing-meshfence`

### [NOVA-03] Post-Quantum Location Attestation (PQ-Attest)
- **Concept:** NIST post-quantum digital signatures (ML-DSA / Crystals-Dilithium) combined with TPM 2.0 / Apple Secure Enclave quotes for tamper-proof location evidence.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-03-post-quantum-location-attestation-pq-attest`

### [NOVA-04] Autonomous Threat-Hunting & Auto-Playbook AI Engine
- **Concept:** Local agentic engine that analyzes spatial-temporal fleet anomalies and automatically synthesizes policy rules and SOAR playbooks with 1-click approval.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-04-autonomous-threat-hunting--auto-playbook-ai-engine`

### [NOVA-05] Spatio-Temporal Anomaly & Hardware Telemetry Fusion
- **Concept:** Correlate micro-movements, gyroscope, thermal degradation, battery health, and physical travel speed limits to detect device cloning or SIM swapping.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-05-spatio-temporal-anomaly--hardware-telemetry-fusion`

### [NOVA-06] Physical Access Control & IoT GateKeeper Bridge
- **Concept:** Local-first physical security integration (OSDP/Wiegand/MQTT) to automatically revoke facility NFC badges and door access when geofences or risk conditions are violated.
- **Reference:** `docs/product/2026-09-10-visionary-roadmap-proposal.md#nova-06-physical-access-control--iot-gatekeeper`
