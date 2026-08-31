# Troubleshooting — LucidFence

Common issues and how to fix them.

## Dashboard

### Dashboard not loading

**Symptom**: Browser shows "Connection refused" or "Site can't be reached".

**Fix**:
1. Check that the server is running: `lucidfence server`
2. Check for errors in the server output
3. Verify your browser can reach localhost:8765
4. Try a different browser or incognito mode

**Still not working?** Check the server logs for errors. Run `lucidfence server --verbose` for more detail.

### Blank dashboard

**Symptom**: Dashboard loads but shows no content.

**Fix**:
1. Check that at least one UEM provider is connected
2. Go to Settings → Providers and verify each provider is connected
3. Check the sync status — first sync may take 30-60 seconds

### "No devices" message

**Symptom**: Dashboard shows "No devices found".

**Fix**:
1. Verify your UEM provider credentials are correct
2. Check that devices exist in your UEM console
3. Force a sync: `lucidfence sync --force`
4. Check the incident log for sync errors

## Providers

### Connection fails

**Symptom**: Provider shows "Connection failed" or auth error.

**Fix**:
1. Verify your API key/token is correct and not expired
2. Check that the key has the necessary permissions
3. Verify the API endpoint URL is correct
4. Check for network issues (firewall, VPN, proxy)

### 401 Unauthorized

**Symptom**: "Invalid token" or "Authentication failed".

**Fix**:
1. Regenerate the API key/token from your UEM console
2. Update the config with the new credentials
3. Restart the server

### 403 Forbidden

**Symptom**: "Permission denied" or "Insufficient privileges".

**Fix**:
1. Check that your API key has the required scopes
2. For Intune: verify Azure AD app has `DeviceManagementManagedDevices.Read.All`
3. For Jamf: verify API client has computer/mobile device read access
4. Contact your UEM administrator if needed

### 404 Not Found

**Symptom**: "Route not found" or "Resource not found".

**Fix**:
1. Verify the API endpoint URL is correct
2. For Applivery: the correct route is `/v1/organizations/{org}/mdm/devices` (not `/orgs/{org}/devices`)
3. Check your UEM version — API paths may differ

### Timeout

**Symptom**: "Request timed out" or sync hangs.

**Fix**:
1. Check your internet connection
2. Check the UEM provider's status page
3. Increase the timeout in config (if supported)
4. Try with a smaller device set (filter by status)

## Sync

### Devices not updating

**Symptom**: Device list is stale.

**Fix**:
1. Force a sync: `lucidfence sync --force`
2. Check the sync logs for errors
3. Verify the provider connection is active
4. Check if the UEM API has rate limiting

### Missing devices

**Symptom**: Some devices don't appear.

**Fix**:
1. Check device filters in your UEM console
2. Verify the device has location data
3. Check if the device is marked as inactive/retired
4. Run a full sync (not incremental)

## Configuration

### Config file not found

**Symptom**: "Config file not found" error.

**Fix**:
1. Run `lucidfence init` to create a default config
2. Or specify the config path: `lucidfence server --config /path/to/config.json`

### Invalid JSON in config

**Symptom**: "Invalid config" or JSON parse error.

**Fix**:
1. Validate the JSON: `python3 -m json.tool config.json`
2. Check for trailing commas, unquoted keys, etc.
3. Use `lucidfence validate` to check the config

### Sensitive data in config

**Best practice**: Don't store API keys in the config file. Use environment variables instead:

```bash
export APPLIVERY_API_KEY="your-key"
export APPLIVERY_ORG_ID="your-org"
lucidfence server
```

## Performance

### Server is slow

**Symptom**: Dashboard loads slowly, sync takes long.

**Fix**:
1. Check the number of devices — large fleets take longer
2. Reduce sync frequency if needed
3. Check system resources (CPU, memory, disk)
4. Use dry_run mode for testing to reduce API calls

## Getting Help

- Check the [installation guide](./installation.md)
- Check the [quick start guide](./quickstart.md)
- Check the [configuration reference](./configuration.md)
- File an issue on GitHub: https://github.com/adrimg3196/lucidfence/issues
- For security issues, see SECURITY.md
