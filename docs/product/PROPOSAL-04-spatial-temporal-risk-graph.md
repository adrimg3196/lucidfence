# Proposal 04: Spatial-Temporal Risk Graph & Impossible Velocity Anomaly Engine

**Status:** Proposed (EXPLORE Horizon)
**Author:** Visionary Product Architect
**Target Engine:** Hermes / LucidFence 2.0+

## 1. Context & Motivation

Static geofencing evaluates devices against fixed geographic polygons. However, sophisticated threat actors bypass traditional checks through spoofing or token theft across locations that pass simple boundary checks independently, but are impossible when evaluated temporally (e.g., check-in in Madrid at 10:00 AM and check-in in Tokyo at 11:00 AM).

## 2. Solution Overview

**Spatial-Temporal Risk Graph** constructs a local, privacy-preserving graph of spatial-temporal transitions:
- **Velocity Vector Calculation:** Evaluates Great Circle (Haversine) distance over time interval $\Delta t$:
  $$v = \frac{\text{haversine}(P_1, P_2)}{\Delta t}$$
- **Teleportation Detection:** Flags velocity $v > v_{\max}$ (e.g., $900\text{ km/h}$ for commercial aviation) as immediate location spoofing or account compromise.
- **Dwell Anomaly Matrix:** Models statistical likelihood of device presence in specific zones based on historical shift schedules, departmental norms, and temporal clusters.

## 3. Key Capabilities

1. **Pure Domain Function:** Zero-I/O implementation extending `internal/domain/integrity` and `internal/domain/risk`.
2. **Deterministic Risk Signal:** Outputs `signal:integrity.impossible_velocity` and `signal:temporal.off_hours_cluster` for policy matching.
3. **Local Graph Storage:** Efficiently serialized in `store` without external graph databases or third-party cloud services.
