"""Operator-facing CLI configuration flows."""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import CheriClient
from ..config import (
    ENV_API_URL_KEYS,
    CheriConfigError,
    get_paths,
    load_cli_settings,
    reset_cli_settings,
    resolve_api_url,
    set_saved_api_url,
)
from ..deployment import load_deployment_info


def _source_label(source: str) -> str:
    if source == "local_config":
        return "saved local config"
    if source == "deployment_metadata":
        return "deployment metadata"
    if source.startswith("environment:"):
        return source.split(":", 1)[1]
    return source


def show_config(console: Console) -> None:
    paths = get_paths()
    deployment = load_deployment_info()
    settings = load_cli_settings(paths)
    current_url = "-"
    current_source = "-"
    resolution_error = ""
    try:
        resolved = resolve_api_url(paths)
    except CheriConfigError as exc:
        resolution_error = str(exc)
    else:
        current_url = resolved.url
        current_source = _source_label(resolved.source)

    table = Table(title="Cheri Configuration", border_style="blue")
    table.add_column("Setting", style="cyan", width=26)
    table.add_column("Value", style="white")
    table.add_row("Current API URL", current_url)
    table.add_row("Current source", current_source)
    table.add_row("Saved API URL", settings.api_url or "-")
    table.add_row("Config file", str(paths.settings_file))
    table.add_row("Default Worker domain", deployment.api_url or "-")
    table.add_row("KV binding", f"{deployment.kv_binding} ({deployment.kv_id or '-'})")
    table.add_row("R2 binding", f"{deployment.r2_binding} ({deployment.bucket_name or '-'})")
    table.add_row("Wrangler info", deployment.wrangler_information_path or "embedded deployment snapshot")
    table.add_row("Wrangler toml", deployment.wrangler_toml_path or "embedded deployment snapshot")
    console.print(table)

    env_rows = [f"{key}={value}" for key in ENV_API_URL_KEYS if (value := os.environ.get(key, "").strip())]
    console.print(
        Panel.fit(
            "\n".join(env_rows) if env_rows else "No environment override is currently set.",
            title="Environment Overrides",
            border_style="yellow" if env_rows else "dim",
        )
    )

    if deployment.notes:
        console.print(
            Panel.fit(
                "\n".join(f"- {note}" for note in deployment.notes),
                title="Deployment Notes",
                border_style="dim",
            )
        )

    if resolution_error:
        console.print(Panel.fit(resolution_error, title="Configuration Error", border_style="red"))


def set_api_url(console: Console, api_url: str) -> None:
    normalized = set_saved_api_url(api_url)
    console.print(
        Panel.fit(
            f"Saved API URL:\n\n{normalized}",
            title="Cheri Config Updated",
            border_style="green",
        )
    )


def reset_config(console: Console) -> None:
    reset_cli_settings()
    resolved = resolve_api_url()
    console.print(
        Panel.fit(
            f"Saved local config cleared.\n\nCurrent fallback API URL:\n{resolved.url}",
            title="Cheri Config Reset",
            border_style="yellow",
        )
    )


def check_backend(console: Console, client: CheriClient) -> None:
    payload = client.healthcheck()
    console.print(
        Panel.fit(
            f"API URL    : {client.base_url}\n"
            f"Product    : {payload.get('product', '-')}\n"
            f"Mode       : {payload.get('mode', '-')}\n"
            f"Blob store : {payload.get('backend_foundation', {}).get('blob_storage', '-')}\n"
            f"Registry   : {payload.get('backend_foundation', {}).get('registry_storage', '-')}",
            title="Backend Reachable",
            border_style="green",
        )
    )
