import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheri_cloud_cli.config import CheriConfigError, resolve_api_url, set_saved_api_url
from cheri_cloud_cli.deployment import load_deployment_info


WRANGLER_INFO = """# Cheri Wrangler Information
Worker name: cheri-sync-api
Worker API base URL: https://cheri.parapanteri.com
Custom domain: cheri.parapanteri.com

KV binding: CHERI_KV
KV id: 00000000000000000000000000000000

R2 binding: cheri_files
R2 bucket: cheri-files
"""


WRANGLER_TOML = """name = "cheri-sync-api"
main = "index.js"

[[kv_namespaces]]
binding = "HERMES_KV"
id = "00000000000000000000000000000000"

[[r2_buckets]]
binding = "HERMES_BUCKET"
bucket_name = "cheri-files"

[[routes]]
pattern = "cheri.parapanteri.com"
custom_domain = true
"""


class ConfigResolutionTests(unittest.TestCase):
    def test_deployment_info_normalizes_wranger_metadata_and_route(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            (repo / "wrangler_information.txt").write_text(WRANGLER_INFO, encoding="utf-8")
            (repo / "wrangler.toml").write_text(WRANGLER_TOML, encoding="utf-8")

            with patch.dict(os.environ, {"CHERI_REPO_ROOT": str(repo)}, clear=False):
                deployment = load_deployment_info()

            self.assertEqual(deployment.api_url, "https://cheri.parapanteri.com")
            self.assertEqual(deployment.kv_binding, "HERMES_KV")
            self.assertEqual(deployment.r2_binding, "HERMES_BUCKET")
            self.assertEqual(deployment.bucket_name, "cheri-files")
            self.assertTrue(any("Normalized KV binding" in note for note in deployment.notes))

    def test_api_url_resolution_prefers_environment_then_local_then_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as config_dir, tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            (repo / "wrangler_information.txt").write_text(WRANGLER_INFO, encoding="utf-8")
            (repo / "wrangler.toml").write_text(WRANGLER_TOML, encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "CHERI_CONFIG_DIR": config_dir,
                    "CHERI_REPO_ROOT": str(repo),
                },
                clear=False,
            ):
                resolved = resolve_api_url()
                self.assertEqual(resolved.url, "https://cheri.parapanteri.com")
                self.assertEqual(resolved.source, "deployment_metadata")

                saved = set_saved_api_url("https://saved.example.com")
                self.assertEqual(saved, "https://saved.example.com")
                resolved = resolve_api_url()
                self.assertEqual(resolved.url, "https://saved.example.com")
                self.assertEqual(resolved.source, "local_config")

                with patch.dict(os.environ, {"CHERI_API_URL": "https://env.example.com"}, clear=False):
                    resolved = resolve_api_url()
                    self.assertEqual(resolved.url, "https://env.example.com")
                    self.assertEqual(resolved.source, "environment:CHERI_API_URL")

    def test_invalid_api_url_is_rejected_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as config_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                with self.assertRaises(CheriConfigError) as ctx:
                    set_saved_api_url("cheri.parapanteri.com")
        self.assertIn("Invalid API URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
