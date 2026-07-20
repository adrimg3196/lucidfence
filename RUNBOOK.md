# LucidFence — Runbook

> Step-by-step playbook for new operators. Each task has an estimated time
> and lists the files you'll touch. **A new user should install and operate
> LucidFence end-to-end using only this runbook + the GUI.**

---

## R0 — Boot the app (60 s)

### R0.1 macOS desktop

```bash
# Install + launch
open /Applications/LucidFence.app
# Engine listens on 127.0.0.1:8765; Command Center window opens.
```

### R0.2 macOS / Linux via Homebrew

```bash
brew install adrimg3196/lucidfence/lucidfence
lucidfence
```

### R0.3 Docker (any host)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
docker compose up -d
# http://localhost:8765
```

### R0.4 Direct Python (dev/CI)

```bash
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence
python3 -m pip install -r requirements.txt
python3 saas_server.py
```

Verify the engine is healthy:

```bash
curl -sf http://127.0.0.1:8765/health
# {"ok": true, ...}
```

---

## R1 — Connect a UEM/MDM (5 min)

### R1.1 Pick the adapter

The supported MDM adapters (from `core/adapters/`) are:

| Adapter | When to use | Live creds env-var |
|---|---|---|
| `SimulationAdapter` | Demo / no tenant | none |
| `AppliveryAdapter` | Applivery UEM (SaaS) | `APPLIVERY_API_KEY` |
| `IntuneAdapter` | Microsoft Intune (live mode) | `INTUNE_TENANT_ID` / `INTUNE_CLIENT_ID` / `INTUNE_CLIENT_SECRET` |
| `JamfAdapter` | Jamf Pro (live mode) | `JAMF_BASE_URL` / `JAMF_CLIENT_ID` / `JAMF_CLIENT_SECRET` |
| `WindowsConformidadAdapter` | Windows 10/11 posture report (read-only) | `INTUNE_*` (same OAuth as Intune) |
| `ChromeOSAdapter` | Google Admin SDK / Directory API (read-only) | `GOOGLE_ADMIN_REFRESH_TOKEN` / `CLIENT_ID` / `CLIENT_SECRET` |

For a demo fleet, leave the default `simulation` mode — no creds needed.

### R1.2 Wire your MDM via `config.json`

`config.json` lives in the LucidFence data directory (`data/` by default;
`~/Library/Application Support/LucidFence` on macOS).

```json
{
  "mode": "intune",
  "mdm": {
    "intune": {
      "live": true,
      "tenant_id": "<Azure-tenant-guid>",
      "client_id": "<app-registration-client-id>",
      "client_secret": "<client-secret-value>"
    }
  }
}
```

Drop the env vars into a `.env` alongside `config.json` to avoid committing
secrets:

```
INTUNE_TENANT_ID=<Azure-tenant-guid>
INTUNE_CLIENT_ID=<app-registration-client-id>
INTUNE_CLIENT_SECRET=<client-secret-value>
```

`config_loader.load()` merges `.env` into `mdm.<adapter>.*` automatically
(see `config_loader.py`).

### R1.3 Restart the engine

```bash
# macOS app
LucidFence → Quit, then reopen.
# Homebrew / Docker / Python
lucidfence restart   # or kill + relaunch
```

The Command Center's **Settings** tab now shows the MDM status indicator
(green dot = live OK, yellow = mock fallback, red = auth error).

---

## R2 — Add a geofence (3 min)

A geofence is a polygon + a rule attached to it. Rules are evaluated every
15 min by the engine-cron workflow.

### R2.1 Edit `fences.json`

```json
{
  "fences": [
    {
      "id": "office_main",
      "name": "Oficina principal",
      "polygon": [[-3.703, 40.417], [-3.703, 40.420], [-3.700, 40.420], [-3.700, 40.417]],
      "rule": "must_be_inside",
      "applies_to": ["department:field-ops"],
      "schedule": "mon-fri 09:00-19:00"
    }
  ]
}
```

### R2.2 Validate before deploying

```bash
python3 -c "from core.fences import load_fences; load_fences('fences.json')"
# Empty / silent = OK; non-zero exit = schema error.
```

### R2.3 Push & watch

```bash
# (data/ is on a watch; the engine reloads fences.json on next tick)
# Open Command Center → Geofences tab → see the new entry
```

---

## R3 — Read incidents (2 min)

The Command Center's **Eventos / Incidentes** view shows every fence
breach, CVE flag, and AI provider alert. To read the same data via CLI:

```bash
curl -sf http://127.0.0.1:8765/api/incidents | jq .
```

Each incident has:
- `id`, `device_id`, `rule_violated`, `severity`, `opened_at`, `closed_at?`
- `evidence`: location snapshots, OS patch level, CVE refs

---

## R4 — Trigger an action (lock/wipe/locate) (90 s)

From the Command Center → **Acciones** tab → pick a device → pick an action
→ confirm.

Via CLI (admin token required):

```bash
curl -sf -X POST http://127.0.0.1:8765/api/actions \
  -H "Content-Type: application/json" \
  -d '{"device_id": "dev-001", "action": "lock", "params": {}}'
