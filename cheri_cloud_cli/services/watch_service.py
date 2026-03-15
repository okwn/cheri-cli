"""Watch-loop orchestration for Cheri task automation."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from ..client import CheriClient
from ..sessions import JsonCredentialStore, load_authenticated_state
from ..task.models import TaskDefinition, iso_now
from ..task.registry import TaskRegistry
from ..task.runtime import prime_runtime_state, scan_task
from ..task.scheduler import interval_due, next_interval_timestamp
from ..task.watcher import (
    clear_pending_change,
    clear_watcher,
    debounce_elapsed,
    has_changes,
    mark_watcher_started,
    note_change,
    poll_interval,
    touch_watcher,
    watcher_active,
)
from ..workspace import resolve_workspace_reference
from .task_service import TaskService


class WatchService:
    def __init__(self, task_service: Optional[TaskService] = None, registry: Optional[TaskRegistry] = None) -> None:
        self.task_service = task_service or TaskService()
        self.registry = registry or self.task_service.registry

    def start_task(self, client: CheriClient, store: JsonCredentialStore, task_id: str) -> TaskDefinition:
        task = self.task_service.resume_task(task_id, client=client, store=store)
        state = load_authenticated_state(client, store)
        workspace_summary = resolve_workspace_reference(state, task.workspace_id)
        if not workspace_summary:
            raise click.ClickException("Task workspace is no longer accessible for this user.")
        self.task_service._assert_workspace_ready(workspace_summary)

        runtime = self.registry.get_runtime(task.id)
        runtime = self._prepare_runtime(task, runtime)
        if watcher_active(task, runtime):
            task.status = "watching"
            task.updated_at = iso_now()
            self.registry.upsert_task(task)
            self._sync_remote_task(client, state, task)
            return task

        log_path = self._watch_log_path(task.id)
        process = self._spawn_background_watcher(task.id, log_path=log_path)
        mark_watcher_started(runtime, pid=process.pid, log_path=log_path)
        self.registry.save_runtime(runtime)

        task.status = "watching"
        task.last_error = ""
        task.updated_at = iso_now()
        self.registry.upsert_task(task)
        self._sync_remote_task(client, state, task)
        return task

    def stop_task(self, client: CheriClient, store: JsonCredentialStore, task_id: str) -> TaskDefinition:
        task = self.task_service.pause_task(task_id, client=client, store=store)
        runtime = self.registry.get_runtime(task.id)
        self._terminate_watcher(runtime.watcher_pid)
        clear_pending_change(runtime)
        clear_watcher(runtime)
        self.registry.save_runtime(runtime)
        task.status = "stopped"
        task.updated_at = iso_now()
        self.registry.upsert_task(task)
        try:
            state = load_authenticated_state(client, store)
        except click.ClickException:
            return task
        self._sync_remote_task(client, state, task)
        return task

    def watch(
        self,
        console: Console,
        client: CheriClient,
        store: JsonCredentialStore,
        *,
        task_id: Optional[str] = None,
        watch_all: bool = False,
        dry_run: bool = False,
        poll_seconds: Optional[float] = None,
        background: bool = False,
    ) -> None:
        tasks = self._select_tasks(task_id=task_id, watch_all=watch_all)
        if not tasks:
            raise click.ClickException("No matching tasks found to watch.")
        if not background:
            background_tasks = [task for task in tasks if watcher_active(task, self.registry.get_runtime(task.id))]
            if task_id and background_tasks:
                raise click.ClickException(
                    f"Task {task_id} is already watching in the background. Use `cheri task stop {task_id}` first."
                )
            if background_tasks:
                tasks = [task for task in tasks if task not in background_tasks]
                if not tasks:
                    raise click.ClickException(
                        "All matching tasks are already watching in the background. Use `cheri task stop <task-id>` first."
                    )

        if not background:
            console.print(
                Panel.fit(
                    "\n".join(f"{task.id}  {task.workspace_name}  {task.mode_label}" for task in tasks),
                    title="Watching Tasks",
                    border_style="cyan",
                )
            )
            console.print("[dim]Press Ctrl+C to stop the watch loop.[/]")

        for task in tasks:
            runtime = self.registry.get_runtime(task.id)
            runtime = self._prepare_runtime(task, runtime)
            if background and task_id and task.id == task_id:
                touch_watcher(runtime)
                self.registry.save_runtime(runtime)
                task.status = "watching"
                task.updated_at = iso_now()
                self.registry.upsert_task(task)

        try:
            while True:
                selected_tasks = self._select_tasks(task_id=task_id, watch_all=watch_all)
                if task_id:
                    selected_tasks = [task for task in selected_tasks if task.enabled]
                if not selected_tasks:
                    if not background:
                        console.print("[yellow]No enabled tasks remain. Stopping watch loop.[/]")
                    return

                sleep_seconds = min(poll_interval(task, poll_seconds) for task in selected_tasks)
                for task in selected_tasks:
                    if not task.enabled or task.status == "running":
                        continue

                    runtime = self.registry.get_runtime(task.id)
                    if background and task_id and task.id == task_id:
                        touch_watcher(runtime)
                        self.registry.save_runtime(runtime)

                    try:
                        self._watch_task_once(
                            console,
                            client,
                            store,
                            task,
                            runtime,
                            dry_run=dry_run,
                            background=background,
                        )
                    except Exception as exc:
                        self._mark_watch_error(task, runtime, str(exc))
                        if not background:
                            console.print(f"[red]{task.id}[/] {exc}")

                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            if not background:
                console.print("\n[yellow]Task watch loop stopped.[/]")
        finally:
            self._finalize_watch_loop(client, store, task_id=task_id, background=background)

    def _select_tasks(self, *, task_id: Optional[str], watch_all: bool) -> list[TaskDefinition]:
        tasks = self.task_service.list_tasks()
        if task_id:
            return [task for task in tasks if task.id == task_id]
        if watch_all:
            return [task for task in tasks if task.enabled]
        return [task for task in tasks if task.enabled]

    def _prepare_runtime(self, task: TaskDefinition, runtime) -> object:
        changed = False
        if task.sync_mode in {"on-change", "instant", "hybrid"} and not runtime.snapshot:
            prime_runtime_state(task, runtime)
            changed = True
        if task.sync_mode in {"interval", "hybrid"} and not runtime.next_interval_run_at:
            runtime.next_interval_run_at = next_interval_timestamp(task)
            changed = True
        if changed:
            self.registry.save_runtime(runtime)
        return runtime

    def _watch_task_once(
        self,
        console: Console,
        client: CheriClient,
        store: JsonCredentialStore,
        task: TaskDefinition,
        runtime,
        *,
        dry_run: bool,
        background: bool,
    ) -> None:
        if task.status == "error":
            return

        ran = False
        if interval_due(task, runtime.next_interval_run_at):
            result = self.task_service.execute_task(task.id, client, store, dry_run=dry_run)
            if not background:
                console.print(f"[green]{result.task.id}[/] {result.log_entry.summary}")
            ran = True
            runtime = self.registry.get_runtime(task.id)

        if task.sync_mode not in {"on-change", "instant", "hybrid"} or ran:
            return

        scan = scan_task(task, runtime)
        if has_changes(scan):
            note_change(runtime)
            self.registry.save_runtime(runtime)
            if task.sync_mode == "instant" or debounce_elapsed(runtime, task):
                result = self.task_service.execute_task(
                    task.id,
                    client,
                    store,
                    dry_run=dry_run,
                    scan_result=scan,
                )
                if not background:
                    console.print(f"[green]{result.task.id}[/] {result.log_entry.summary}")
        elif runtime.last_detected_change_at:
            clear_pending_change(runtime)
            self.registry.save_runtime(runtime)

    def _mark_watch_error(self, task: TaskDefinition, runtime, error: str) -> None:
        clear_pending_change(runtime)
        self.registry.save_runtime(runtime)
        task.last_error = error
        task.status = "error"
        task.updated_at = iso_now()
        self.registry.upsert_task(task)

    def _sync_remote_task(self, client: CheriClient, state, task: TaskDefinition) -> None:
        try:
            self.task_service._sync_remote_task_registry(client, state, task)
        except Exception:
            return

    def _finalize_watch_loop(
        self,
        client: CheriClient,
        store: JsonCredentialStore,
        *,
        task_id: Optional[str],
        background: bool,
    ) -> None:
        if not background or not task_id:
            return
        try:
            task = self.task_service.get_task(task_id)
        except click.ClickException:
            return
        runtime = self.registry.get_runtime(task.id)
        if runtime.watcher_pid != os.getpid():
            return
        clear_watcher(runtime)
        self.registry.save_runtime(runtime)
        if task.status != "error":
            task.status = self.task_service.effective_status(task)
            task.updated_at = iso_now()
            self.registry.upsert_task(task)
        try:
            state = load_authenticated_state(client, store)
        except click.ClickException:
            return
        self._sync_remote_task(client, state, task)

    def _watch_log_path(self, task_id: str) -> Path:
        log_dir = self.registry.paths.config_dir / "task-watchers"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{task_id}.log"

    def _spawn_background_watcher(self, task_id: str, *, log_path: Path) -> subprocess.Popen:
        command = self._watch_command(task_id)
        log_handle = log_path.open("a", encoding="utf-8")
        creationflags = 0
        popen_kwargs: dict[str, object] = {
            "cwd": str(Path.home()),
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            popen_kwargs["creationflags"] = creationflags
        else:
            popen_kwargs["start_new_session"] = True
        try:
            return subprocess.Popen(command, **popen_kwargs)
        finally:
            log_handle.close()

    def _watch_command(self, task_id: str) -> list[str]:
        argv0 = Path(sys.argv[0]).expanduser()
        if argv0.exists():
            return [sys.executable, str(argv0), "task", "watch", task_id, "--background"]
        return [sys.executable, "-m", "cheri_cloud_cli.cli", "task", "watch", task_id, "--background"]

    def _terminate_watcher(self, pid: int) -> None:
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
