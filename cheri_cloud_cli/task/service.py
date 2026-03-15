"""CLI command handlers for Cheri tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import CheriClient
from ..sessions import JsonCredentialStore
from ..services import TaskService, WatchService
from ..task.discovery import TaskTargetCandidate, describe_search_locations, search_task_targets
from ..task.runtime import display_path_label


def _render_tasks(console: Console, tasks) -> None:
    task_service = TaskService()
    table = Table(box=box.ROUNDED, border_style="cyan", title="Cheri Tasks")
    table.add_column("Task Id", style="cyan", width=18)
    table.add_column("Target", style="white", width=34)
    table.add_column("Workspace", width=18)
    table.add_column("Mode", width=24)
    table.add_column("Status", width=12)
    table.add_column("Last Run", style="dim", width=20)
    if not tasks:
        table.add_row("-", "-", "-", "-", "-", "-")
    else:
        for task in tasks:
            table.add_row(
                task.id,
                display_path_label(Path(task.target_path)),
                task.workspace_name,
                task.mode_label,
                task_service.effective_status(task),
                task.last_run_at[:19] if task.last_run_at else "-",
            )
    console.print(table)


def _resolve_target(task_file: Optional[str], task_directory: Optional[str]) -> tuple[str, str]:
    if bool(task_file) == bool(task_directory):
        raise click.ClickException("Specify exactly one of --file or --directory.")
    if task_file:
        return "file", task_file
    return "directory", task_directory or ""


def _resolve_mode(mode: Optional[str], on_change: bool, instant: bool) -> Optional[str]:
    selected = [item for item in [mode, "on-change" if on_change else None, "instant" if instant else None] if item]
    if len(selected) > 1:
        raise click.ClickException("Choose either --mode, --on-change, or --instant.")
    return selected[0] if selected else None


def _render_target_candidates(console: Console, title: str, candidates: Sequence[TaskTargetCandidate]) -> None:
    table = Table(box=box.ROUNDED, border_style="blue", title=title)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Location", style="white", width=18)
    table.add_column("Path", style="dim")
    for index, candidate in enumerate(candidates, start=1):
        table.add_row(str(index), candidate.source_label, str(candidate.path))
    console.print(table)


def _resolve_target_candidate(
    console: Console,
    raw_target: str,
    target_type: str,
    *,
    pick: bool,
) -> TaskTargetCandidate:
    search_result = search_task_targets(raw_target, target_type)
    if not search_result.candidates:
        searched = describe_search_locations(search_result.searched_locations)
        raise click.ClickException(
            f"Could not find the {target_type} target `{raw_target}`.\n\n"
            f"Searched:\n{searched}\n\n"
            "Try `cheri task find <name>` or pass a quoted full path."
        )

    if len(search_result.candidates) == 1 and not pick:
        return search_result.candidates[0]

    _render_target_candidates(console, "Task Target Matches", search_result.candidates)
    selected_index = click.prompt(
        "Select the task target",
        type=click.IntRange(1, len(search_result.candidates)),
        default=1,
    )
    return search_result.candidates[selected_index - 1]


def create_task(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    *,
    task_file: Optional[str],
    task_directory: Optional[str],
    workspace: Optional[str],
    mode: Optional[str],
    on_change: bool,
    instant: bool,
    every: str,
    debounce_seconds: int,
    recursive: bool,
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    direction: str,
    conflict_strategy: str,
    watch_poll_seconds: float,
    no_start: bool,
    pick: bool,
) -> None:
    target_type, raw_target = _resolve_target(task_file, task_directory)
    requested_mode = _resolve_mode(mode, on_change, instant)
    resolved_target = _resolve_target_candidate(console, raw_target, target_type, pick=pick)
    task_service = TaskService()
    task = task_service.create_task(
        client,
        store,
        target_type=target_type,
        target_path=str(resolved_target.path),
        workspace=workspace,
        mode=requested_mode,
        every=every,
        debounce_seconds=debounce_seconds,
        recursive=recursive,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        direction=direction,
        conflict_strategy=conflict_strategy,
        watch_poll_seconds=watch_poll_seconds,
        enabled=not no_start,
    )
    if no_start:
        task.status = "stopped"
    else:
        task = WatchService(task_service=task_service).start_task(client, store, task.id)
    console.print(
        Panel.fit(
            f"Task id       : {task.id}\n"
            f"Workspace     : {task.workspace_name}\n"
            f"Target        : {display_path_label(Path(task.target_path))}\n"
            f"Resolved from : {resolved_target.source_label}\n"
            f"Mode          : {task.mode_label}\n"
            f"Direction     : {task.direction}\n"
            f"Recursive     : {'yes' if task.recursive else 'no'}\n"
            f"Status        : {task.status}\n"
            f"Watcher       : {'started automatically' if not no_start else 'not started'}",
            title="Task Created",
            border_style="green" if not no_start else "yellow",
        )
    )
    if not no_start:
        console.print(f"[green]Watching[/] {display_path_label(Path(task.target_path))} in the background.")
        console.print(f"Use [white]cheri task stop {task.id}[/] to stop it.")


def list_tasks(console: Console) -> None:
    _render_tasks(console, TaskService().list_tasks())


def start_task(console: Console, client: CheriClient, store: JsonCredentialStore, task_id: str) -> None:
    task = WatchService().start_task(client, store, task_id)
    console.print(f"[green]Started[/] [white]{task.id}[/] and resumed background watching.")


def stop_task(console: Console, client: CheriClient, store: JsonCredentialStore, task_id: str) -> None:
    task = WatchService().stop_task(client, store, task_id)
    console.print(f"[yellow]Stopped[/] [white]{task.id}[/]. The task definition is kept locally.")


def pause_task(console: Console, task_id: str) -> None:
    stop_task(console, CheriClient(), JsonCredentialStore(), task_id)


def resume_task(console: Console, task_id: str) -> None:
    start_task(console, CheriClient(), JsonCredentialStore(), task_id)


def remove_task(console: Console, task_id: str) -> None:
    task_service = TaskService()
    task = task_service.get_task(task_id)
    if not click.confirm(f"Remove task {task.id} for {display_path_label(Path(task.target_path))}?", default=False):
        return
    WatchService(task_service=task_service).stop_task(CheriClient(), JsonCredentialStore(), task.id)
    task_service.remove_task(task_id, client=CheriClient(), store=JsonCredentialStore())
    console.print(f"[green]Removed[/] [white]{task.id}[/].")


def run_task(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    task_id: str,
    *,
    dry_run: bool,
) -> None:
    result = TaskService().execute_task(task_id, client, store, dry_run=dry_run)
    console.print(
        Panel.fit(
            f"Task id    : {result.task.id}\n"
            f"Workspace  : {result.task.workspace_name}\n"
            f"Target     : {display_path_label(Path(result.task.target_path))}\n"
            f"Summary    : {result.log_entry.summary}\n"
            f"Changed    : {len(result.changed_paths)}\n"
            f"Deleted    : {len(result.deleted_paths)}\n"
            f"Uploaded   : {result.uploaded_count}\n"
            f"Dry run    : {'yes' if dry_run else 'no'}",
            title="Task Run",
            border_style="green" if result.log_entry.status != "noop" else "yellow",
        )
    )


def show_task_logs(console: Console, task_id: str) -> None:
    task_service = TaskService()
    task = task_service.get_task(task_id)
    logs = task_service.list_logs(task_id)
    table = Table(box=box.ROUNDED, border_style="magenta", title=f"Task Logs: {task.id}")
    table.add_column("Started", style="dim", width=20)
    table.add_column("Status", width=12)
    table.add_column("Summary", style="white")
    if not logs:
        table.add_row("-", "-", "No task runs recorded.")
    else:
        for entry in logs[:20]:
            summary = entry.summary if not entry.error else f"{entry.summary} ({entry.error})"
            table.add_row(entry.started_at[:19], entry.status, summary)
    console.print(table)


def find_task_targets(console: Console, query: str, *, target_type: str = "directory") -> None:
    search_result = search_task_targets(query, target_type)
    if not search_result.candidates:
        searched = describe_search_locations(search_result.searched_locations)
        raise click.ClickException(f"No matching {target_type} found for `{query}`.\n\nSearched:\n{searched}")
    _render_target_candidates(console, "Task Target Matches", search_result.candidates)


def watch_tasks(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    *,
    task_id: Optional[str],
    watch_all: bool,
    dry_run: bool,
    poll_seconds: Optional[float],
    background: bool = False,
) -> None:
    WatchService().watch(
        console,
        client,
        store,
        task_id=task_id,
        watch_all=watch_all,
        dry_run=dry_run,
        poll_seconds=poll_seconds,
        background=background,
    )
