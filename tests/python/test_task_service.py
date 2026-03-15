import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheri_cloud_cli.contracts import AuthState
from cheri_cloud_cli.services.task_service import TaskService
from cheri_cloud_cli.services.watch_service import WatchService
from cheri_cloud_cli.sessions.store import JsonCredentialStore
from cheri_cloud_cli.task.discovery import search_task_targets


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
            "bootstrap": {"secret": ""},
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


class FakeClient:
    def __init__(self, state: AuthState) -> None:
        self.state = state
        self.registry_updates = []
        self.registry_removals = []
        self.activity_events = []

    def get_session(self, state: AuthState) -> AuthState:
        return self.state

    def upsert_task_registry_record(self, state: AuthState, *, workspace_id: str, task_payload: dict):
        self.registry_updates.append((workspace_id, task_payload))
        return task_payload

    def delete_task_registry_record(self, state: AuthState, *, workspace_id: str, task_id: str) -> None:
        self.registry_removals.append((workspace_id, task_id))

    def record_task_event(self, state: AuthState, *, workspace_id: str, action: str, summary: str, metadata: dict) -> None:
        self.activity_events.append((workspace_id, action, summary, metadata))


class TaskServiceTests(unittest.TestCase):
    def test_task_create_pause_resume_remove_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as config_dir, tempfile.TemporaryDirectory() as workspace_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                store = JsonCredentialStore()
                state = sample_auth_state()
                store.save(state)
                client = FakeClient(state)
                target_file = Path(workspace_dir) / "notes.txt"
                target_file.write_text("hello", encoding="utf-8")

                service = TaskService()
                task = service.create_task(
                    client,
                    store,
                    target_type="file",
                    target_path=str(target_file),
                    workspace=None,
                    mode=None,
                    every="",
                    debounce_seconds=3,
                    recursive=False,
                    include_patterns=(),
                    exclude_patterns=(),
                    direction="upload-only",
                    conflict_strategy="manual-placeholder",
                    watch_poll_seconds=2.0,
                )

                self.assertEqual(task.sync_mode, "instant")
                self.assertEqual(len(service.list_tasks()), 1)
                self.assertTrue(client.registry_updates)

                paused = service.pause_task(task.id, client=client, store=store)
                self.assertFalse(paused.enabled)
                self.assertEqual(paused.status, "stopped")

                resumed = service.resume_task(task.id, client=client, store=store)
                self.assertTrue(resumed.enabled)
                self.assertEqual(resumed.status, "idle")

                service.remove_task(task.id, client=client, store=store)
                self.assertEqual(service.list_tasks(), [])
                self.assertTrue(client.registry_removals)

    def test_task_run_updates_logs_runtime_and_activity(self) -> None:
        with tempfile.TemporaryDirectory() as config_dir, tempfile.TemporaryDirectory() as workspace_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                store = JsonCredentialStore()
                state = sample_auth_state()
                store.save(state)
                client = FakeClient(state)

                target_dir = Path(workspace_dir) / "src"
                target_dir.mkdir()
                tracked_file = target_dir / "app.txt"
                tracked_file.write_text("v1", encoding="utf-8")

                service = TaskService()
                task = service.create_task(
                    client,
                    store,
                    target_type="directory",
                    target_path=str(target_dir),
                    workspace=None,
                    mode="on-change",
                    every="",
                    debounce_seconds=2,
                    recursive=True,
                    include_patterns=(),
                    exclude_patterns=(),
                    direction="upload-only",
                    conflict_strategy="manual-placeholder",
                    watch_poll_seconds=1.0,
                )

                tracked_file.write_text("version-two", encoding="utf-8")

                with patch("cheri_cloud_cli.services.task_service.upload_path_once") as upload_path_once:
                    upload_path_once.return_value = type(
                        "RemoteFile",
                        (),
                        {"id": "file_123", "name": "app.txt", "version": 1},
                    )()
                    result = service.execute_task(task.id, client, store, dry_run=False)

                self.assertEqual(result.uploaded_count, 1)
                self.assertEqual(result.log_entry.status, "success")
                self.assertTrue(service.list_logs(task.id))
                self.assertTrue(client.activity_events)
                self.assertEqual(service.get_task(task.id).status, "idle")

    def test_task_start_and_stop_update_watcher_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as config_dir, tempfile.TemporaryDirectory() as workspace_dir:
            with patch.dict(os.environ, {"CHERI_CONFIG_DIR": config_dir}, clear=False):
                store = JsonCredentialStore()
                state = sample_auth_state()
                store.save(state)
                client = FakeClient(state)
                target_dir = Path(workspace_dir) / "Desktop" / "cheri_test_files"
                target_dir.mkdir(parents=True)

                service = TaskService()
                task = service.create_task(
                    client,
                    store,
                    target_type="directory",
                    target_path=str(target_dir),
                    workspace=None,
                    mode="on-change",
                    every="",
                    debounce_seconds=3,
                    recursive=True,
                    include_patterns=(),
                    exclude_patterns=(),
                    direction="upload-only",
                    conflict_strategy="manual-placeholder",
                    watch_poll_seconds=1.0,
                    enabled=False,
                )
                self.assertEqual(task.status, "stopped")

                with patch("cheri_cloud_cli.services.watch_service.subprocess.Popen") as popen:
                    popen.return_value = type("Process", (), {"pid": 4321})()
                    started = WatchService(task_service=service).start_task(client, store, task.id)

                runtime = service.registry.get_runtime(task.id)
                self.assertEqual(started.status, "watching")
                self.assertEqual(runtime.watcher_pid, 4321)

                with patch("cheri_cloud_cli.services.watch_service.os.kill") as kill:
                    stopped = WatchService(task_service=service).stop_task(client, store, task.id)

                runtime = service.registry.get_runtime(task.id)
                self.assertEqual(stopped.status, "stopped")
                self.assertEqual(runtime.watcher_pid, 0)
                kill.assert_called_once_with(4321, unittest.mock.ANY)

    def test_target_search_falls_back_to_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            home = Path(root_dir) / "home"
            cwd = Path(root_dir) / "workspace"
            desktop = home / "Desktop"
            cwd.mkdir(parents=True)
            desktop.mkdir(parents=True)
            expected_dir = desktop / "cheri_test_files"
            expected_dir.mkdir()

            with patch("pathlib.Path.home", return_value=home):
                result = search_task_targets("cheri_test_files", "directory", cwd=cwd)

            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].path, expected_dir.resolve())
            self.assertEqual(result.candidates[0].source_label, "Desktop")


if __name__ == "__main__":
    unittest.main()