# returns {"ok": true, "adapter": "intune", "graph_status": 204}
```

For read-only posture (WindowsConformidadAdapter / ChromeOSAdapter):

```bash
curl -sf -X POST http://127.0.0.1:8765/api/actions \
  -H "Content-Type: application/json" \
  -d '{"device_id": "win-001", "action": "report"}'
# returns {ok, mode, devices: [...], summary: {compliant, encrypted, policy_id}}
```

---

## R5 — Diagnose failures (5 min)

| Symptom | File to read | Likely cause |
|---|---|---|
| Engine returns 500 on any API | `data/logs/engine.log` | traceback in startup |
| MDM status indicator red | `data/logs/mdm.log` | 401 from UEM (rotate creds) |
| Fence not detected | `fences.json` | JSON schema mismatch (run `core.fences.load_fences`) |
| CVE feed empty | `data/cve_cache.json` | NVD API rate-limit (wait 1 h) |
| Tests failing on CI | `tests/run_tests.py` | a `test_*.py` raising `SystemExit` at import — see AGENTS.md "Known landmines" |

---

## R6 — Add a new community MDM adapter (1 day)

This is documented in detail in `core/adapters/ADAPTER.md`. Short version:

```bash
# 1. Copy the SDK template
cp core/adapters/_template_adapter.py core/adapters/<your_mdm>.py
# 2. Rename the class + set `name`
# 3. Wire `_build_request` + the live-path branch in `execute()`
# 4. Register in core/adapters/__init__.py:
#    ADAPTER_REGISTRY["<your_mdm>"] = <YourMdm>Adapter
# 5. Add tests:
cp tests/test_template_contract.py tests/test_<your_mdm>.py
# 6. Run the contract suite:
python3 tests/test_sdk_contract.py
# 7. Open PR — first merged adapter for your MDM joins the Hall of Fame.
```

---

## Where to start (file map)

| If you want to… | Read this file first |
|---|---|
| Install the app | `README_CLIENTE.md` (es) or `README.en.md` (en) |
| Understand the engine | `core/engine.py` (top-level scheduler) |
| Add a fence | `core/fences.py` + `fences.json` |
| Add an MDM | `core/adapters/ADAPTER.md` + `core/adapters/_template_adapter.py` |
| Read incidents | `core/incidents.py` + `tests/test_incidents.py` |
| Wire AI | `core/ai_provider.py` + `.env.example` (`OPENAI_API_KEY` / etc.) |
| Triage CVE feed | `core/cve_feed_nvd.py` + `data/cve_cache.json` |
| Run the test suite | `tests/run_tests.py` (zero-deps runner) |

---

## Escalation path

If a step in this runbook fails after the listed time estimate, open an
issue with:
1. The exact command + its output
2. The contents of `data/logs/engine.log` (last 50 lines)
3. The OS / Python version (`python3 --version`, `uname -a`)

Do **not** open an issue if a `Maybe Rewarded` label is on a custom adapter
you forked — that's expected behaviour for unfinished adapters.