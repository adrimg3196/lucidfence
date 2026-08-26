# LucidFence vs Kandji

> **Capability-by-capability comparison.** This page is not "we're better" —
> it is a structured, sourced comparison of what each tool does so you can
> decide where each fits. Every claim links to the internal doc that backs it.
> For the other vendors, see [LucidFence vs Intune](lucidfence-vs-intune.md)
> and [LucidFence vs Jamf](lucidfence-vs-jamf.md).

## What each one is

**Kandji** (rebranded to **Iru** in late 2025, now extending beyond Apple to
Windows/Android MDM) is an Apple-first UEM: device enrollment, inventory,
auto-remediation, and
smart templates for macOS/iOS, with a mature ecosystem and vendor support.

**LucidFence** is a **local-first control plane** that turns fleet geolocation
into *explainable risk* (a 0–100 score **with its reason**) and runs automated
actions — **MDM-agnostic** through adapters. It is not a replacement UEM: it
sits on top of the UEM you already run (Applivery, Intune, Jamf, Fleet, …
**and Kandji via the bring-your-own-UEM connector**) and correlates everything
on your own machine. See [README.en.md](../README.en.md) and the root
[README.md](../README.md).

> ⚠️ **Accuracy note (signed off by CTO, 2026-08-26 — mirrors the Intune/Jamf #203/#267 co-sign).** Two facts on this page are *vendor-side* and come from the SEO & Docs Bot's 2026 evidence review, not from LucidFence source code. The CTO verified both against `origin/main` (@ `1e6bfd3`) and co-signed them: the adapter registry (`lucidfence/core/adapters/__init__.py`, `ADAPTER_REGISTRY`) has **no `kandji` key** (keys: `simulation`, `applivery`, `intune`, `jamf`, `windows_conformidad`, `chromeos`, `workspace_one`, `fleet`) — so Kandji is reached via `GENERIC_HTTP` (and `docs/adapters/GENERIC_HTTP.md` names Kandji as a BYO example); and Kandji/Iru's "Lost Mode" is documented vendor *recovery* location, **not** geofencing/compliance-by-location (consistent with `docs/internal/product/BACKLOG.md` §6). The LucidFence-side claims remain verifiable from code/docs:
> 1. **Kandji has no native LucidFence adapter today** (the adapter registry
>    holds Applivery, Intune, Jamf, Fleet + chromeos/workspace_one/windows_conformidad). Kandji is reached through the
>    **GENERIC_HTTP** bring-your-own-UEM connector
>    ([adapters/GENERIC_HTTP.md](../adapters/GENERIC_HTTP.md)). This is a real
>    gap vs Intune/Jamf, stated honestly below.
> 2. **Kandji offers no geofencing / location-based compliance policy.** Its
>    only location feature is **"Lost Mode"** — on-demand device location for
>    *lost-device recovery*, not continuous fleet geofencing or risk-by-location
>    policy. Source: 2026 vendor docs reviewed by the bot.
>
> The LucidFence-side claims (local-first, explainable risk, no exfiltration,
> MDM-agnostic) are verifiable from the codebase and the docs linked below.

## Capability table

| Capability | Kandji | LucidFence | Source |
|---|---|---|---|
| Core purpose | Apple-first UEM (enrollment, inventory, auto-remediation, templates) | Local-first geofence + explainable-risk control plane (MDM-agnostic) | [README.en.md](../README.en.md), [README.md](../README.md) |
| Geofencing engine | **None** — only "Lost Mode" (on-demand lost-device location) | Geofences + risk engine with reasons; policies as code | [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md), [operations/config_as_code.md](../operations/config_as_code.md) |
| **Location data fidelity** | Lost Mode = point-in-time location for recovery; **no continuous fleet geofencing** | Pairs with a real location source (Applivery GPS, iOS on-device, or network/osquery) for continuous geo | [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md), [adapters/GENERIC_HTTP.md](../adapters/GENERIC_HTTP.md) |
| **Location-based compliance / risk policy** | Not provided (no geofence-triggered policy) | Geofence is a first-class risk signal; policies trigger on location + posture | [operations/config_as_code.md](../operations/config_as_code.md), [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Explainable risk (0–100 + reason) | Not provided (no risk score with reason) | Every device gets a 0–100 score **with the reason** — never a magic number | [README.en.md](../README.en.md) |
| Data sovereignty / no exfiltration | Vendor cloud (Kandji/Iru Cloud) holds fleet data | Local-first: location/data **never leave your infrastructure** | [README.en.md](../README.en.md), [README.md](../README.md) |
| MDM-agnostic / multi-UEM | Apple-centric (2026: expanding to Win/Android via Iru) | Correlates a mixed fleet (Applivery + Intune + Jamf + Fleet + generic UEM) in one risk map | [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md) |
| Native adapter today | — (no LucidFence Kandji adapter in registry) | Reach Kandji via **GENERIC_HTTP** bring-your-own-UEM connector | [adapters/GENERIC_HTTP.md](../adapters/GENERIC_HTTP.md) |
| Remote actions (lock/wipe/message/restart) | Native via Kandji automations | Via connector to Kandji's API; dry-run in `observe` | [adapters/GENERIC_HTTP.md](../adapters/GENERIC_HTTP.md), [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Apple DDM declarative | First-class Apple DDM | Generates Apple DDM declarations; **DDM does not geolocate** | [operations/apple_ddm.md](../operations/apple_ddm.md) |
| On-device (iOS) & logical (network) geo options | Not a geofencing location source | iOS on-device CoreLocation (privacy) + network/osquery logical geo | [integrations/IOS_ONDEVICE.md](../integrations/IOS_ONDEVICE.md), [integrations/NETWORK_LOCATION.md](../integrations/NETWORK_LOCATION.md) |
| Safe rollout (observe→enforce, double-key wipe) | Via Kandji automations/policies | `observe` default, action gating, `wipe` needs double key (opt-in + allowlist) | [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Deployment / licensing | Commercial SaaS/self-host (subscription) | Self-hosted, Apache-2.0, **no telemetry, no accounts, free** | [README.en.md](../README.en.md), [README.md](../README.md) |

## Where Kandji clearly wins

We are explicit about this — it is what makes the comparison citable rather
than marketing:

- **Apple device management depth.** Enrollment, inventory, configuration
  profiles, and DDM for macOS/iOS are Kandji's home turf — LucidFence consumes
  that posture, it does not replace it.
- **Auto-remediation & smart templates.** Kandji's templated automations reduce
  macOS/iOS toil out of the box; LucidFence does not attempt device lifecycle
  management.
- **Mature, vendor-supported UEM.** Full Apple device lifecycle, app
  distribution, patch/OS update management, SLAs, and a large admin community —
  far beyond a focused geofence/risk plane.
- **Expanding platform (2026).** The "Iru" rebrand opens Windows/Android MDM,
  broadening the fleet Kandji can natively cover.

**Use both:** Kandji as your Apple UEM, LucidFence on top (via the
GENERIC_HTTP connector) for local-first geofence risk, explainable scoring, and
a safe observe→enforce rollout that acts through Kandji's own API
([MULTI_UEM.md](../integrations/MULTI_UEM.md)).

## Where LucidFence is a different bet

- **Local-first sovereignty.** Your fleet's location and data never leave your
  infrastructure; no vendor cloud, no telemetry. Kandji's data lives in
  Kandji/Iru Cloud by design ([README.en.md](../README.en.md)).
- **Explainable risk, not a black box.** Every device gets a 0–100 score *with
  the reason*; Kandji does not provide a risk score with rationale
  ([README.en.md](../README.en.md)).
- **MDM-agnostic.** One risk plane across a mixed fleet (Applivery + Intune +
  Jamf + Fleet + Kandji) instead of per-vendor silos
  ([MULTI_UEM.md](../integrations/MULTI_UEM.md)).
- **The layer Kandji lacks: geofencing as risk.** Kandji gives you *Lost Mode*
  for recovery; LucidFence adds continuous geofence risk **on top** of Kandji —
  exactly the "geofencing layer over your UEM" positioning
  ([README.en.md](../README.en.md)).

## The moat (honest)

| | Native UEM (Kandji) | LucidFence |
|---|---|---|
| Geofencing | ❌ (Lost Mode only) | ✅ |
| **Explainable risk** (0–100 + reason) | ❌ black box | ✅ score + `reasons` |
| **No location exfiltration** | ❌ (vendor cloud) | ✅ local-first |
| MDM-agnostic | ❌ Apple-centric (expanding) | ✅ via adapters + GENERIC_HTTP |
| Geofence as a first-class risk signal | ❌ | ✅ |

## Deep links

- Bring-your-own UEM (Kandji): [adapters/GENERIC_HTTP.md](../adapters/GENERIC_HTTP.md)
- Location reality per UEM: [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md)
- Mixed fleet: [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md)
- Safe rollout: [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md)
- Other vendors: [LucidFence vs Intune](lucidfence-vs-intune.md), [LucidFence vs Jamf](lucidfence-vs-jamf.md)
