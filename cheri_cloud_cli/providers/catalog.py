"""Provider metadata and CLI prompts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import CheriClient, CheriClientError
from ..contracts import ProviderConfig, ProviderFieldSpec, ProviderMetadata, ProviderValidationState


@dataclass(frozen=True)
class ProviderOption:
    key: str
    label: str
    description: str
    recommended: bool = False
    temporary: bool = False
    selectable: bool = True
    coming_soon: bool = False
    experimental: bool = False
    reset_policy: str = ""
    integration_status: str = ""
    supports_direct_transfers: bool = False
    supports_remote_revision: bool = False
    supports_change_tracking: bool = False
    supports_incremental_sync: bool = False
    fields: Tuple[ProviderFieldSpec, ...] = ()

    @property
    def warning(self) -> str:
        if self.key == "system":
            return "System storage is temporary. Files are reset daily."
        return ""

    @property
    def status_label(self) -> str:
        if self.coming_soon:
            return "Coming soon"
        if self.experimental and not self.selectable:
            return "Experimental"
        if self.integration_status == "connected":
            return "Ready"
        if self.integration_status:
            return self.integration_status.replace("-", " ").title()
        return "Unknown"

    def to_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            description=self.description,
            recommended=self.recommended,
            temporary=self.temporary,
            selectable=self.selectable,
            coming_soon=self.coming_soon,
            experimental=self.experimental,
            reset_policy=self.reset_policy,
            integration_status=self.integration_status,
            supports_direct_transfers=self.supports_direct_transfers,
            supports_remote_revision=self.supports_remote_revision,
            supports_change_tracking=self.supports_change_tracking,
            supports_incremental_sync=self.supports_incremental_sync,
            credential_fields=list(self.fields),
        )


FALLBACK_PROVIDER_OPTIONS: Tuple[ProviderOption, ...] = (
    ProviderOption(
        key="s3-compatible",
        label="S3-compatible",
        description="Use an S3-style bucket with explicit endpoint and credential fields.",
        selectable=False,
        coming_soon=True,
        experimental=True,
        integration_status="scaffolded",
        supports_remote_revision=True,
        supports_incremental_sync=True,
        fields=(
            ProviderFieldSpec("endpoint", "Endpoint URL", required=True),
            ProviderFieldSpec("bucket", "Bucket name", required=True),
            ProviderFieldSpec("region", "Region", required=True, default="auto"),
            ProviderFieldSpec("access_key_id", "Access key id", required=True),
            ProviderFieldSpec("secret_access_key", "Secret access key", required=True, secret=True),
        ),
    ),
    ProviderOption(
        key="system",
        label="System (recommended)",
        description="Worker-managed temporary storage for fast setup and testing.",
        recommended=True,
        temporary=True,
        selectable=True,
        reset_policy="daily",
        integration_status="connected",
        supports_remote_revision=True,
    ),
    ProviderOption(
        key="google-drive",
        label="Google Drive",
        description="Store blobs in a shared Drive-backed workspace location.",
        selectable=False,
        coming_soon=True,
        experimental=True,
        integration_status="scaffolded",
        supports_remote_revision=True,
        supports_change_tracking=True,
        supports_incremental_sync=True,
        fields=(
            ProviderFieldSpec("drive_id", "Shared drive id", required=True),
            ProviderFieldSpec("folder_id", "Folder id", required=True),
            ProviderFieldSpec("service_account_email", "Service account email", required=True),
            ProviderFieldSpec("credential_reference", "Credential reference", required=True, secret=True),
        ),
    ),
    ProviderOption(
        key="backblaze-b2",
        label="Backblaze B2",
        description="Use a B2 bucket with explicit application key credentials.",
        selectable=False,
        coming_soon=True,
        experimental=True,
        integration_status="scaffolded",
        supports_remote_revision=True,
        supports_incremental_sync=True,
        fields=(
            ProviderFieldSpec("bucket", "Bucket name", required=True),
            ProviderFieldSpec("key_id", "Application key id", required=True),
            ProviderFieldSpec("application_key", "Application key", required=True, secret=True),
        ),
    ),
)


def _option_from_payload(payload: Dict[str, object]) -> ProviderOption:
    return ProviderOption(
        key=str(payload.get("kind", "system")),
        label=str(payload.get("label", "System (recommended)")),
        description=str(payload.get("description", "")),
        recommended=bool(payload.get("recommended", False)),
        temporary=bool(payload.get("temporary", False)),
        selectable=bool(payload.get("selectable", True)),
        coming_soon=bool(payload.get("coming_soon", False)),
        experimental=bool(payload.get("experimental", False)),
        reset_policy=str(payload.get("reset_policy", "")),
        integration_status=str(payload.get("integration_status", "")),
        supports_direct_transfers=bool(payload.get("supports_direct_transfers", False)),
        supports_remote_revision=bool(payload.get("supports_remote_revision", False)),
        supports_change_tracking=bool(payload.get("supports_change_tracking", False)),
        supports_incremental_sync=bool(payload.get("supports_incremental_sync", False)),
        fields=tuple(
            ProviderFieldSpec.from_payload(field)
            for field in payload.get("credential_fields", [])
            if isinstance(field, dict)
        ),
    )


def _provider_options(client: Optional[CheriClient] = None) -> Tuple[ProviderOption, ...]:
    if client is None:
        return FALLBACK_PROVIDER_OPTIONS
    try:
        catalog = client.get_provider_catalog(include_experimental=True)
    except CheriClientError:
        return FALLBACK_PROVIDER_OPTIONS
    if not catalog:
        return FALLBACK_PROVIDER_OPTIONS
    return tuple(_option_from_payload(item) for item in catalog if isinstance(item, dict)) or FALLBACK_PROVIDER_OPTIONS


def iter_provider_options(client: Optional[CheriClient] = None) -> Iterable[ProviderOption]:
    return _provider_options(client)


def find_provider_option(kind: str, client: Optional[CheriClient] = None) -> ProviderOption:
    for option in _provider_options(client):
        if option.key == kind:
            return option
    raise KeyError(kind)


def _masked_settings(option: ProviderOption, settings: Dict[str, object]) -> Dict[str, str]:
    masked: Dict[str, str] = {}
    for field in option.fields:
        value = settings.get(field.key, "")
        if field.secret and value:
            masked[field.key] = "***"
        else:
            masked[field.key] = str(value or "")
    return masked


def _render_provider_table(console: Console, options: Tuple[ProviderOption, ...]) -> None:
    table = Table(box=box.ROUNDED, border_style="blue", title="Storage Providers")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Provider", style="white", width=24)
    table.add_column("Status", width=14)
    table.add_column("Notes", style="dim")
    for index, option in enumerate(options, start=1):
        note = option.description
        if option.recommended:
            note = f"{note} Recommended for quick start."
        if option.coming_soon:
            note = f"{note} Coming soon for active workspace use."
        table.add_row(str(index), option.label, option.status_label, note)
    console.print(table)


def _render_validation(console: Console, option: ProviderOption, provider: ProviderConfig) -> None:
    validation = provider.validation
    masked_settings = _masked_settings(option, provider.settings)
    details = [
        f"Provider   : {provider.label}",
        f"Validation : {validation.state}",
        f"Available  : {'yes' if validation.available else 'no'}",
    ]
    if provider.reset_policy:
        details.append(f"Reset      : {provider.reset_policy}")
    if masked_settings:
        details.append("")
        details.append("Config")
        for key, value in masked_settings.items():
            details.append(f"  {key}: {value or '-'}")
    if validation.warnings:
        details.append("")
        details.append("Warnings")
        for warning in validation.warnings:
            details.append(f"  - {warning}")
    if validation.errors:
        details.append("")
        details.append("Errors")
        for error in validation.errors:
            details.append(f"  - {error}")
    console.print(
        Panel.fit(
            "\n".join(details),
            title="Provider Validation",
            border_style="yellow" if validation.warnings or not validation.available else "green",
        )
    )


def prompt_for_provider(console: Console, client: CheriClient) -> ProviderConfig:
    options = _provider_options(client)
    _render_provider_table(console, options)
    selectable_indexes = [
        index
        for index, option in enumerate(options, start=1)
        if option.selectable or (option.experimental and os.environ.get("CHERI_EXPERIMENTAL_PROVIDERS") == "1")
    ]
    if not selectable_indexes:
        raise click.ClickException("No storage providers are currently selectable in this deployment.")

    selected_index = click.prompt(
        "Select storage provider",
        type=click.IntRange(1, len(options)),
        default=selectable_indexes[0],
    )
    option = options[selected_index - 1]
    if selected_index not in selectable_indexes:
        raise click.ClickException(f"{option.label} is coming soon and cannot be selected in the public setup flow yet.")
    warning_acknowledged = False
    if option.warning:
        console.print(Panel.fit(option.warning, title=option.label, border_style="yellow"))
        if not click.confirm("Continue with this storage provider?", default=False):
            raise click.Abort()
        warning_acknowledged = True

    settings: Dict[str, str] = {}
    for field in option.fields:
        prompt_kwargs = {"hide_input": field.secret}
        if field.default:
            prompt_kwargs["default"] = field.default
        settings[field.key] = click.prompt(field.label, **prompt_kwargs)

    selection = ProviderConfig(
        kind=option.key,
        label=option.label,
        temporary=option.temporary,
        recommended=option.recommended,
        selectable=option.selectable,
        coming_soon=option.coming_soon,
        experimental=option.experimental and os.environ.get("CHERI_EXPERIMENTAL_PROVIDERS") == "1",
        warning_acknowledged=warning_acknowledged,
        reset_policy=option.reset_policy,
        settings=settings,
        metadata=option.to_metadata(),
        validation=ProviderValidationState(),
    )

    try:
        validated = client.validate_provider_config(selection, allow_experimental=selection.experimental)
    except CheriClientError as exc:
        raise click.ClickException(str(exc)) from exc

    selection.temporary = validated.temporary
    selection.recommended = validated.recommended
    selection.selectable = validated.selectable
    selection.coming_soon = validated.coming_soon
    selection.experimental = validated.experimental
    selection.reset_policy = validated.reset_policy
    selection.metadata = validated.metadata
    selection.validation = validated.validation
    _render_validation(console, option, selection)

    if selection.validation.errors:
        raise click.ClickException(selection.validation.errors[0])
    if not selection.validation.available:
        console.print(
            Panel.fit(
                "This provider configuration is saved as scaffolded. Upload and download commands remain unavailable until the connector is enabled in the deployment.",
                title="Provider Not Active",
                border_style="yellow",
            )
        )
        if not click.confirm("Use this provider anyway?", default=False):
            raise click.Abort()

    return selection


def describe_provider(provider: ProviderConfig) -> str:
    suffixes = []
    if provider.recommended:
        suffixes.append("recommended")
    if provider.temporary:
        suffixes.append("temporary")
    if provider.coming_soon:
        suffixes.append("coming soon")
    if provider.validation.state and not provider.validation.available:
        suffixes.append(provider.validation.state.replace("-", " "))
    if not suffixes:
        return provider.label
    return f"{provider.label} ({', '.join(suffixes)})"
