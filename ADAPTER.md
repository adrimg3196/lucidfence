# Intune Adapter

## Overview
The Intune adapter allows you to manage and control devices using Microsoft Intune via the Microsoft Graph API.

## Configuration
To use the Intune adapter, you need to configure the following settings in your `config.json` file:

```json
{
    "intune": {
        "client_id": "<your_client_id>",
        "tenant_id": "<your_tenant_id>",
        "client_secret": "<your_client_secret>"
    }
}
```

## OAuth Flow
The Intune adapter uses the `client_credentials` flow to authenticate with the Microsoft Graph API. The `client_id`, `tenant_id`, and `client_secret` are used to obtain an access token, which is then used to make API requests.

## Endpoint Template
The `endpoint_template` in `config.json` should use the `tenant_id` variable, not hardcode it:

```json
{
    "endpoint_template": "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
}
```

## Error Handling
- `AuthError`: Raised when there is an authentication issue.
- `TransportError`: Raised when there is a transport issue, such as a network error or a non-200 status code from the API.

## Example Usage
```python
from core.adapters.intune import IntuneAdapter

adapter = IntuneAdapter(client_id='your_client_id', tenant_id='your_tenant_id', client_secret='your_client_secret')
devices = adapter.list_devices(org='org1')
print(devices)

result = adapter.run_command(org='org1', device_id='device1', action='wipe', params={})
print(result)
```
