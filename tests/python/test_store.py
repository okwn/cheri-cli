import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheri_cloud_cli.contracts import AuthState
from cheri_cloud_cli.sessions.store import JsonCredentialStore


def sample_auth_state() -> AuthState:
    return AuthState.from_payload(
        {
            "identity": {
                "id": "usr_123",
                "username": "alice",
                "created_at": "2026-03-15T00:00:00+00:00",
            },
            "session": {
                "token": "tok_1234567890abcdef",
                "issued_at": "2026-03-15T00:00:00+00:00",
                "id": "ses_123",
            },
            "bootstrap": {
                "secret": "amber anchor apple atlas bamboo beacon berry birch candle cedar cloud cobalt",
            },
            "workspace_access": {
                "active_workspace_id": "ws_123",
                "workspaces": [
                    {
                        "id": "ws_123",
                        "name": "docs",
                        "slug": "docs",
                        "role": "admin",
                        "created_at": "2026-03-15T00:00:00+00:00",
                        "joined_at": "2026-03-15T00:00:00+00:00",
                        "provider": {
                            "kind": "system",
                            "label": "System (recommended)",
                            "temporary": True,
                            "recommended": True,
                            "reset_policy": "daily",
                            "validation": {"state": "ready", "available": True},
                        },
                    }
                ],
            },
        }
    )


class JsonCredentialStoreTests(unittest.TestCase):
    def test_store_splits_public_and_secret_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": temp_dir}, clear=False):
                store = JsonCredentialStore()
                state = sample_auth_state()

                store.save(state, persist_bootstrap_secret=False)

                public_payload = json.loads(Path(store.location).read_text(encoding="utf-8"))
                secret_payload = json.loads(Path(store.secret_location).read_text(encoding="utf-8"))

                self.assertIn("identity", public_payload)
                self.assertIn("workspace_access", public_payload)
                self.assertNotIn("session", public_payload)
                self.assertNotIn("bootstrap", public_payload)

                self.assertIn("session", secret_payload)
                self.assertEqual(secret_payload["session"]["token"], state.session_token)
                self.assertEqual(secret_payload["bootstrap"]["secret"], "")

                loaded = store.load()
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded.session_token, state.session_token)
                self.assertEqual(loaded.bootstrap_secret, "")

    def test_store_can_persist_bootstrap_secret_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": temp_dir}, clear=False):
                store = JsonCredentialStore()
                state = sample_auth_state()

                store.save(state, persist_bootstrap_secret=True)

                loaded = store.load()
                self.assertEqual(loaded.bootstrap_secret, state.bootstrap_secret)


if __name__ == "__main__":
    unittest.main()
