# Proposal 01: Zero-Knowledge Location Attestation (ZK-Geofence)

**Status:** Proposed (EXPLORE Horizon)
**Author:** Visionary Product Architect
**Target Engine:** Hermes / LucidFence 2.0+

## 1. Context & Motivation

Current enterprise geofencing tools face a severe privacy dilemma: to enforce location compliance, administrators typically demand raw GPS coordinates, Wi-Fi BSSID dumps, or invasive telemetry. In privacy-conscious, local-first environments or jurisdictions governed by strict privacy laws (e.g., GDPR, CCPA), employees resist exfiltrating fine-grained location tracking.

LucidFence solves this locally on the server/agent, but enterprise compliance auditors often require cryptographic proof that a device was strictly inside or outside a sanctioned geographic perimeter without ever storing or revealing the exact $(x, y)$ coordinate.

## 2. Solution Overview

**ZK-Geofence** generates Zero-Knowledge proofs (zk-SNARKs / zk-STARKs) directly on the local agent or device runtime.
- **Public Inputs:** Fence Polygon Hash $H(\mathcal{P})$, Boundary Threshold $\epsilon$, Timestamp $T$.
- **Private Inputs (Witness):** Raw GPS Coordinates $(lat, lng)$, Signal Triangulation Data.
- **Proof Output:** $\pi = \text{ZK-Proof}(\text{PointInPolygon}(lat, lng, \mathcal{P}) == 1)$.

LucidFence verifies $\pi$ in $\mathcal{O}(1)$ time. The administrator receives undeniable mathematical attestation that the device complies with perimeter rules while the exact coordinate remains cryptographically private.

## 3. Architectural Design

```
+------------------------------------+
| Local Edge Runtime / Device Agent  |
|                                    |
| [GPS / BSSID] ---> [ZK Prover]     |
|                        |           |
|                  (Witness: lat,lng)|
+------------------------|-----------+
                         | Proof (\pi)
                         v
+------------------------------------+
| LucidFence Engine (`internal/domain`)
|                                    |
| [ZK Verifier]                      |
|   Inputs: H(Fence), Timestamp, \pi  |
|   Result: Compliant / Non-Compliant|
+------------------------------------+
```

## 4. Key Features & Capabilities

1. **Zero Raw Coordinate Storage**: Zero-knowledge verification means database/JSON store never holds raw coordinates for sensitive tenant roles.
2. **Deterministic Verification**: Fast, Go stdlib / Go-WASM verifier embedded directly in `internal/domain/geo`.
3. **Audit Evidence Export**: Generates cryptographically signed OCSF Detection Findings containing proof hash $\pi$ for auditor verification.

## 5. Non-Goals

- Replacing local GPS sensors or UEM location APIs. ZK-Geofence consumes raw location data locally and produces verifiable proofs.
- Storing proofs on a public blockchain. Verification remains strictly local-first and zero-telemetry.
