import os
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from cheri_cloud_cli.cli import cli


class CliConfigCommandTests(unittest.TestCase):
    def test_config_get_shows_default_backend_url(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as config_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                result = runner.invoke(cli, ["config", "get"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("https://cheri.parapanteri.com", result.output)

    def test_config_set_and_reset_api_url(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as config_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                set_result = runner.invoke(cli, ["config", "set", "api-url", "https://saved.example.com"])
                get_result = runner.invoke(cli, ["config", "get"])
                reset_result = runner.invoke(cli, ["config", "reset"])

        self.assertEqual(set_result.exit_code, 0)
        self.assertIn("https://saved.example.com", set_result.output)
        self.assertEqual(get_result.exit_code, 0)
        self.assertIn("https://saved.example.com", get_result.output)
        self.assertEqual(reset_result.exit_code, 0)
        self.assertIn("https://cheri.parapanteri.com", reset_result.output)

    def test_config_check_reports_backend_health(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as config_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                with patch("cheri_cloud_cli.client.CheriClient.healthcheck") as healthcheck:
                    healthcheck.return_value = {
                        "product": "Cheri CLI API",
                        "mode": "api_only",
                        "backend_foundation": {
                            "blob_storage": "cloudflare_r2",
                            "registry_storage": "cloudflare_kv",
                        },
                    }
                    result = runner.invoke(cli, ["config", "check"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cheri CLI API", result.output)
        self.assertIn("https://cheri.parapanteri.com", result.output)


if __name__ == "__main__":
    unittest.main()
