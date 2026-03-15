"""Activity display for the active workspace."""

from __future__ import annotations

from typing import Optional

from rich import box
from rich.console import Console
from rich.table import Table

from ..client import CheriClient
from ..sessions import JsonCredentialStore, load_authenticated_state
from ..workspace import describe_workspace_target, resolve_workspace_id


def _render_file_table(console: Console, title: str, files) -> None:
    table = Table(box=box.ROUNDED, border_style="blue", title=title)
    table.add_column("Name", style="white", width=30)
    table.add_column("Version", width=8)
    table.add_column("Editor", style="green", width=18)
    table.add_column("Modified", style="dim", width=20)
    if files:
        for item in files:
            table.add_row(item.name, str(item.version), item.editor, item.modified_at[:19])
    else:
        table.add_row("-", "-", "-", "-")
    console.print(table)


def _render_activity_table(console: Console, title: str, entries) -> None:
    table = Table(box=box.ROUNDED, border_style="magenta", title=title)
    table.add_column("When", style="dim", width=20)
    table.add_column("Actor", style="cyan", width=18)
    table.add_column("Action", width=22)
    table.add_column("Summary", style="white")
    if entries:
        for item in entries:
            table.add_row(item.at[:19], item.actor, item.action, item.summary)
    else:
        table.add_row("-", "-", "-", "-")
    console.print(table)


def show_activity(console: Console, client: CheriClient, store: JsonCredentialStore, *, workspace: Optional[str] = None) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    label = describe_workspace_target(state, workspace)
    feed = client.list_activity(state, workspace_id=workspace_id)
    _render_file_table(console, f"Recently Uploaded: {label}", feed.recent_uploads)
    _render_file_table(console, f"Recently Modified: {label}", feed.recent_modified_files)
    _render_activity_table(console, f"Workspace Activity: {label}", feed.recent_actions)
    _render_activity_table(console, f"Collaboration Activity: {label}", feed.recent_collaboration)
