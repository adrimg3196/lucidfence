# LucidFence vs Microsoft Intune

> **Capability-by-capability comparison.** This page is not "we're better" —
> it is a structured, sourced comparison of what each tool does so you can
> decide where each fits. Every claim links to the internal doc that backs it.
> For the other vendor, see [LucidFence vs Jamf](lucidfence-vs-jamf.md).

## What each one is

**Microsoft Intune** is a cloud UEM (Unified Endpoint Management) in the
Microsoft 365 / Entra stack. It enrolls, configures, and manages devices and
applications, and drives [Conditional Access](../integrations/INTUNE.md) on the
Microsoft identity platform.

**LucidFence** is a **local-first control plane** that turns fleet geolocation
into *explainable risk* (a 0–100 score **with its reason**) and runs automated
actions — **MDM-agnostic** through adapters. It is not a replacement UEM: it
sits on top of the UEM you already run (Applivery, Intune, Jamf, Fleet, …) and
correlates everything on your own machine. See
[README.en.md](../README.en.md) and the root [README.md](../README.md).

> ⚠️ **Accuracy note (signed off by CTO, 2026-08-20).** The Intune and Jamf
> adapters run in **live mode** — they make real Microsoft Graph / Jamf API
> calls when credentials are configured, and only fall back to a mock path
> when *no token is present*. Older wording that said "mocks included" was
> outdated; the corrected framing is the one used here. Source:
> [`lucidfence/core/adapters/__init__.py`](https://github.com/adrimg3196/lucidfence/blob/main/lucidfence/core/adapters/__init__.py)
> (line ~94, "Intune/Jamf: … mock if no token") and
> [operations/RUNBOOK.md](../operations/RUNBOOK.md) (Intune = `live mode`).

## Capability table

| Capability | Microsoft Intune | LucidFence | Source |
|---|---|---|---|
| Core purpose | Cloud UEM + device/app management + Conditional Access | Local-first geofence + explainable-risk control plane (MDM-agnostic) | [README.en.md](../README.en.md), [README.md](../README.md) |
| Geofencing engine | Commodity "inside/outside" only | Geofences + risk engine with reasons; policies as code | [README.en.md](../README.en.md), [operations/config_as_code.md](../operations/config_as_code.md) |
| **Location data fidelity** | `locateDevice` is point-in-time, for lost/supervised devices; Graph exposes **no continuous fleet location stream** | Uses Intune for *acting*; pairs with a real location source (Applivery GPS, iOS on-device, or network/osquery) for continuous geofencing | [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md), [integrations/INTUNE.md](../integrations/INTUNE.md) |
| Explainable risk (0–100 + reason) | Not provided (no risk score with reason) | Every device gets a 0–100 score **with the reason** — never a magic number | [README.en.md](../README.en.md) |
| Data sovereignty / no exfiltration | Vendor cloud holds fleet location & data | Local-first: location/data **never leave your infrastructure** (only egress you configure) | [README.en.md](../README.en.md), [README.md](../README.md) |
| MDM-agnostic / multi-UEM | Locked to the Microsoft ecosystem | Correlates a mixed fleet (Applivery + Intune + Jamf + Fleet) in one risk map | [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md) |
| Remote actions (lock/wipe/message/locate/reboot/clear_passcode) | Native (Graph `PrivilegedOperations.All`) | Adapter executes the same actions via Graph; dry-run in `observe` | [integrations/INTUNE.md](../integrations/INTUNE.md), [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Compliance & Conditional Access | Native, first-class (Entra/CA) | `set_compliance` → PATCH `isCompliant` via Graph; degrades honestly if Graph rejects | [integrations/INTUNE.md](../integrations/INTUNE.md) |
| Apple DDM declarative | Via Apple ecosystem / partner | Generates Apple DDM declarations; **DDM does not geolocate** (trigger stays in the engine) | [operations/apple_ddm.md](../operations/apple_ddm.md) |
| On-device (iOS) & logical (network) geo options | Not a geofencing location source | iOS on-device CoreLocation (privacy) + network/osquery logical geo | [integrations/IOS_ONDEVICE.md](../integrations/IOS_ONDEVICE.md), [integrations/NETWORK_LOCATION.md](../integrations/NETWORK_LOCATION.md) |
| Safe rollout (observe→enforce, double-key wipe) | CA policies, manual | `observe` default, action gating, `wipe` needs double key (opt-in + allowlist) | [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Deployment / licensing | SaaS (Microsoft 365 subscription) | Self-hosted, Apache-2.0, **no telemetry, no accounts, free** | [README.en.md](../README.en.md), [README.md](../README.md) |

## Where Intune clearly wins

We are explicit about this — it is what makes the comparison citable rather
than marketing:

- **Native Microsoft 365 / Entra / Conditional Access.** Intune is *the* MDM
  for the Microsoft identity platform; `set_compliance` and CA are first-class
  and need no glue. LucidFence drives CA *through* Intune, it does not replace
  it ([INTUNE.md](../integrations/INTUNE.md)).
- **Zero extra agent on Windows.** Intune manages Windows out of the box as
  part of the Microsoft stack; LucidFence is an added control layer you run
  yourself.
- **Mature, vendor-supported UEM.** Full device lifecycle, app distribution,
  OS/update management, co-management with Configuration Manager, SLAs, and a
  large admin community — far beyond a focused geofence/risk plane.
- **Broad enterprise adoption & compliance certifications** backed by
  Microsoft, which matters for procurement and legal review.

**Use both:** Intune as your Microsoft UEM, LucidFence on top for
local-first geofence risk, explainable scoring, and a safe observe→enforce
rollout that acts through Intune's own API
([MULTI_UEM.md](../integrations/MULTI_UEM.md)).

## Where LucidFence is a different bet

- **Local-first sovereignty.** Your fleet's location and data never leave your
  infrastructure; no vendor cloud, no telemetry. Intune's data lives in the
  Microsoft cloud by design ([README.en.md](../README.en.md)).
- **Explainable risk, not a black box.** Every device gets a 0–100 score *with
  the reason*; Intune does not provide a risk score with rationale
  ([README.en.md](../README.en.md)).
- **MDM-agnostic.** One risk plane across a mixed fleet (Applivery + Intune +
  Jamf + Fleet) instead of per-vendor silos
  ([MULTI_UEM.md](../integrations/MULTI_UEM.md)).
- **Honest location matrix.** LucidFence documents exactly what location each
  UEM *actually* yields and tells you when continuous geofencing on Intune
  location alone is not feasible ([LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md)).

## The moat (corrected)

Recycled from [README.en.md § Why](../README.en.md) with the adapter claim
**corrected** (Intune/Jamf are live adapters, not bundled mocks):

| | Native MDM (Intune) | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| **Explainable risk** (0–100 + reason) | ❌ black box | ✅ score + `reasons` |
| **No location exfiltration** | ❌ (vendor cloud) | ✅ local-first |
| MDM-agnostic | ❌ locked to yours | ✅ via adapters |
| SOAR + live CVE + on-demand commands | partial | ✅ |

## Deep links

- Intune onboarding: [integrations/INTUNE.md](../integrations/INTUNE.md)
- Location reality per UEM: [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md)
- Mixed fleet: [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md)
- Safe rollout: [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md)
- Other vendor: [LucidFence vs Jamf](lucidfence-vs-jamf.md)
