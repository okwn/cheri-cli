"""Interactive auth flows."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from ..client import CheriClient, CheriClientError
from ..contracts import AuthState
from ..providers import prompt_for_provider
from ..security import mask_secret, mask_token, print_copy_ready_payload
from ..sessions import JsonCredentialStore


def _summarize_state(console: Console, state: AuthState, title: str) -> None:
    workspace = state.active_workspace
    console.print(
        Panel.fit(
            f"Identity        : {state.user.username}\n"
            f"Active workspace: {(workspace.name if workspace else '-')} ({state.active_workspace_id or '-'})\n"
            f"Membership role : {(workspace.role if workspace else '-')}\n"
            f"Session token   : {mask_token(state.session_token)}\n"
            f"Bootstrap secret: {mask_secret(state.bootstrap_secret) if state.bootstrap_secret else '-'}",
            title=title,
            border_style="green",
        )
    )


def _save_or_print(console: Console, store: JsonCredentialStore, state: AuthState, *, prompt_user: bool) -> None:
    should_save = store.has_saved_state()
    persist_bootstrap_secret = False
    if prompt_user:
        should_save = click.confirm(
            "Save the Cheri session and workspace access locally on this machine?",
            default=True,
        )
    if should_save:
        if state.bootstrap_secret:
            persist_bootstrap_secret = click.confirm(
                "Also store the 12-word bootstrap secret locally for future login?",
                default=False,
            )
        store.save(state, persist_bootstrap_secret=persist_bootstrap_secret)
        console.print(
            "[green]Saved[/] local Cheri state.\n"
            f"Public state      : [white]{store.location}[/]\n"
            f"Sensitive session : [white]{store.secret_location}[/]\n"
            f"Bootstrap secret  : [{'green' if persist_bootstrap_secret else 'yellow'}]"
            f"{'stored' if persist_bootstrap_secret else 'not stored'}[/]"
        )
        return
    store.clear()
    print_copy_ready_payload(console, state)


def _bootstrap_registration(console: Console, client: CheriClient, store: JsonCredentialStore, *, invite_code: str = "") -> AuthState:
    username = click.prompt("Username").strip()
    workspace_name = click.prompt("Initial workspace name", default=f"{username} workspace").strip()
    provider = prompt_for_provider(console, client)
    state = client.register(username=username, workspace_name=workspace_name, provider=provider)
    if invite_code:
        state = client.accept_team_invite(state, invite_code)
    _summarize_state(console, state, "Cheri Registered")
    console.print(
        Panel.fit(
            f"Your bootstrap secret:\n\n{state.bootstrap_secret}",
            title="Bootstrap Secret",
            border_style="yellow",
        )
    )
    _save_or_print(console, store, state, prompt_user=True)
    return state


def register(console: Console, client: CheriClient, store: JsonCredentialStore) -> None:
    _bootstrap_registration(console, client, store)


def login(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    *,
    invite_code: str = "",
    force: bool = False,
) -> None:
    existing = None if force else store.load()
    if existing and existing.session_token:
        try:
            refreshed = client.get_session(existing)
        except CheriClientError:
            store.clear()
        else:
            if invite_code:
                refreshed = client.accept_team_invite(refreshed, invite_code)
            store.save(refreshed)
            _summarize_state(console, refreshed, "Cheri Session")
            return

    default_username = existing.user.username if existing else ""
    username = click.prompt("Username", default=default_username or None).strip()
    bootstrap_secret = existing.bootstrap_secret if existing else ""

    if bootstrap_secret and click.confirm("Use the saved bootstrap secret for login?", default=True):
        pass
    else:
        has_secret = click.confirm("Do you already have a 12-word bootstrap secret?", default=bool(bootstrap_secret))
        if not has_secret:
            _bootstrap_registration(console, client, store, invite_code=invite_code)
            return
        bootstrap_secret = click.prompt("Bootstrap secret", hide_input=True).strip()

    state = client.login(username=username, bootstrap_secret=bootstrap_secret)
    if invite_code:
        state = client.accept_team_invite(state, invite_code)
    _summarize_state(console, state, "Cheri Login")
    _save_or_print(console, store, state, prompt_user=not store.has_saved_state())


def logout(console: Console, client: CheriClient, store: JsonCredentialStore) -> None:
    state = store.load()
    if not state:
        console.print("[yellow]No saved session found.[/]")
        return
    if click.confirm("Log out and remove local Cheri credentials?", default=True):
        try:
            client.logout(state)
        finally:
            store.clear()
        console.print("[green]Logged out.[/]")
