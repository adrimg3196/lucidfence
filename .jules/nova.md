# Product Discovery & Visionary Learnings: NOVA

## Visionary Architecture Principles
1. **Zero-Knowledge Privacy First:** Geofencing should evolve to verify spatial location without ever recording raw GPS coordinates in logs or stores. ZK-SNARKs enable true privacy-preserving compliance for strict European regulatory environments.
2. **Offline Mesh Resilience:** Defense against GPS jamming/spoofing requires peer-to-peer verification (UWB, BLE, Wi-Fi Direct) where nearby devices validate each other's physical presence.
3. **Post-Quantum Integrity:** Audit evidence must remain tamper-proof in the quantum era by utilizing NIST-standardized algorithms (ML-DSA / Crystals-Dilithium) anchored in hardware chips (TPM 2.0 / Secure Enclave).
4. **Autonomous AI Threat-Hunting:** Machine learning and agentic workflows should analyze micro-anomalies and auto-synthesize rules and playbooks for human approval rather than requiring manual rule drafting.
5. **Cyber-Physical Convergence:** Digital risk state and physical access control must be unified. Devices exceeding risk boundaries must trigger automated physical access revocations (OSDP/Wiegand/MQTT).

## Directives for Hermes Implementation
- Keep code additions strictly modular within Go packages (`internal/domain/`).
- Preserve single-binary static Go distribution with embedded React UI.
- Maintain zero-telemetry and local-first execution.
