# NOVA Product Discovery & Hermes Execution Learnings

## Core Directives for Agent Hermes

1. **Zero External Telemetry Guarantee:**
   - Any ONNX/WASM ML model introduced for spatial anomaly detection must execute strictly locally inside the Go binary or client process.
   - GPS coordinates and raw location data must never leave the local environment under any circumstance.

2. **OCSF Compliance:**
   - All generated risk verdicts and spatial anomalies must conform to the OCSF (Open Cybersecurity Schema Framework) standard established in `internal/notify/ocsf.go`.

3. **Multi-Platform Network Isolation:**
   - Air-gap isolation routines should leverage eBPF on Linux/macOS and WFP (Windows Filtering Platform) on Windows without requiring heavy external daemon dependencies.

4. **Post-Quantum Cryptography:**
   - PQ signature validation should utilize standard Go PQC packages (`golang.org/x/crypto/...` or hardware TPM / Secure Enclave APIs) with fallback to classical signature attestation for legacy systems.
