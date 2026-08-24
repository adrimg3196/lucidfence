# LucidFence · Command Center

> **Geofencing that doesn't exfiltrate. Risk that explains itself.**

*English overview of LucidFence — the counterpart of the [root `README.md`](../README.md)
(Spanish, for first-time users). For a full step-by-step English walkthrough with
screenshots, see [`docs/manual/USER_GUIDE.md`](manual/USER_GUIDE.md).*

[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](../LICENSE)
[![Multi-UEM](https://img.shields.io/badge/UEM-Applivery%20%7C%20Intune%20%7C%20Jamf%20%7C%20Fleet-9cf)](integrations/MULTI_UEM.md)
[![Local-first](https://img.shields.io/badge/architecture-100%25%20local-blue)](../saas_server.py)

Local-first **UEM Risk & Geofence Control Plane** that turns your mobile fleet's
geolocation into **explainable risk** (0–100 score **with its reason**) and
automated actions — **MDM-agnostic** via adapters.

- 🛡️ **Sovereignty / local-first**: your fleet's location and data **never leave
  your infrastructure**. The only egress is what YOU configure: your MDM
  (Applivery/Intune/Jamf/Fleet) and the NVD CVE feed (read-only vuln data). No third-party
  CDNs in the dashboard (100% local).
- 🧠 **Explainable Risk Engine**: every device gets a 0–100 score **with the reason**
  — never a magic number.
- 🔌 **Multi-UEM**: Applivery, Intune, Jamf and Fleet adapters exist today.
  Vendor API calls run only when that tenant configures its own credentials;
  otherwise the product stays in explicit simulation mode.
- 📊 **Dashboard**: geofences, IT inventory, remote commands, alerts, CVE/SOAR.
- ✅ **Evidence gate**: a risk finding only counts if backed by real signals (anti-overclaim).

## Install (client, $0, sovereign)

### From the repository (macOS or Linux)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Uses Docker when available; otherwise it creates .venv with Python 3.11+.
# It only exits successfully after /api/health responds (30 s timeout).
./install.sh
# Explicit Docker alternative:
# docker compose up -d --build

# Verify the service started by either path.
curl -fsS http://127.0.0.1:8765/api/health

# Optional with Python 3.11+: self-verifying walkthrough, no host CLI required.
python3 -m lucidfence.cli quickstart
```

The installer waits for the application with a bounded timeout and fails if it
does not start. The Python path uses an isolated `.venv`; it does not modify
system Python. `curl` is optional because health can also be checked through
Python or inside the container. The dashboard is exposed at `http://127.0.0.1:8765`.
Neither the installer nor Docker installs a global `lucidfence` command on the
host. The module-based walkthrough is available when Python 3.11+ is installed.

### Homebrew (macOS)

```bash
brew install adrimg3196/lucidfence/lucidfence
lucidfence --version    # confirm the version actually installed
lucidfence              # starts the local server and opens the dashboard
lucidfence doctor       # checks the installation
```

Homebrew installs the `lucidfence` CLI, not `LucidFence.app`.
The tap can temporarily lag behind the newest GitHub release. Check
`lucidfence --version` against [GitHub Releases](https://github.com/adrimg3196/lucidfence/releases)
before relying on a recently added capability.

**Optional macOS desktop preview.** The drag-and-drop `LucidFence.app` is a
separate Apple Silicon-only, not-yet-notarized preview
(`v1.2.0-desktop-preview.1`). See
[`docs/operations/DESKTOP_APP.md`](operations/DESKTOP_APP.md) for its download,
requirements and build instructions.

## Why (the moat)

Native MDMs (Intune, Jamf, Applivery, SOTI, Workspace ONE) do commodity geofencing:
they tell you "inside/outside" and ship your fleet's location to **their** cloud.
They don't correlate risk, don't explain why, and take control of data
sovereignty away from the administrator.

**LucidFence inverts the premise:** local-first, explainable risk, MDM-agnostic.

| | Native MDM | LucidFence |
|---|---|---|
| Geofencing | ✅ commodity | ✅ |
| **Explainable risk** (0–100 + reason) | ❌ black box | ✅ score + `reasons` |
| **No location exfiltration** | ❌ (vendor cloud) | ✅ local-first |
| MDM-agnostic | ❌ locked to yours | ✅ via adapters |
| SOAR + live CVE + on-demand commands | partial | ✅ |

## What is not finished

- Native vendor integrations still require credentials supplied and controlled
  by the administrator; CI cannot prove a live tenant it cannot access.
- `LucidFence.app` is an Apple Silicon preview and is not notarized.
- The public Pages showcase contains synthetic demo data, never customer data.

The project is Apache-2.0 with no paid tier or proprietary backend.

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
