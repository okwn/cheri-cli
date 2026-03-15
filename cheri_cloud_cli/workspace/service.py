"""Workspace selection and creation flows."""

from __future__ import annotations

from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import CheriClient
from ..contracts import AuthState, WorkspaceSummary
from ..providers import describe_provider, prompt_for_provider
from ..sessions import JsonCredentialStore, load_authenticated_state


def _render_workspaces(console: Console, workspaces, active_workspace_id: str) -> None:
    table = Table(box=box.ROUNDED, border_style="cyan", title="Accessible Workspaces")
    table.add_column("Active", width=8)
    table.add_column("Name", style="white", width=26)
    table.add_column("Id", style="dim", width=18)
    table.add_column("Role", width=10)
    table.add_column("Provider", width=28)
    table.add_column("Joined", style="dim", width=20)
    for workspace in workspaces:
        table.add_row(
            "*" if workspace.id == active_workspace_id else "",
            workspace.name,
            workspace.id,
            workspace.role,
            describe_provider(workspace.provider),
            workspace.joined_at[:19],
        )
    console.print(table)


def resolve_workspace_reference(state: AuthState, identifier: Optional[str]) -> Optional[WorkspaceSummary]:
    if not identifier:
        return state.active_workspace
    normalized = str(identifier).strip()
    if not normalized:
        return state.active_workspace
    return next((workspace for workspace in state.workspaces if workspace.matches(normalized)), None)


def resolve_workspace_id(state: AuthState, identifier: Optional[str]) -> Optional[str]:
    workspace = resolve_workspace_reference(state, identifier)
    if identifier and not workspace:
        raise click.ClickException(f"Workspace not found: {identifier}")
    return workspace.id if workspace else None


def describe_workspace_target(state: AuthState, identifier: Optional[str]) -> str:
    workspace = resolve_workspace_reference(state, identifier)
    if workspace:
        return workspace.name
    return "active workspace"


def list_workspaces(console: Console, client: CheriClient, store: JsonCredentialStore) -> None:
    state = load_authenticated_state(client, store)
    _render_workspaces(console, state.workspaces, state.active_workspace_id)


def use_workspace(console: Console, client: CheriClient, store: JsonCredentialStore, *, identifier: str) -> None:
    state = load_authenticated_state(client, store)
    target = resolve_workspace_reference(state, identifier)
    if not target:
        raise click.ClickException(f"Workspace not found: {identifier}")
    updated = client.select_workspace(state, identifier=target.id)
    store.save(updated)
    console.print(f"[green]Active workspace:[/] [white]{target.name}[/] ({target.id})")
    _render_workspaces(console, updated.workspaces, updated.active_workspace_id)


def create_workspace(console: Console, client: CheriClient, store: JsonCredentialStore, *, name: str) -> None:
    state = load_authenticated_state(client, store)
    existing = resolve_workspace_reference(state, name)
    if existing:
        updated = client.select_workspace(state, identifier=existing.id)
        store.save(updated)
        console.print(f"[green]Workspace already exists.[/] Using [white]{existing.name}[/] ({existing.id}).")
        _render_workspaces(console, updated.workspaces, updated.active_workspace_id)
        return

    provider = prompt_for_provider(console, client)
    updated = client.select_workspace(
        state,
        identifier=name,
        create_if_missing=True,
        provider=provider,
    )
    store.save(updated)
    created = resolve_workspace_reference(updated, name)
    created_label = created.name if created else name
    console.print(f"[green]Created and selected[/] [white]{created_label}[/].")
    _render_workspaces(console, updated.workspaces, updated.active_workspace_id)


def manage_workspace(console: Console, client: CheriClient, store: JsonCredentialStore, *, name: Optional[str]) -> None:
    if not name:
        state = load_authenticated_state(client, store)
        _render_workspaces(console, state.workspaces, state.active_workspace_id)
        return
    create_workspace(console, client, store, name=name)


def join_workspace(console: Console, client: CheriClient, store: JsonCredentialStore, *, invite_code: str) -> None:
    state = load_authenticated_state(client, store)
    updated = client.accept_team_invite(state, invite_code)
    store.save(updated)
    workspace = updated.active_workspace
    console.print(
        Panel.fit(
            f"Joined workspace : {(workspace.name if workspace else '-')}\n"
            f"Active workspace : {updated.active_workspace_id}\n"
            f"Accessible total : {len(updated.workspaces)}",
            title="Workspace Joined",
            border_style="green",
        )
    )
    _render_workspaces(console, updated.workspaces, updated.active_workspace_id)
