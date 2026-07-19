import requests
from core.adapters.base import BaseAdapter
from core.exceptions import AdapterError

class JamfAdapter(BaseAdapter):
    def __init__(self, jss_url, client_id, client_secret):
        self.jss_url = jss_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires = 0

    def _get_token(self):
        if self.token and self.token_expires > 0:
            return self.token

        auth_url = f"{self.jss_url}/api/v1/auth/token"
        response = requests.post(auth_url, auth=(self.client_id, self.client_secret))
        if response.status_code == 200:
            data = response.json()
            self.token = data['token']
            self.token_expires = data['expires']
            return self.token
        else:
            raise AdapterError(f"Failed to get token: {response.text}")

    def list_devices(self, org):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        devices_url = f"{self.jss_url}/api/v1/devices"
        response = requests.get(devices_url, headers=headers)
        if response.status_code == 200:
            devices = response.json()
            return [
                {
                    "device_id": device["id"],
                    "platform": device["platform"],
                    "compliant": device["compliant"],
                    "encrypted": device["encrypted"],
                    "os_version": device["osVersion"],
                    "battery_level": device["batteryLevel"],
                    "storage_free_gb": device["freeDiskSpace"]
                }
                for device in devices
            ]
        else:
            raise AdapterError(f"Failed to list devices: {response.text}")

    def run_command(self, org, device_id, action, params):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        command_url = f"{self.jss_url}/api/v1/devices/{device_id}/commands"
        payload = {
            "action": action,
            "params": params
        }
        response = requests.post(command_url, json=payload, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise AdapterError(f"Failed to run command: {response.text}")