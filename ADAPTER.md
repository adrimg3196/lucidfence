# Jamf Adapter

## Authentication Flow

To use the Jamf adapter, you need to authenticate with the Jamf Pro API using your client ID and client secret. The authentication process involves the following steps:

1. **Obtain a Bearer Token:**
   - Send a POST request to the `/api/v1/auth/token` endpoint with your client ID and client secret.
   - The response will include a Bearer token and its expiration time (TTL).

2. **Use the Bearer Token:**
   - Include the Bearer token in the `Authorization` header of subsequent requests to the Jamf Pro API.

### Example

```python
adapter = JamfAdapter(
    jss_url="https://your-jamf-pro-url.com",
    client_id="your-client-id",
    client_secret="your-client-secret"
)
```

## Endpoint Template

The `jss_url` parameter should be set to the base URL of your Jamf Pro instance. For example:

- `jss_url = "https://your-jamf-pro-url.com"`

## Functions

### `list_devices(org)`

- **Description:** Lists all devices in the specified organization.
- **Parameters:**
  - `org`: The organization identifier.
- **Returns:**
  - A list of dictionaries, each containing the following keys:
    - `device_id`
    - `platform`
    - `compliant`
    - `encrypted`
    - `os_version`
    - `battery_level`
    - `storage_free_gb`

### `run_command(org, device_id, action, params)`

- **Description:** Runs a command on the specified device.
- **Parameters:**
  - `org`: The organization identifier.
  - `device_id`: The identifier of the device.
  - `action`: The action to perform (e.g., `erase`, `lock`, `device-location`).
  - `params`: Additional parameters for the action.
- **Returns:**
  - A dictionary containing the result of the command.