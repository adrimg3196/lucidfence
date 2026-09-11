# NOVA Product Discovery Learnings & Agentic Guidelines

This document logs critical architectural learnings, design trade-offs, and implementation principles for future agentic execution (Hermes / Jules) when implementing features from the `EXPLORE` horizon.

---

## 1. Core Architectural Invariants

When implementing proposals from `docs/product/` or tasks on `docs/roadmap/PRODUCT_ROADMAP.md`:

1. **Local-First & Zero-Telemetry:**
   - No feature may exfiltrate tenant location data, raw telemetry, or credentials to third-party servers or external services.
   - All risk evaluations, proofs, and store updates must occur locally within the LucidFence process or on-device agent.

2. **Domain Purity (`internal/domain`):**
   - Domain packages (`geo`, `fence`, `route`, `poi`, `device`, `integrity`, `risk`, `policy`, `action`, `transition`) must remain pure: **zero I/O, zero network calls, zero external dependencies**.
   - Calculations (like ZK verification or spatial-temporal velocity calculations) must be pure functions with deterministic outputs.

3. **Guardrails & Admin Sovereignty:**
   - All automated actions triggered by NOVA features must pass through `internal/engine/guardrails.go`.
   - The default mode must always remain `observe` (dry-run). Live actions require explicit enforcement configuration and live allowlist inclusion.
   - Destructive actions (`wipe`, `lock`) must respect double-key security (`allow_wipe` and `wipe_allowlist`) or generate human-in-the-loop handoffs.

4. **Multi-UEM Compatibility:**
   - Features must operate across all connected UEM adapters without assuming platform-specific APIs unless declared via `Adapter.Capabilities()`.

---

## 2. Feature Implementation Notes for Hermes

- **ZK-Geofence (PROPOSAL-01):**
  - Implement proof verification as a pure function in `internal/domain/geo` or `internal/domain/integrity`.
  - Ensure verification latency is $\le 5\text{ms}$ per device to avoid blocking the engine evaluation cycle.

- **Air-Gap Drift Remediation (PROPOSAL-02):**
  - Trajectory vectors belong in `internal/domain/integrity`.
  - Offline policy bundles must be encrypted at rest using local tenant keys.

- **Cross-UEM Consensus Mesh (PROPOSAL-03):**
  - Extend `internal/domain/risk` to calculate adapter agreement weights.
  - State discrepancies must be exposed via `signal:uem.disagreement_score` for policy evaluation.

- **Spatial-Temporal Risk Graph (PROPOSAL-04):**
  - Use Haversine distance calculations from `internal/domain/geo`.
  - Impossible velocity thresholds ($v_{\max}$) must be configurable per organization in `settings.json`.
