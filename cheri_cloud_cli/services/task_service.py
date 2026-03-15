"""Task definition and execution services for Cheri."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

import click

from ..client import CheriClient, CheriClientError
from ..files.service import upload_path_once
from ..sessions import JsonCredentialStore, load_authenticated_state
from ..task.logging import TaskLogStore
from ..task.models import TaskDefinition, TaskLogEntry, TaskRuntimeState, iso_now
from ..task.registry import TaskRegistry
from ..task.runtime import (
    TaskScanResult,
    normalize_target_path,
    prime_runtime_state,
    scan_task,
    target_label,
)
from ..task.scheduler import interval_seconds, next_interval_timestamp, parse_every
from ..task.watcher import clear_pending_change, watcher_active
from ..workspace import resolve_workspace_reference


SUPPORTED_MODES = {"interval", "on-change", "instant", "hybrid"}
SUPPORTED_DIRECTIONS = {"upload-only"}
RUN_LOCK_WINDOW = timedelta(minutes=10)


@dataclass
class TaskExecutionResult:
    task: TaskDefinition
    log_entry: TaskLogEntry
    changed_paths: list[str]
    deleted_paths: list[str]
    uploaded_count: int
    dry_run: bool = False


class TaskService:
    def __init__(self, registry: Optional[TaskRegistry] = None, log_store: Optional[TaskLogStore] = None) -> None:
        self.registry = registry or TaskRegistry()
        self.log_store = log_store or TaskLogStore()

    def list_tasks(self) -> list[TaskDefinition]:
        return sorted(self.registry.list_tasks(), key=lambda task: (task.workspace_name.lower(), task.created_at, task.id))

    def get_task(self, task_id: str) -> TaskDefinition:
        task = self.registry.get_task(task_id)
        if not task:
            raise click.ClickException(f"Task not found: {task_id}")
        return task

    def effective_status(self, task: TaskDefinition) -> str:
        return self._resting_status(task, self.registry.get_runtime(task.id))

    def create_task(
        self,
        client: CheriClient,
        store: JsonCredentialStore,
        *,
        target_type: str,
        target_path: str,
        workspace: Optional[str],
        mode: Optional[str],
        every: str,
        debounce_seconds: int,
        recursive: bool,
        include_patterns: Sequence[str],
        exclude_patterns: Sequence[str],
        direction: str,
        conflict_strategy: str,
        watch_poll_seconds: float,
        enabled: bool = True,
    ) -> TaskDefinition:
        state = load_authenticated_state(client, store)
        workspace_summary = resolve_workspace_reference(state, workspace or state.active_workspace_id)
        if not workspace_summary:
            raise click.ClickException("Workspace not found or no active workspace is selected.")
        self._assert_workspace_ready(workspace_summary)

        resolved_path = normalize_target_path(target_path, target_type)
        sync_mode = self._normalize_mode(target_type, mode, every)
        interval_value = 0
        interval_unit = ""
        if every:
            interval_value, interval_unit = parse_every(every)
        if sync_mode in {"interval", "hybrid"} and not interval_value:
            raise click.ClickException("Interval and hybrid tasks require --every.")
        if direction not in SUPPORTED_DIRECTIONS:
            raise click.ClickException("Only upload-only task direction is supported in this build.")

        now = iso_now()
        task = TaskDefinition(
            id=f"task_{secrets.token_hex(5)}",
            workspace_id=workspace_summary.id,
            workspace_name=workspace_summary.name,
            target_type=target_type,
            target_path=str(resolved_path),
            sync_mode=sync_mode,
            interval_value=interval_value,
            interval_unit=interval_unit,
            enabled=enabled,
            debounce_seconds=max(debounce_seconds, 0 if sync_mode == "instant" else 2),
            recursive=recursive if target_type == "directory" else False,
            include_patterns=list(include_patterns),
            exclude_patterns=list(exclude_patterns),
            status="idle" if enabled else "stopped",
            created_by=state.user.username,
            created_at=now,
            updated_at=now,
            direction=direction,
            conflict_strategy=conflict_strategy,
            watch_poll_seconds=max(watch_poll_seconds, 0.5),
        )
        runtime = TaskRuntimeState(task_id=task.id, updated_at=now)
        if enabled and sync_mode in {"on-change", "instant", "hybrid"}:
            runtime = prime_runtime_state(task, runtime)
        if enabled and sync_mode in {"interval", "hybrid"}:
            runtime.next_interval_run_at = next_interval_timestamp(task)
        self.registry.upsert_task(task)
        self.registry.save_runtime(runtime)
        self._sync_remote_task_registry(client, state, task)
        return task

    def pause_task(
        self,
        task_id: str,
        *,
        client: Optional[CheriClient] = None,
        store: Optional[JsonCredentialStore] = None,
    ) -> TaskDefinition:
        task = self.get_task(task_id)
        task.enabled = False
        task.status = "stopped"
        task.updated_at = iso_now()
        self.registry.upsert_task(task)
        if client and store:
            try:
                self._sync_remote_task_registry(client, load_authenticated_state(client, store), task)
            except Exception:
                pass
        return task

    def resume_task(
        self,
        task_id: str,
        *,
        client: Optional[CheriClient] = None,
        store: Optional[JsonCredentialStore] = None,
    ) -> TaskDefinition:
        task = self.get_task(task_id)
        task.enabled = True
        task.status = "idle"
        task.last_error = ""
        task.updated_at = iso_now()
        runtime = self.registry.get_runtime(task.id)
        if task.sync_mode in {"on-change", "instant", "hybrid"} and not runtime.snapshot:
            runtime = prime_runtime_state(task, runtime)
        if task.sync_mode in {"interval", "hybrid"}:
            runtime.next_interval_run_at = next_interval_timestamp(task)
        self.registry.save_runtime(runtime)
        self.registry.upsert_task(task)
        if client and store:
            try:
                self._sync_remote_task_registry(client, load_authenticated_state(client, store), task)
            except Exception:
                pass
        return task

    def remove_task(
        self,
        task_id: str,
        *,
        client: Optional[CheriClient] = None,
        store: Optional[JsonCredentialStore] = None,
    ) -> TaskDefinition:
        task = self.get_task(task_id)
        self.registry.remove_task(task_id)
        self.registry.remove_runtime(task_id)
        self.log_store.remove_task_logs(task_id)
        if client and store:
            try:
                self._remove_remote_task_registry(client, load_authenticated_state(client, store), task)
            except Exception:
                pass
        return task

    def list_logs(self, task_id: str) -> list[TaskLogEntry]:
        self.get_task(task_id)
        return self.log_store.list_logs(task_id=task_id)

    def execute_task(
        self,
        task_id: str,
        client: CheriClient,
        store: JsonCredentialStore,
        *,
        dry_run: bool = False,
        scan_result: Optional[TaskScanResult] = None,
    ) -> TaskExecutionResult:
        task = self.get_task(task_id)
        runtime = self.registry.get_runtime(task.id)
        started_at = iso_now()
        run_id = f"run_{secrets.token_hex(6)}"
        self._acquire_run_lock(task, runtime, run_id, started_at)
        try:
            state = load_authenticated_state(client, store)
            workspace_summary = resolve_workspace_reference(state, task.workspace_id)
            if not workspace_summary:
                raise click.ClickException("Task workspace is no longer accessible for this user.")
            self._assert_workspace_ready(workspace_summary)
            self._assert_direction_supported(task)

            scan = scan_result or scan_task(task, runtime)
            details: list[str] = []
            uploaded_count = 0

            if not scan.changed_paths and not scan.deleted_paths:
                status = "noop"
                summary = "No changes detected."
            else:
                for relative_path in scan.deleted_paths:
                    details.append(f"Deleted locally and ignored by upload-only mode: {relative_path}")
                if dry_run:
                    status = "dry-run"
                    summary = f"Would upload {len(scan.changed_paths)} file(s)."
                    for relative_path in scan.changed_paths:
                        details.append(f"Would upload {relative_path}")
                else:
                    for relative_path in scan.changed_paths:
                        remote_file = upload_path_once(
                            client,
                            state,
                            scan.path_map[relative_path],
                            workspace_id=task.workspace_id,
                            show_progress=False,
                            logical_name=relative_path,
                        )
                        uploaded_count += 1
                        details.append(f"Uploaded {relative_path} as {remote_file.id}")
                    status = "success"
                    summary = f"Uploaded {uploaded_count} file(s)."

            finished_at = iso_now()
            runtime.snapshot = scan.current_snapshot
            runtime.next_interval_run_at = next_interval_timestamp(task) if interval_seconds(task) else ""
            runtime.active_run_id = ""
            runtime.active_run_started_at = ""
            clear_pending_change(runtime)
            self.registry.save_runtime(runtime)

            task.last_run_at = finished_at
            task.last_success_at = finished_at
            task.last_error = ""
            task.status = self._resting_status(task, runtime)
            task.updated_at = finished_at
            self.registry.upsert_task(task)
            self._sync_remote_task_registry(client, state, task)

            log_entry = TaskLogEntry(
                id=f"log_{secrets.token_hex(6)}",
                task_id=task.id,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                summary=summary,
                target_label=target_label(task),
                workspace_name=task.workspace_name,
                mode=task.sync_mode,
                dry_run=dry_run,
                uploaded_count=uploaded_count,
                changed_count=len(scan.changed_paths),
                deleted_count=len(scan.deleted_paths),
                skipped_count=max(len(scan.deleted_paths), 0),
                details=details,
            )
            self.log_store.append(log_entry)
            self._record_activity(
                client,
                state,
                task,
                action=f"task_sync_{status.replace('-', '_')}",
                summary=summary,
                status=status,
                uploaded_count=uploaded_count,
                changed_count=len(scan.changed_paths),
                deleted_count=len(scan.deleted_paths),
                dry_run=dry_run,
            )
            return TaskExecutionResult(
                task=task,
                log_entry=log_entry,
                changed_paths=list(scan.changed_paths),
                deleted_paths=list(scan.deleted_paths),
                uploaded_count=uploaded_count,
                dry_run=dry_run,
            )
        except Exception as exc:
            finished_at = iso_now()
            task.last_run_at = finished_at
            task.last_error = str(exc)
            task.status = "error"
            task.updated_at = finished_at
            runtime.next_interval_run_at = next_interval_timestamp(task) if interval_seconds(task) else runtime.next_interval_run_at
            runtime.active_run_id = ""
            runtime.active_run_started_at = ""
            clear_pending_change(runtime)
            self.registry.save_runtime(runtime)
            self.registry.upsert_task(task)
            try:
                state = load_authenticated_state(client, store)
                self._sync_remote_task_registry(client, state, task)
            except Exception:
                pass
            log_entry = TaskLogEntry(
                id=f"log_{secrets.token_hex(6)}",
                task_id=task.id,
                started_at=started_at,
                finished_at=finished_at,
                status="error",
                summary="Task execution failed.",
                target_label=target_label(task),
                workspace_name=task.workspace_name,
                mode=task.sync_mode,
                dry_run=dry_run,
                error=str(exc),
                details=[str(exc)],
            )
            self.log_store.append(log_entry)
            try:
                state = load_authenticated_state(client, store)
                self._record_activity(
                    client,
                    state,
                    task,
                    action="task_sync_error",
                    summary="Task execution failed.",
                    status="error",
                    uploaded_count=0,
                    changed_count=0,
                    deleted_count=0,
                    dry_run=dry_run,
                )
            except Exception:
                pass
            raise

    def _record_activity(
        self,
        client: CheriClient,
        state,
        task: TaskDefinition,
        *,
        action: str,
        summary: str,
        status: str,
        uploaded_count: int,
        changed_count: int,
        deleted_count: int,
        dry_run: bool,
    ) -> None:
        try:
            client.record_task_event(
                state,
                workspace_id=task.workspace_id,
                action=action,
                summary=summary,
                metadata={
                    "task_id": task.id,
                    "target": target_label(task),
                    "mode": task.sync_mode,
                    "status": status,
                    "uploaded_count": uploaded_count,
                    "changed_count": changed_count,
                    "deleted_count": deleted_count,
                    "dry_run": dry_run,
                },
            )
        except CheriClientError:
            return

    def _sync_remote_task_registry(self, client: CheriClient, state, task: TaskDefinition) -> None:
        try:
            client.upsert_task_registry_record(
                state,
                workspace_id=task.workspace_id,
                task_payload={
                    "id": task.id,
                    "workspace_id": task.workspace_id,
                    "workspace_name": task.workspace_name,
                    "target_type": task.target_type,
                    "target_label": target_label(task),
                    "sync_mode": task.sync_mode,
                    "interval_value": task.interval_value,
                    "interval_unit": task.interval_unit,
                    "enabled": task.enabled,
                    "debounce_seconds": task.debounce_seconds,
                    "recursive": task.recursive,
                    "include_patterns": list(task.include_patterns),
                    "exclude_patterns": list(task.exclude_patterns),
                    "status": task.status,
                    "last_run_at": task.last_run_at,
                    "last_success_at": task.last_success_at,
                    "last_error": task.last_error,
                    "created_by": task.created_by,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "direction": task.direction,
                    "conflict_strategy": task.conflict_strategy,
                    "watch_poll_seconds": task.watch_poll_seconds,
                },
            )
        except CheriClientError:
            return

    def _remove_remote_task_registry(self, client: CheriClient, state, task: TaskDefinition) -> None:
        try:
            client.delete_task_registry_record(state, workspace_id=task.workspace_id, task_id=task.id)
        except CheriClientError:
            return

    def _assert_workspace_ready(self, workspace_summary) -> None:
        validation = workspace_summary.provider.validation
        if not validation.available:
            raise click.ClickException(
                f"Workspace provider {workspace_summary.provider.label} is not available for automated sync in this deployment."
            )

    def _assert_direction_supported(self, task: TaskDefinition) -> None:
        if task.direction != "upload-only":
            raise click.ClickException("Only upload-only task direction is supported in this build.")

    def _normalize_mode(self, target_type: str, requested_mode: Optional[str], every: str) -> str:
        if requested_mode:
            normalized = requested_mode.strip().lower()
        elif every:
            normalized = "interval"
        else:
            normalized = "on-change" if target_type == "directory" else "instant"
        if normalized not in SUPPORTED_MODES:
            raise click.ClickException("Task mode must be interval, on-change, instant, or hybrid.")
        return normalized

    def _acquire_run_lock(self, task: TaskDefinition, runtime: TaskRuntimeState, run_id: str, started_at: str) -> None:
        if runtime.active_run_started_at:
            try:
                active_started_at = datetime.fromisoformat(runtime.active_run_started_at)
            except ValueError:
                active_started_at = None
            if active_started_at and (datetime.now(tz=timezone.utc) - active_started_at) < RUN_LOCK_WINDOW:
                raise click.ClickException(f"Task {task.id} is already running.")
        runtime.active_run_id = run_id
        runtime.active_run_started_at = started_at
        self.registry.save_runtime(runtime)
        task.status = "running"
        task.updated_at = started_at
        self.registry.upsert_task(task)

    def _resting_status(self, task: TaskDefinition, runtime: TaskRuntimeState) -> str:
        if not task.enabled:
            return "stopped"
        if task.status == "error":
            return "error"
        if runtime.active_run_id:
            return "running"
        if watcher_active(task, runtime):
            return "watching"
        return "idle"
