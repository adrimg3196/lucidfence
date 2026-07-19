import unittest
from unittest.mock import patch, Mock
from core.adapters.jamf import JamfAdapter

class TestJamfAdapter(unittest.TestCase):
    @patch('requests.post')
    @patch('requests.get')
    def test_list_devices(self, mock_get, mock_post):
        mock_post.return_value = Mock(status_code=200, json=lambda: {'token': 'test_token', 'expires': 1000})
        mock_get.return_value = Mock(status_code=200, json=lambda: [
            {
                "id": "1",
                "platform": "iOS",
                "compliant": True,
                "encrypted": True,
                "osVersion": "14.5",
                "batteryLevel": 80,
                "freeDiskSpace": 32
            }
        ])

        adapter = JamfAdapter(jss_url="https://example.com", client_id="test_client_id", client_secret="test_client_secret")
        devices = adapter.list_devices("org")

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_id"], "1")
        self.assertEqual(devices[0]["platform"], "iOS")

    @patch('requests.post')
    def test_run_command(self, mock_post):
        mock_post.side_effect = [
            Mock(status_code=200, json=lambda: {'token': 'test_token', 'expires': 1000}),
            Mock(status_code=200, json=lambda: {'status':'success'})
        ]

        adapter = JamfAdapter(jss_url="https://example.com", client_id="test_client_id", client_secret="test_client_secret")
        result = adapter.run_command("org", "1", "erase", {})

        self.assertEqual(result, {'status':'success'})

if __name__ == '__main__':
    unittest.main()