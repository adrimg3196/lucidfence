# LucidFence User Guide

> User guide with real product screenshots (demo tenant).
> Interactive step-by-step version: **`/static/manual.html`** in your local
> install (language toggle ES/EN in the header), or `manual.html` on the
> project's public site. **Versión en español:**
> [`MANUAL_DE_USO.md`](MANUAL_DE_USO.md). To install, see
> [`GETTING_STARTED.md`](../GETTING_STARTED.md).

LucidFence is the **geofencing and posture companion for the UEM you already
run** (Intune, Jamf, Applivery, Fleet…): it reads your fleet, correlates
location with signals, explains risk, and only acts through your UEM when you
decide. 100% local: your data never leaves your machine.

## 1. Start and log in

```bash
lucidfence quickstart     # or: python3 saas_server.py
```

Open `http://127.0.0.1:8765/`. With no credentials it starts in **demo mode**
with a sample fleet (yellow banner at the top): you can explore everything
risk-free — nothing touches real devices.

![Command Center: overview with live map, compliance and activity](../../static/manual/01-dashboard.png)

The **Overview** is your on-call screen: devices inside/outside geofences,
compliance breaches, CVEs in fleet apps, live map and the compliance donut
(exportable to PDF).

## 2. The map and the fleet

![Full-page fleet map](../../static/manual/02-mapa.png)

**Map**: every dot is a device, colored by state (inside / outside / unknown).
The **"Mapa detallado"** button (bottom right) switches to a real
OpenStreetMap background, Google-Maps style — it is *opt-in* with a notice:
tiles are downloaded from openstreetmap.org, which sees the viewport area;
your devices and positions are never sent, and the default remains the local
map with no external requests. Laptops without GPS can also be positioned if
you configure network-fencing (declare the office by CIDR/SSID — see
[`NETWORK_LOCATION.md`](../integrations/NETWORK_LOCATION.md)).

![Device table with state and posture](../../static/manual/03-dispositivos.png)

**Devices**: the operational table. Click any row for the device sheet: last
position, posture signals (encryption, Lockdown Mode, supervision, hardware
health), apps with CVEs and the actions available *through your UEM*.

## 3. Explainable risk (no black box)

![Risk engine with per-device justified score](../../static/manual/04-riesgo.png)

Every score carries **its reasons** ("outside allowed geofence", "apps with
risky CVEs…") and a verification seal that distinguishes real signal from
absence of signal. The product's honesty rule: **the unknown never
penalizes** — a datum your UEM does not report never invents risk.

## 4. Geofences

![Geofence view](../../static/manual/05-geovallas.png)

Create circles (center + radius) or polygons. A device is `inside`, `outside`
or `unknown` (no usable signal — it is never guessed). Prefer config as code?
Keep `fences.json` in git and apply it with
`lucidfence apply --fences file.json` (it validates, shows the diff and
simulates the impact **before** writing; see
[`config_as_code.md`](../operations/config_as_code.md)).

## 5. Incidents and workflows

![Incidents with context](../../static/manual/06-incidentes.png)

**Incidents** collects what deserves attention (geofence exits, compliance
breaches) with its context. Alerts can go out via Slack, Teams, signed webhook
or ntfy ([`ALERT_RECIPES.md`](../operations/ALERT_RECIPES.md)).

![Workflows ready to enable](../../static/manual/07-workflows.png)

**Workflows**: common automations already built ("on geofence exit, notify"),
or build your own with trigger + condition + action without touching JSON.

## 6. Connect your UEM

![UEM connector wizard](../../static/manual/08-conectores.png)

The **UEM Connectors** wizard guides you per vendor with the real **least
privilege** each one needs (in observe, read-only is enough). Per-UEM guides
live in [`docs/integrations/`](../integrations/); the
[location matrix](../integrations/LOCATION_MATRIX.md) states what each vendor
truly delivers, without overpromising.

## 7. Settings: you stay in control

![Settings with dry-run enabled](../../static/manual/09-ajustes.png)

Rollout safety is designed so nothing acts without you:

1. **`observe` (default)**: everything is computed and audited, nothing
   executes. **Dry-run** comes enabled.
2. **`enforce`**: only if you enable it per tenant, and only the actions on
   your allow-list.
3. **`wipe` requires a double key** (`allow_wipe: true` **and** the device in
   `wipe_allowlist`). It is never widened from the UI.

Full detail in [`ENFORCEMENT.md`](../operations/ENFORCEMENT.md).

## 8. What am I NOT seeing? (blind spots)

`GET /api/coverage` (or the matching card) shows the negative of your
coverage: devices without signal, devices that stopped reporting, and empty
geofences — visible so you decide, never automatic action
([`coverage.md`](../operations/coverage.md)).

## Quick questions

- **Do I need credentials to try it?** No: demo mode is complete.
- **Does my data leave my machine?** No. No telemetry, no vendor cloud; your
  fleet's location never leaves your install.
- **How much does it cost?** Nothing: 100% free open-source (Apache-2.0).
- **Can LucidFence wipe a device on its own?** No: explicit double key and
  always through your UEM.
- **Something fails** → `lucidfence doctor`, and
  [`RUNBOOK.md`](../operations/RUNBOOK.md).
