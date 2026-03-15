"""Team invite and membership flows."""

from __future__ import annotations

from typing import Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import CheriClient
from ..sessions import JsonCredentialStore, load_authenticated_state
from ..workspace import describe_workspace_target, resolve_workspace_id


def _render_invite_state(console: Console, snapshot) -> None:
    state = snapshot.invite_state
    if not state.visible:
        console.print(
            Panel.fit(
                "Invite state is only visible to workspace admins.",
                title="Invite State",
                border_style="dim",
            )
        )
        return
    console.print(
        Panel.fit(
            f"Generation : {state.invite_generation}\n"
            f"Active     : {state.active_count}\n"
            f"Accepted   : {state.accepted_count}\n"
            f"Revoked    : {state.revoked_count}\n"
            f"Expired    : {state.expired_count}",
            title="Invite State",
            border_style="yellow",
        )
    )


def list_team(console: Console, client: CheriClient, store: JsonCredentialStore, *, workspace: Optional[str] = None) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    snapshot = client.list_team(state, workspace_id=workspace_id)

    members = Table(box=box.ROUNDED, border_style="green", title=f"Team Members: {snapshot.workspace.name}")
    members.add_column("User", style="white", width=22)
    members.add_column("Role", width=10)
    members.add_column("Joined", style="dim", width=20)
    for member in snapshot.members:
        members.add_row(member.username, member.role, member.joined_at[:19])
    console.print(members)

    _render_invite_state(console, snapshot)

    invites = Table(box=box.ROUNDED, border_style="yellow", title="Active Invite Codes")
    invites.add_column("Code", style="cyan", width=24)
    invites.add_column("Label", width=20)
    invites.add_column("Expires", style="dim", width=20)
    if snapshot.invites:
        for invite in snapshot.invites:
            invites.add_row(invite.code, invite.label or "-", invite.expires_at[:19])
    else:
        invites.add_row("-", "-", "-")
    console.print(invites)


def create_invite(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    *,
    label: str,
    workspace: Optional[str] = None,
) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    if not label:
        label = click.prompt("Invite label", default="team invite").strip()
    invite = client.create_team_invite(state, label=label, workspace_id=workspace_id)
    console.print(
        Panel.fit(
            f"Workspace : {invite.workspace_name}\n"
            f"Code      : {invite.code}\n"
            f"Expires   : {invite.expires_at[:19]}\n"
            f"Label     : {invite.label or '-'}",
            title="Invite Created",
            border_style="yellow",
        )
    )


def reset_invites(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    *,
    create_replacement: bool = False,
    label: str = "",
    workspace: Optional[str] = None,
) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    workspace_label = describe_workspace_target(state, workspace)
    if not click.confirm(
        f"Revoke all active invite codes for {workspace_label}?",
        default=False,
    ):
        return
    if not create_replacement:
        create_replacement = click.confirm("Create a replacement invite code after the reset?", default=False)
    if create_replacement and not label:
        label = click.prompt("Replacement invite label", default="team invite").strip()
    payload = client.reset_team_invites(
        state,
        workspace_id=workspace_id,
        create_replacement=create_replacement,
        label=label,
    )
    console.print(
        f"[green]Invite generation rotated.[/] "
        f"Revoked [white]{payload.get('revoked_count', 0)}[/] invite(s)."
    )
    invite = payload.get("invite")
    if invite:
        console.print(
            Panel.fit(
                f"Workspace : {invite.get('workspace_name', workspace_label)}\n"
                f"Code      : {invite.get('code', '-')}\n"
                f"Expires   : {str(invite.get('expires_at', ''))[:19]}\n"
                f"Label     : {invite.get('label', '-') or '-'}",
                title="Replacement Invite",
                border_style="yellow",
            )
        )
