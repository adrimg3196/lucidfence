# Configuration — LucidFence

Reference for the LucidFence configuration file.

## File Location

By default, LucidFence looks for `config.json` in the current directory. You can specify a different path with `--config`.

## Structure

```json
{
  "mode": "live",
  "dry_run": false,
  "applivery": {
    "api_key": "...",
    "org_id": "...",
    "api_base": "https://api.applivery.io/v1"
  },
  "intune": {
    "tenant_id": "...",
    "client_id": "...",
    "client_secret": "..."
  },
  "jamf": {
    "api_token": "...",
    "base_url": "https://your-jamf.jamfcloud.com"
  },
  "fleet": {
    "api_key": "...",
    "base_url": "https://fleet.local"
  },
  "fences": [],
  "policies": [],
  "organizations": [],
  "llm": {}
}
```

## Fields

### Global

| Field | Type | Description |
|-------|------|-------------|
| `mode` | string | `live` or `dry_run`. In dry_run, no API calls are made. |
| `dry_run` | bool | If true, run in dry-run mode (no side effects). |
| `device_auth` | object | OIDC device auth configuration (optional). |

### UEM Providers

Each provider has its own section. Only configure the ones you use.

#### Applivery

| Field | Type | Description |
|-------|------|-------------|
| `api_key` | string | Your Applivery API key. |
| `org_id` | string | Your organization ID. |
| `api_base` | string | API base URL (default: `https://api.applivery.io/v1`). |

#### Intune

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | string | Azure AD tenant ID. |
| `client_id` | string | Application (client) ID. |
| `client_secret` | string | Client secret (or use OIDC device flow). |

#### Jamf

| Field | Type | Description |
|-------|------|-------------|
| `api_token` | string | Jamf API token. |
| `base_url` | string | Jamf Pro URL. |

#### Fleet

| Field | Type | Description |
|-------|------|-------------|
| `api_key` | string | Fleet API key. |
| `base_url` | string | Fleet server URL. |

### Fences

Array of geofence definitions. Each fence has:

```json
{
  "name": "Madrid Office",
  "type": "circle",
  "latitude": 40.4168,
  "longitude": -3.7038,
  "radius_m": 500,
  "actions": ["log"]
}
```

### Policies

Array of risk policy definitions. See [Geofencing Policies](./policies.md) for the full DSL.

### Organizations

Array of organization definitions for multi-tenant setups.

### LLM

Optional LLM configuration for AI-powered features. Only needed if you use AI-assisted policy analysis.

## Environment Variables

Sensitive values can be set via environment variables instead of the config file:

- `APPLIVERY_API_KEY`
- `APPLIVERY_ORG_ID`
- `INTUNE_TENANT_ID`
- `INTUNE_CLIENT_ID`
- `INTUNE_CLIENT_SECRET`
- `JAMF_API_TOKEN`
- `JAMF_BASE_URL`
- `FLEET_API_KEY`
- `FLEET_BASE_URL`

## Example: Minimal Config

```json
{
  "mode": "dry_run",
  "applivery": {
    "api_key": "${APPLIVERY_API_KEY}",
    "org_id": "${APPLIVERY_ORG_ID}"
  }
}
```

## Example: Full Config

See `config.json.example` in the repository root for a complete example.

## Validation

Run `lucidfence validate` to check your config file for errors.

## Next Steps

- [Quick Start](./quickstart.md) — get running fast
- [Geofencing Policies](./policies.md) — define geofences and risk rules
- [UEM Adapters](./adapters.md) — per-provider setup
