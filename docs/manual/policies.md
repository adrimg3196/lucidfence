# Policies — LucidFence

Reference for LucidFence's policy DSL.

## Overview

Policies define what actions to take when devices enter or leave geofences, or when risk conditions are met. Policies are defined in the `policies` array of your config file.

## Policy Structure

```json
{
  "name": "Office geofence alert",
  "type": "geofence",
  "fence": "Madrid Office",
  "condition": "enter",
  "severity": "low",
  "actions": ["log", "notify"]
}
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable name for the policy. |
| `type` | string | Yes | Policy type: `geofence`, `risk`, or `schedule`. |
| `fence` | string | For geofence | Name of the geofence to monitor. |
| `condition` | string | Yes | Trigger condition: `enter`, `exit`, `inside`, `outside`. |
| `severity` | string | Yes | Risk severity: `low`, `medium`, `high`, `critical`. |
| `actions` | array | Yes | List of actions to take. |
| `filters` | object | No | Optional filters to narrow when the policy applies. |
| `schedule` | object | No | Optional time window when the policy is active. |

## Policy Types

### Geofence Policy

Triggers when a device enters or exits a geofence.

```json
{
  "name": "Office geofence",
  "type": "geofence",
  "fence": "Madrid Office",
  "condition": "enter",
  "severity": "low",
  "actions": ["log"]
}
```

### Risk Policy

Triggers when the risk engine evaluates a device as meeting certain risk criteria.

```json
{
  "name": "High risk device",
  "type": "risk",
  "condition": "risk_score > 70",
  "severity": "high",
  "actions": ["alert", "notify"]
}
```

### Schedule Policy

Triggers on a time schedule.

```json
{
  "name": "After hours alert",
  "type": "schedule",
  "condition": "outside_hours",
  "hours": [9, 18],
  "severity": "medium",
  "actions": ["log"]
}
```

## Actions

Available actions:

| Action | Description |
|--------|-------------|
| `log` | Record the event in the incident log. |
| `alert` | Show an alert in the dashboard. |
| `notify` | Send a notification (email, webhook, etc.). |
| `block` | Block the device from accessing resources. |
| `wipe` | Trigger a remote wipe (use with caution). |
| `lock` | Lock the device screen. |
| `location` | Request current location. |

## Filters

Filters narrow when a policy applies:

```json
{
  "filters": {
    "platform": "ios",
    "status": "active",
    "compliance": false
  }
}
```

## Schedule

Time window when the policy is active:

```json
{
  "schedule": {
    "start": "09:00",
    "end": "18:00",
    "days": [1, 2, 3, 4, 5]
  }
}
```

Days are 0=Sunday through 6=Saturday.

## Examples

### Log when device enters office

```json
{
  "name": "Office entry log",
  "type": "geofence",
  "fence": "Madrid Office",
  "condition": "enter",
  "severity": "low",
  "actions": ["log"]
}
```

### Alert on high-risk device outside geofence

```json
{
  "name": "High risk outside office",
  "type": "geofence",
  "fence": "Madrid Office",
  "condition": "outside",
  "severity": "high",
  "filters": {
    "risk_score": 70
  },
  "actions": ["alert", "notify"]
}
```

### Block non-compliant devices

```json
{
  "name": "Block non-compliant",
  "type": "risk",
  "condition": "compliance == false",
  "severity": "critical",
  "actions": ["block", "notify"]
}
```

## Validation

Run `lucidfence validate` to check your policies for errors.

## Programmatic Use

You can also manage policies via the API:

```bash
# List policies
lucidfence policies list

# Validate policies
lucidfence policies validate

# Export policies
lucidfence policies export > policies.json
```

## Next Steps

- [Configuration](./configuration.md) — config file reference
- [Quick Start](./quickstart.md) — get started
- [UEM Adapters](./adapters.md) — connect your UEM
