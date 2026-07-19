import requests
from core.adapters.base import BaseAdapter
from core.exceptions import AuthError, TransportError

class IntuneAdapter(BaseAdapter):
    def __init__(self, client_id, tenant_id, client_secret):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': 'https://graph.microsoft.com/.default'
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            raise AuthError("Failed to get access token")

    def list_devices(self, org):
        url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices"
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            devices = response.json().get('value', [])
            return [
                {
                    'device_id': device['id'],
                    'platform': device['operatingSystem'],
                    'compliant': device['complianceState'] == 'compliant',
                    'encrypted': device['isEncrypted'],
                    'os_version': device['operatingSystemVersion'],
                    'battery_level': device.get('batteryLevel', None),
                   'storage_free_gb': device.get('freeStorageInBytes', 0) / (1024 ** 3)
                }
                for device in devices
            ]
        else:
            raise TransportError(f"Failed to list devices: {response.status_code}")

    def run_command(self, org, device_id, action, params):
        url = f"https://graph.microsoft.com/v1.0/deviceManagement/managedDevices/{device_id}/{action}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise TransportError(f"Failed to run command: {response.status_code}")

    def map_error(self, error):
        if isinstance(error, requests.exceptions.RequestException):
            return TransportError(str(error))
        elif isinstance(error, AuthError):
            return AuthError(str(error))
        else:
            return error