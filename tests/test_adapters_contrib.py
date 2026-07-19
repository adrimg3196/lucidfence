import unittest
from unittest.mock import patch, MagicMock
from core.adapters.intune import IntuneAdapter

class TestIntuneAdapter(unittest.TestCase):
    @patch('requests.post')
    @patch('requests.get')
    def test_list_devices(self, mock_get, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'access_token': 'dummy_token'}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'value': [
                {
                    'id': 'device1',
                    'operatingSystem': 'Windows',
                    'complianceState': 'compliant',
                    'isEncrypted': True,
                    'operatingSystemVersion': '10.0.19041.1',
                    'batteryLevel': 80,
                    'freeStorageInBytes': 10737418240
                }
            ]
        }

        adapter = IntuneAdapter(client_id='dummy_client_id', tenant_id='dummy_tenant_id', client_secret='dummy_client_secret')
        devices = adapter.list_devices(org='org1')

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['device_id'], 'device1')
        self.assertEqual(devices[0]['platform'], 'Windows')
        self.assertTrue(devices[0]['compliant'])
        self.assertTrue(devices[0]['encrypted'])
        self.assertEqual(devices[0]['os_version'], '10.0.19041.1')
        self.assertEqual(devices[0]['battery_level'], 80)
        self.assertEqual(devices[0]['storage_free_gb'], 10)

    @patch('requests.post')
    @patch('requests.get')
    def test_run_command(self, mock_get, mock_post):
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {'access_token': 'dummy_token'}),
            MagicMock(status_code=200, json=lambda: {'status':'success'})
        ]

        adapter = IntuneAdapter(client_id='dummy_client_id', tenant_id='dummy_tenant_id', client_secret='dummy_client_secret')
        result = adapter.run_command(org='org1', device_id='device1', action='wipe', params={})

        self.assertEqual(result, {'status':'success'})

if __name__ == '__main__':
    unittest.main()