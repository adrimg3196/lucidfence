# LucidFence vs Microsoft Intune — Capability Comparison

This page compares LucidFence against Microsoft Intune on a capability-by-capability basis. Claims are co-signed by the CTO where they represent the project's position, and sourced to internal docs where applicable.

**Last updated:** 2026-09-01  
**Status:** Living document, updated as features ship or Intune's capabilities are verified

---

## What this is NOT

- Not a marketing attack on Intune
- Not a claim that LucidFence replaces Intune in every scenario
- Not a substitute for trying both and deciding for your context

This page is for operators who are evaluating alternatives and want honest, specific comparisons — not marketing blur.

---

## Capability matrix

| Capability | LucidFence | Microsoft Intune | Notes |
|------------|------------|-----------------|-------|
|| **Geofencing** | Yes — fully featured | Via Compliance Policies + Conditional Access (limited) | LucidFence: native geofence engine with radius, polygon, dwell-time. Intune: relies on CA policies triggered by location; less granular control. Source: [`integrations/LOCATION_MATRIX.md`](../integrations/LOCATION_MATRIX.md) |
| **Multi-UEM support** | Yes — designed for it | No — single vendor (Microsoft ecosystem) | LucidFence supports Applivery, Intune, Jamf, Fleet, and generic HTTP. Intune is a single-UEM solution. Source: [`lucidfence/core/multiuem.py`](../../lucidfence/core/multiuem.py) |
| **Local-first** | Yes — entire system runs on operator's machine | No — cloud-based management | LucidFence: no cloud dependency, offline-capable. Intune: requires Azure/AD connect. Source: [**Constitution Article I**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/CONSTITUTION.md) |
| **Cost at $0** | Yes — free, open source, Apache 2.0 | No — Intune is part of Microsoft 365 paid tiers | LucidFence: $0 for any fleet size. Intune: requires Microsoft 365 Business Premium or Enterprise. Source: [**Constitution Article II**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/CONSTITUTION.md) |
| **Open source** | Yes — Apache 2.0 | No — proprietary | LucidFence: code is inspectable, forkable, self-hostable. Source: [**Constitution Article III**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/CONSTITUTION.md) |
| **Credential handling** | Local, encrypted at rest, tenant-isolated | Cloud-stored, Microsoft-managed | LucidFence: credentials never leave the operator's machine. Intune: credentials are in Microsoft's cloud. Source: [**Constitution Article I**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/CONSTITUTION.md), [**Threat Model**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/THREAT_MODEL.md) |
| **Risk evaluation** | Yes — configurable, transparent | Yes — via Endpoint Analytics + compliance | LucidFence: risk is computed from explicit signals and configurable policies; you see why a device is flagged. Intune: risk scoring is more opaque. Source: [`lucidfence/core/policies.py`](../../lucidfence/core/policies.py) |
| **SOAR / workflows** | Yes — declarative playbooks | Limited — via automation scripts | LucidFence: SOAR playbooks with triggers, conditions, and actions. Intune: limited to Azure Automation / Logic Apps. Source: [`lucidfence/core/soar.py`](../../lucidfence/core/soar.py) |
| **Web dashboard** | Yes — local SPA | Yes — cloud console | LucidFence: dashboard runs locally at `localhost:8765`. Intune: console at `endpoint.microsoft.com`. |
| **Mobile agent (iOS)** | Yes — on-device geofencing | Yes — Intune Company Portal | LucidFence iOS agent: on-device geofencing without location exfiltration. Intune: Company Portal app provides similar but cloud-connected. Source: [`integrations/IOS_ONDEVICE.md`](../integrations/IOS_ONDEVICE.md) |
| **Windows support** | Yes — PowerShell DSC + agent | Yes — Intune client | LucidFence: Windows support via DSC and optional agent. Intune: native Windows support. Source: [`operations/windows_dsc.md`](../operations/windows_dsc.md) |
| **macOS support** | Yes — full | Yes — full | Both support macOS. LucidFence: macOS via Jamf, Intune, or Fleet adapters. |
| **Android support** | Yes — via adapters | Yes — via Intune | Both support Android. LucidFence: via Applivery or Intune adapter. |
| **Linux support** | Limited — via generic HTTP adapter | No — no Intune Linux client | LucidFence: Linux via generic HTTP adapter (operator provides endpoint). Intune: no Linux client. |
 Source: [**Privacy / data minimization**](https://raw.githubusercontent.com/adrimg3196/lucidfence/main/docs/architecture/CONSTITUTION.md) |
| **Custom policies (DSL)** | Yes — full policy DSL | Limited — via OMA-URI / custom config | LucidFence: policy DSL with operators, signals, actions. Intune: requires OMA-URI for custom configuration. Source: [`reference/POLICY_DSL.md`](../reference/POLICY_DSL.md) |
| **API / automation** | Yes — CLI + REST API | Yes — Microsoft Graph API | Both are automatable. LucidFence CLI is self-contained. Intune uses Graph API. |
| **Vendor lock-in** | No — open source, local data | Yes — tied to Microsoft ecosystem | LucidFence: leave anytime, take your data. Intune: hard to migrate away. |
| **API / automation** | Yes — CLI + REST API | Yes — Microsoft Graph API | Both are automatable. LucidFence CLI is self-contained. Intune uses Graph API. |
| **Vendor lock-in** | No — open source, local data | Yes — tied to Microsoft ecosystem | LucidFence: leave anytime, take your data. Intune: hard to migrate away. |

---

## Areas where LucidFence is stronger

1. **Multi-UEM fleets** — If you use more than one UEM (e.g., Jamf for Macs, Intune for Windows, Applivery for mobile), LucidFence is built for this. Intune is single-vendor.

2. **Local-first / air-gapped** — LucidFence runs entirely on your machine with no cloud dependency. This matters for classified environments, regulated industries, and operators who don't want their device data in a cloud.

3. **Cost** — LucidFence is $0 for any fleet size. Intune requires a paid Microsoft 365 tier.

4. **Transparency** — Risk scoring, policy evaluation, and SOAR playbooks are all inspectable. You see exactly why a device is flagged.

5. **Open source** — You can audit the code, fork it, self-host it, and modify it. Intune is a proprietary black box.

---

## Areas where Intune is stronger

1. **Microsoft ecosystem integration** — If you're already in the Microsoft 365 world (Azure AD, Entra ID, Defender), Intune integrates natively. LucidFence can use Intune as an adapter but doesn't have the same depth of AAD/Entra integration.

2. **Windows at scale** — Intune's Windows client is mature and widely deployed. LucidFence's Windows support is functional but less proven at huge scale.

3. **Compliance certifications** — Intune comes with Microsoft's compliance certifications (FedRAMP, HIPAA, etc.). LucidFence is self-hosted; the operator is responsible for their own compliance posture.

4. **Enterprise support** — Intune has Microsoft support channels. LucidFence relies on community support and the operator's own expertise.

5. **Device enrollment** — Intune has mature enrollment flows (especially with Autopilot). LucidFence relies on the underlying UEM's enrollment.

---

## When to choose LucidFence

- You have a multi-UEM fleet (more than one MDM/UEM solution)
- You want local-first, air-gapped, or data-sovereign operation
- You need $0 cost at any fleet size
- You want full transparency into risk evaluation and policy logic
- You're comfortable self-hosting and operating the system
- Open source is important to you

## When to choose Intune

- You're already deep in the Microsoft 365 / Entra ID ecosystem
- You need Microsoft's compliance certifications out of the box
- You want enterprise support from a vendor
- Your fleet is predominantly Windows and you want Autopilot
- You don't want to self-host or operate a local service

## When to use both

Many operators use Intune for Windows/Entra integration and LucidFence as the cross-UEM geofencing and risk layer. LucidFence's Intune adapter makes this straightforward — you get Intune's enrollment and Windows management, plus LucidFence's multi-UEM orchestration, geofencing, and transparent risk evaluation.

---

## Claims co-signed by CTO

The following claims have been reviewed and co-signed by the CTO:

1. **"LucidFence supports multi-UEM fleets natively"** — Verified in `lucidfence/core/multiuem.py` and the orchestrator tests.
2. **"LucidFence is $0 for any fleet size"** — Enforced by `loop_free_guard` in CI; no paid dependency is mandatory.
3. **"LucidFence is local-first, no cloud dependency"** — Constitution Article I; enforced by denylist in `loop-constraints.md`.
4. **"LucidFence has on-device iOS geofencing"** — iOS agent design documented in `integrations/IOS_ONDEVICE.md`.

---

*This page is part of the [comparisons](../README.md#comparativas) documentation. See also [LucidFence vs Jamf Pro](../comparisons/lucidfence-vs-jamf.md).*
