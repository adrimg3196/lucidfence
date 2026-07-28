# LucidFence · Command Center

> **Geofencing that doesn't exfiltrate. Risk that explains itself.**

[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Multi-MDM](https://img.shields.io/badge/MDM-Applivery%20%7C%20Intune%20%7C%20Jamf-9cf)](core/adapters/ADAPTER.md)
[![Local-first](https://img.shields.io/badge/architecture-100%25%20local-blue)](saas_server.py)

Local-first **UEM Risk & Geofence Control Plane** that turns your mobile fleet's
geolocation into **explainable risk** (0–100 score **with its reason**) and
automated actions — **MDM-agnostic** via adapters.

- 🛡️ **Sovereignty / local-first**: your fleet's location and data **never leave
  your infrastructure**. The only egress is what YOU configure: your MDM
  (Applivery/Intune/Jamf) and the NVD CVE feed (read-only vuln data). No third-party
  CDNs in the dashboard (100% local).
- 🧠 **Explainable Risk Engine**: every device gets a 0–100 score **with the reason**
  — never a magic number.
- 🔌 **Multi-MDM**: Applivery (live) + Intune/Jamf (mocks included) + community adds the rest.
- 📊 **Dashboard**: geofences, IT inventory, remote commands, alerts, CVE/SOAR.
- ✅ **Evidence gate**: a risk finding only counts if backed by real signals (anti-overclaim).

## Install (client, $0, sovereign)

```bash
brew install adrimg3196/lucidfence/lucidfence
# opens Launchpad → LucidFence.app → dashboard at http://localhost:8765
```

Or download the release tarball and run `lucidfence serve`. The desktop app
(`.app` on macOS) starts the on-prem server and opens the dashboard in your browser.
Login demo: `ciso@acme.test` / `demo1234`.

## Why (the moat)

Native MDMs (Intune, Jamf, Applivery, SOTI, Workspace ONE) do commodity geofencing:
they tell you "inside/outside" and ship your fleet's location to **their** cloud.
They don't correlate risk, don't explain why, and keep your data sovereignty.

**LucidFence inverts the premise:** local-first, explainable risk, MDM-agnostic.

| | Native MDM | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| **Explainable risk** (0–100 + reason) | ❌ black box | ✅ score + `reasons` |
| **No location exfiltration** | ❌ (vendor cloud) | ✅ local-first |
| MDM-agnostic | ❌ locked to yours | ✅ via adapters |
| SOAR + live CVE + on-demand commands | partial | ✅ |

## Smoke test (verify it works on YOUR machine)

```bash
bash scripts/smoke_client.sh
```

Downloads the release, starts the on-prem server, logs in with the demo account,
and reports PASS/FAIL for the dashboard, API health, and the risk engine.

## Languages

The dashboard is bilingual: **Español / English**. Use the floating language
button (bottom-right) to switch; the choice persists in `localStorage`.

## License

Apache-2.0. 100% free. No accounts, no telemetry, no vendor lock-in.
