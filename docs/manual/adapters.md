# UEM Adapters — LucidFence

Guides for connecting each UEM provider to LucidFence.

## Overview

LucidFence connects to your UEM providers to fetch device data, evaluate geofences, and trigger actions. Each provider has its own adapter with specific configuration requirements.

## Supported Providers

| Provider | Status | Connection |
|----------|--------|------------|
| Applivery | ✅ Live | REST API (Bearer token) |
| Intune | ✅ Live | Microsoft Graph API (OAuth2) |
| Jamf | ✅ Live | Jamf Pro API (Bearer token) |
| Fleet | ✅ Live | Fleet API (API key) |

## Applivery

### Setup

1. Get your API key from the Applivery dashboard (Settings → API).
2. Get your organization ID from the Applivery dashboard.
3. Add to your config:

```json
{
  "applivery": {
    "api_key": "your-api-key",
    "org_id": "your-org-id",
    "api_base": "https://api.applivery.io/v1"
  }
}
```

### What It Does

- Fetches device list with location data
- Supports pagination via `Link` header
- Captures auth errors as `integration_error` (never 500s)
- Tests verified against live api.applivery.io on 2026-07-09

### Contract

- Route: `GET /v1/organizations/{org}/mdm/devices` (plural "organizations" + "mdm")
- Auth: `Authorization: Bearer <token>` (X-Api-Token is a different API)
- Response: `{"items": [...]}` with `nextCursor` for pagination

## Intune

### Setup

1. Register an app in Azure AD (Enterprise Applications → New registration).
2. Grant it `DeviceManagementManagedDevices.Read.All` permission.
3. Get your tenant ID, client ID, and create a client secret.
4. Add to your config:

```json
{
  "intune": {
    "tenant_id": "your-tenant-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }
}
```

### What It Does

- Connects via Microsoft Graph API
- Fetches managed devices with location data
- Uses OAuth2 client credentials flow
- Supports device compliance status

### Contract

- Endpoint: `https://graph.microsoft.com/v1.0/devices/managedDevices`
- Auth: OAuth2 client credentials (tenant_id + client_id + client_secret)
- Response: paginated list of managed devices

## Jamf

### Setup

1. Create an API client in Jamf Pro (Settings → Computer Access → API Clients).
2. Generate an API token.
3. Add to your config:

```json
{
  "jamf": {
    "api_token": "your-api-token",
    "base_url": "https://your-jamf.jamfcloud.com"
  }
}
```

### What It Does

- Fetches computer and mobile device lists
- Supports DDM (Device Enrollment Program) status
- Fetches location data if available
- Supports supervised status, OS version, and more

### Contract

- Base: `https://{your-jamf}.jamfcloud.com`
- Auth: Bearer token (JSS API)
- Endpoints: `/api/v1/computers`, `/api/v1/mobile-devices`

## Fleet

### Setup

1. Get your Fleet API key from the Fleet dashboard.
2. Add to your config:

```json
{
  "fleet": {
    "api_key": "your-api-key",
    "base_url": "https://fleet.local"
  }
}
```

### What It Does

- Fetches device list with telemetry
- Supports multiple device types
- Integrates with osquery for detailed device data

### Contract

- Base: your Fleet server URL
- Auth: API key header
- Endpoints: `/api/v1/devices`

## Adding a New Provider

See [adapter scaffolding](https://github.com/adrimg3196/lucidfence/blob/main/docs/contributing/DEVELOPMENT.md#anadir-un-adaptador-uem-nuevo) to create a new adapter.

## Testing Your Connection

```bash
# Validate your config
lucidfence validate

# Run a single sync cycle (dry run)
lucidfence sync --dry-run

# Start the server and check the dashboard
lucidfence server
```

Then open http://localhost:8765 and check **Settings → Providers**.

## Troubleshooting

- **401 Unauthorized**: Check your API key or OAuth credentials.
- **403 Forbidden**: Your API key doesn't have the right permissions.
- **404 Not Found**: Check the API endpoint URL.
- **Timeout**: Check your network connection and the provider's status page.

See [Troubleshooting](./troubleshooting.md) for more.
