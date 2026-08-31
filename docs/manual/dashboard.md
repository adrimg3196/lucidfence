# Dashboard — LucidFence

Walkthrough of the LucidFence dashboard.

## Access

Open http://localhost:8765 in your browser after starting the server:

```bash
lucidfence server
```

## Layout

The dashboard has four main panels:

### 1. Overview

Shows your fleet at a glance:

- Total devices
- Devices inside geofences
- Devices outside geofences
- Compliance status
- Recent incidents

### 2. Devices

List of all devices from your connected UEM providers:

- Device name, ID, platform
- Current location (if available)
- Inside/outside status
- Compliance status
- Last sync time

Click a device to see details and actions.

### 3. Geofences

Your defined geofences and their status:

- List of all geofences
- Devices inside/outside each
- Violation history
- Create/edit/delete geofences

### 4. Incidents

Timeline of policy-triggered events:

- When and what happened
- Which device and policy
- Actions taken
- Severity level

## Settings

### Providers

Connect and manage your UEM providers:

- Add/remove providers
- Configure credentials
- Test connection
- View sync status

### Policies

Manage your geofencing and risk policies:

- Create new policies
- Edit existing policies
- Enable/disable policies
- View policy triggers

### Enforcement

Configure enforcement mode:

- **Observe**: log only, no actions taken
- **Enforce**: take configured actions (block, lock, wipe, etc.)

Always start in **observe** mode. Only switch to **enforce** after testing.

### Teams

Manage team members and roles (RBAC):

- Add/remove team members
- Assign roles (admin, editor, viewer)
- Audit log of team changes

## Troubleshooting

### Dashboard not loading

1. Check that the server is running: `lucidfence server`
2. Check for errors in the server output
3. Verify your browser can reach localhost:8765

### No devices showing

1. Check that at least one UEM provider is configured
2. Go to Settings → Providers and verify the connection
3. Check the sync status — first sync may take a moment

### Credentials not working

1. Verify your API keys/tokens are correct
2. Check that the credentials have the right permissions
3. Look at the incident log for auth error details

See [Troubleshooting](./troubleshooting.md) for more.
