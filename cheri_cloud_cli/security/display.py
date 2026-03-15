"""Console helpers for secret-safe presentation."""

from __future__ import annotations

import json
from typing import Any, Dict

import click
from rich.console import Console
from rich.panel import Panel

from ..contracts import AuthState


def mask_token(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:6]}...{token[-4:]}"


def mask_secret(secret: str) -> str:
    words = secret.split()
    if len(words) <= 2:
        return secret
    return f"{' '.join(words[:2])} ..."


def copy_ready_payload(state: AuthState) -> str:
    payload: Dict[str, Any] = {
        "identity": state.user.to_dict(),
        "bootstrap": {"secret": state.bootstrap_secret},
        "session": {
            "token": state.session_token,
            "issued_at": state.issued_at,
        },
        "workspace_access": {
            "active_workspace_id": state.active_workspace_id,
            "workspaces": [workspace.to_dict() for workspace in state.workspaces],
        },
    }
    return json.dumps(payload, indent=2)


def print_copy_ready_payload(console: Console, state: AuthState) -> None:
    console.print(
        Panel.fit(
            "Local persistence was skipped.\n\nIdentity, bootstrap secret, session token, and workspace access are printed below for manual copy.",
            title="Copy Ready Output",
            border_style="yellow",
        )
    )
    click.echo(copy_ready_payload(state))
