# 🗺️ LucidFence Strategic Product Roadmap

## Roadmap Governance Principles

- **Value-Driven Horizons:** The roadmap outlines how LucidFence increases user value and security posture, not just a list of feature requests.
- **Horizon Definitions:**
  - **NOW:** Validated, approved, scoped, and actively undergoing development.
  - **NEXT:** High strategic priority with validated demand; pending resource allocation or final UI design.
  - **LATER:** High-value medium/long-term bets dependent on earlier core capabilities.
  - **EXPLORE:** Promising discovery hypotheses undergoing feasibility analysis, simulation design, or user interviews.
  - **PARKED:** Reviewed ideas that are duplicated, premature, or lacking sufficient evidence.
- **Human Approval Requirement:** No proposal automatically moves into `NOW` or `COMMITTED` without explicit human product owner sign-off.

---

## Strategic Horizons

### 🟢 NOW (Committed & Active)
- **LucidFence 2.0 Core Architecture & Engine:** Single Go binary, embedded React 19 dashboard, local JSON/JSONL store, local-first zero telemetry.
- **Multi-UEM Connectors (M3 Milestone):** Native connectors for Applivery, Microsoft Intune, Jamf Pro, Fleet, and VMware Workspace ONE.
- **Risk Engine & Guardrails:** Explicable 0-100 risk scoring, dry-run observe mode by default, double-key wipe protections.

### 🟡 NEXT (Validated Opportunities)
- **SOAR Automated Playbooks & Handoffs:** Gate-kept human approvals for high-impact destructive remediations.
- **osquery Posture Enriched CVE Telemetry:** Local osquery result parsing and NVD CVE vulnerability caching.

### 🔵 LATER (Medium-Term Strategic Expansion)
- **Self-Healing Device Geofence Re-Enrolment:** Automated policy state reconciliation when UEM agents lose sync.
- **Evidence Package Chain-of-Custody Exporter:** Offline verifiable hash chain export for regulatory compliance audits (NIS2 / RGPD).

### 🟣 EXPLORE (Product Discovery & Hypotheses)
- **✨ LucidFence FlightDeck: Pre-Flight Policy Blast-Radius & Impact Twin**
  - *Proposal Document:* `docs/product/lucidfence-flightdeck-blast-radius.md`
  - *Hypothesis:* Deterministic historical re-evaluation of proposed geofence/risk policy changes against `events.jsonl` will eliminate "Blast-Radius Anxiety", boosting `enforce` mode adoption from 22% to 70%+.
  - *Status:* Discovery / EXPLORE.

### 🔴 PARKED
- *Generic AI Chatbot Assistant:* Rejected. Lacks concrete operational automated work; LucidFence prioritizes deterministic decision explanations over generic text interfaces.
