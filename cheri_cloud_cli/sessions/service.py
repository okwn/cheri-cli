"""Helpers for loading and refreshing authenticated state."""

from __future__ import annotations

import click

from ..client import CheriClient, CheriClientError
from ..contracts import AuthState
from .store import JsonCredentialStore


def load_authenticated_state(client: CheriClient, store: JsonCredentialStore) -> AuthState:
    state = store.load()
    if not state:
        raise click.ClickException("No saved session found. Run `cheri login` first.")
    try:
        refreshed = client.get_session(state)
    except CheriClientError as exc:
        store.clear()
        raise click.ClickException(f"{exc}. Run `cheri login` again.") from exc
    store.save(refreshed)
    return refreshed
