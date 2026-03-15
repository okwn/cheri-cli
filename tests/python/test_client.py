import unittest
from unittest.mock import patch

import requests

from cheri_cloud_cli.client import CheriClient, CheriClientError


class CheriClientErrorHandlingTests(unittest.TestCase):
    def test_connection_failure_message_is_user_friendly(self) -> None:
        client = CheriClient(base_url="https://cheri.parapanteri.com")
        with patch("requests.request", side_effect=requests.exceptions.ConnectionError("dns failed")):
            with self.assertRaises(CheriClientError) as ctx:
                client.healthcheck()
        message = str(ctx.exception)
        self.assertIn("Connection failed", message)
        self.assertIn("https://cheri.parapanteri.com", message)
        self.assertIn("cheri config set api-url", message)

    def test_invalid_url_message_is_user_friendly(self) -> None:
        client = CheriClient(base_url="https://cheri.parapanteri.com")
        with patch("requests.request", side_effect=requests.exceptions.InvalidURL("bad url")):
            with self.assertRaises(CheriClientError) as ctx:
                client.healthcheck()
        message = str(ctx.exception)
        self.assertIn("Invalid API URL", message)
        self.assertIn("cheri config set api-url", message)


if __name__ == "__main__":
    unittest.main()
