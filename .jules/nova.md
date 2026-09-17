# NOVA Discovery Learnings & Agent Insights

This document captures critical product discovery learnings, architectural insights, and considerations for Hermes and autonomous implementation agents working on LucidFence 2.0.

---

## Key Learnings & Architectural Insights

1. **Zero-Knowledge Privacy as a Competitive Moat:**
   - Privacy regulations (GDPR, EU AI Act, works council mandates) make employees and enterprises averse to continuous GPS tracking.
   - Moving from "raw location telemetry" to ZK-SNARK proof verification (`internal/domain/zkp`) allows LucidFence to offer 100% mathematical privacy without sacrificing security enforcement.

2. **Offline Mesh Resilience:**
   - Single-point-of-failure GPS/Cellular reliance creates vulnerabilities against jamming and subterranean operations.
   - Dynamic P2P mesh validation using BLE/UWB allows neighboring fleet devices to act as distributed trust anchors without cloud or internet roundtrips.

3. **Post-Quantum Cryptography & Secure Enclave Hardware Binding:**
   - Quantum-resistant signature algorithms (ML-DSA / Crystals-Dilithium) combined with hardware-backed TPM 2.0 / Apple Secure Enclave quotes eliminate the risk of location proof forgery and kernel spoofing.

4. **Preserving Local-First Principles:**
   - Every visionary feature must strictly adhere to the LucidFence core principles:
     - Single binary execution in Go.
     - Local-first data storage (JSON/JSONL).
     - Zero exfiltration/telemetry.
     - Open source (Apache-2.0).
     - Strict safety guardrails (Observe-by-default, dry-run mode, double-key wipe).

---

## Guidelines for Hermes Execution

- When implementing features from the `EXPLORE` horizon:
  1. Define pure domain types and interfaces under `internal/domain/` with zero I/O side effects.
  2. Implement local state management and atomic file persistence in `internal/store/`.
  3. Wire logic through `internal/engine/` respecting existing guardrails (`engine/guardrails.go`).
  4. Ensure claims are verified via unit tests and live execution checks in `internal/battery/`.
