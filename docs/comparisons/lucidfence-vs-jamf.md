# LucidFence vs Jamf

> **Capability-by-capability comparison.** This page is not "we're better" —
> it is a structured, sourced comparison of what each tool does so you can
> decide where each fits. Every claim links to the internal doc that backs it.
> For the other vendor, see [LucidFence vs Intune](lucidfence-vs-intune.md).

## What each one is

**Jamf Pro** is a best-in-class Apple UEM: device enrollment, inventory,
configuration, and declarative management (DDM) for macOS/iOS, with a mature
ecosystem and vendor support.

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
> [operations/RUNBOOK.md](../operations/RUNBOOK.md) (Jamf = `live mode`).

## Capability table

| Capability | Jamf Pro | LucidFence | Source |
|---|---|---|---|
| Core purpose | Apple-focused UEM (enrollment, inventory, config, DDM) | Local-first geofence + explainable-risk control plane (MDM-agnostic) | [README.en.md](../README.en.md), [README.md](../README.md) |
| Geofencing engine | Commodity "inside/outside" only | Geofences + risk engine with reasons; policies as code | [README.en.md](../README.en.md), [operations/config_as_code.md](../operations/config_as_code.md) |
| **Location data fidelity** | **No continuous location by API** — excellent inventory & posture, but not a location source | Pairs Jamf with a real location source (Applivery GPS, iOS on-device, or network/osquery) for continuous geo | [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md), [integrations/JAMF.md](../integrations/JAMF.md) |
| Explainable risk (0–100 + reason) | Not provided (no risk score with reason) | Every device gets a 0–100 score **with the reason** — never a magic number | [README.en.md](../README.en.md) |
| Data sovereignty / no exfiltration | Vendor cloud (Jamf Cloud / your instance) holds fleet data | Local-first: location/data **never leave your infrastructure** | [README.en.md](../README.en.md), [README.md](../README.md) |
| MDM-agnostic / multi-UEM | Apple-centric (extends via partner integrations) | Correlates a mixed fleet (Applivery + Intune + Jamf + Fleet) in one risk map | [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md) |
| Remote actions (lock/wipe/message/reboot/clear_passcode) | Native via API role (e.g. `Send Mobile Device Remote Lock Command`) | Adapter executes the same actions via Jamf API; dry-run in `observe`; API role is a second line of defense | [integrations/JAMF.md](../integrations/JAMF.md), [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Compliance & Conditional Access | **No `set_compliance` API command** — degrades honestly; real path is Smart Groups + Jamf↔Microsoft compliance partner | N/A on Jamf (degrades with explanation); works natively on Intune | [integrations/JAMF.md](../integrations/JAMF.md) |
| Apple DDM declarative | First-class Apple DDM | Adapter supports `apply_ddm` / `ddm_status` / `ddm_sync` (degrades to imperative if unsupported); **DDM does not geolocate** | [integrations/JAMF.md](../integrations/JAMF.md), [operations/apple_ddm.md](../operations/apple_ddm.md) |
| On-device (iOS) & logical (network) geo options | Not a geofencing location source | iOS on-device CoreLocation (privacy) + network/osquery logical geo | [integrations/IOS_ONDEVICE.md](../integrations/IOS_ONDEVICE.md), [integrations/NETWORK_LOCATION.md](../integrations/NETWORK_LOCATION.md) |
| Safe rollout (observe→enforce, double-key wipe) | Manual / via policy | `observe` default, action gating, `wipe` needs double key (opt-in + allowlist) | [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md) |
| Deployment / licensing | Commercial SaaS/self-host (subscription) | Self-hosted, Apache-2.0, **no telemetry, no accounts, free** | [README.en.md](../README.en.md), [README.md](../README.md) |

## Where Jamf clearly wins

We are explicit about this — it is what makes the comparison citable rather
than marketing:

- **Best-in-class Apple management.** Inventory, posture, configuration
  profiles, and DDM for macOS/iOS are Jamf's home turf — LucidFence consumes
  that posture, it does not replace it ([JAMF.md](../integrations/JAMF.md)).
- **Native Apple DDM delivery.** Jamf is a primary DDM channel; LucidFence's
  adapter builds the declarations and Jamf delivers them
  ([JAMF.md](../integrations/JAMF.md),
  [apple_ddm.md](../operations/apple_ddm.md)).
- **Mature, vendor-supported UEM.** Full Apple device lifecycle, app
  distribution, patch/OS update management, SLAs, and a large admin community.
- **Smart Groups + compliance partner ecosystem.** Jamf's real
  compliance mechanism is Smart Groups and the Jamf↔Microsoft compliance
  partner — the correct path for Conditional Access on a Jamf Mac
  ([JAMF.md](../integrations/JAMF.md)).

**Use both:** Jamf as your Apple UEM, LucidFence on top for local-first
geofence risk, explainable scoring, and a safe observe→enforce rollout that
acts through Jamf's own API
([MULTI_UEM.md](../integrations/MULTI_UEM.md)).

## Where LucidFence is a different bet

- **Local-first sovereignty.** Your fleet's location and data never leave your
  infrastructure; no vendor cloud, no telemetry. Jamf's data lives in Jamf
  Cloud / your instance by design ([README.en.md](../README.en.md)).
- **Explainable risk, not a black box.** Every device gets a 0–100 score *with
  the reason*; Jamf does not provide a risk score with rationale
  ([README.en.md](../README.en.md)).
- **MDM-agnostic.** One risk plane across a mixed fleet (Applivery + Intune +
  Jamf + Fleet) instead of per-vendor silos
  ([MULTI_UEM.md](../integrations/MULTI_UEM.md)).
- **Honest location matrix.** LucidFence documents that Jamf gives no
  continuous location by API and tells you which source to pair it with
  ([LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md)).

## The moat (corrected)

Recycled from [README.en.md § Why](../README.en.md) with the adapter claim
**corrected** (Intune/Jamf are live adapters, not bundled mocks):

| | Native MDM (Jamf) | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| **Explainable risk** (0–100 + reason) | ❌ black box | ✅ score + `reasons` |
| **No location exfiltration** | ❌ (vendor cloud) | ✅ local-first |
| MDM-agnostic | ❌ Apple-centric | ✅ via adapters |
| SOAR + live CVE + on-demand commands | partial | ✅ |

## 2026 evidence addendum (SEO refresh, 2026-08-23)

To keep the "No continuous location by API" row precise for 2026 searchers
landing here for "Jamf geofencing":

- **Jamf has no native GPS/location tracking API** — confirmed by the admin
  community; Jamf's strength is inventory & posture, not device geolocation.
  Continuous geofencing on Jamf must pair an external source (Applivery GPS,
  the iOS on-device adapter, or network/osquery logical geo)
  ([LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md),
  [JAMF.md](../integrations/JAMF.md)).
- The Jamf row above ("no continuous location by API") reflects this; this
  addendum confirms it with the 2026 community consensus for searchers.

## Deep links

- Jamf onboarding: [integrations/JAMF.md](../integrations/JAMF.md)
- Location reality per UEM: [integrations/LOCATION_MATRIX.md](../integrations/LOCATION_MATRIX.md)
- Mixed fleet: [integrations/MULTI_UEM.md](../integrations/MULTI_UEM.md)
- Safe rollout: [operations/ENFORCEMENT.md](../operations/ENFORCEMENT.md)
- Other vendors: [LucidFence vs Intune](lucidfence-vs-intune.md), [LucidFence vs Kandji](lucidfence-vs-kandji.md)
