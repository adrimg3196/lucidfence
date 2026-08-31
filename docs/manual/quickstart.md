# Quick Start — LucidFence

Get LucidFence running and connected to your first UEM provider in 5 minutes.

## Step 1: Install

See [Installation](./installation.md) for full instructions. The quick version:

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Step 2: Configure

Create a minimal config file:

```bash
lucidfence init
```

This creates a `config.json` with sensible defaults. Edit it to add your UEM credentials.

## Step 3: Start the Server

```bash
lucidfence server
```

Open http://localhost:8765 — you'll see the dashboard.

## Step 4: Connect a UEM Provider

Go to **Settings → Providers** in the dashboard and add your first provider (Applivery, Intune, Jamf, or Fleet). You'll need:

- API endpoint URL
- API key or OAuth credentials
- Organization/tenant ID

## Step 5: Verify It Works

Once connected, the dashboard shows your devices. Create a simple geofence policy:

1. Go to **Policies → New Policy**
2. Add a geofence (draw a circle on the map or enter coordinates)
3. Set an action (alert, block, log)
4. Save and wait for the next sync cycle

You should see devices entering/leaving the geofence in the **Incidents** panel.

## What's Next

- [Configuration](./configuration.md) — detailed config options
- [Geofencing Policies](./policies.md) — policy DSL reference
- [UEM Adapters](./adapters.md) — per-provider setup guides
- [Dashboard](./dashboard.md) — full dashboard walkthrough
