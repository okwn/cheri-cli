"""Shared configuration for the Cheri CLI."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .deployment import DeploymentInfo, load_deployment_info


ENV_API_URL_KEYS = ("CHERI_API_URL", "CHERI_WORKER_URL")


class CheriConfigError(RuntimeError):
    """Raised when Cheri configuration is missing or invalid."""


@dataclass(frozen=True)
class ConfigPaths:
    config_dir: Path
    settings_file: Path
    state_file: Path
    secret_file: Path
    task_registry_file: Path
    task_runtime_file: Path
    task_log_file: Path


@dataclass(frozen=True)
class CliSettings:
    api_url: str = ""


@dataclass(frozen=True)
class ResolvedApiUrl:
    url: str
    source: str
    deployment: DeploymentInfo
    settings: CliSettings


def _default_config_dir() -> Path:
    override = os.environ.get("CHERI_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return root / "Cheri"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cheri"
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "cheri"


def get_legacy_config_dir() -> Path:
    return Path.home() / ".cheri"


def get_paths() -> ConfigPaths:
    config_root = _default_config_dir()
    return ConfigPaths(
        config_dir=config_root,
        settings_file=config_root / "settings.json",
        state_file=config_root / "state.json",
        secret_file=config_root / "credentials.json",
        task_registry_file=config_root / "tasks.json",
        task_runtime_file=config_root / "task-runtime.json",
        task_log_file=config_root / "task-logs.json",
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def normalize_api_url(value: str, *, source_label: str = "API URL") -> str:
    raw = str(value or "").strip()
    if not raw:
        raise CheriConfigError(f"{source_label} is required.")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CheriConfigError(
            "Invalid API URL\n"
            "Cheri could not use the configured backend API URL.\n\n"
            f"Current API URL:\n  {raw}\n\n"
            "Update it with:\n"
            "  cheri config set api-url https://cheri.parapanteri.com"
        )
    if parsed.query or parsed.fragment:
        raise CheriConfigError(
            "Invalid API URL\n"
            "Cheri backend URLs cannot include a query string or fragment.\n\n"
            f"Current API URL:\n  {raw}\n\n"
            "Update it with:\n"
            "  cheri config set api-url https://cheri.parapanteri.com"
        )
    normalized_path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, "", ""))


def load_cli_settings(paths: ConfigPaths | None = None) -> CliSettings:
    resolved_paths = paths or get_paths()
    if not resolved_paths.settings_file.exists():
        return CliSettings()
    try:
        payload = _read_json(resolved_paths.settings_file)
    except (OSError, ValueError) as exc:
        raise CheriConfigError(
            "Local config is unreadable.\n"
            f"Cheri could not read {resolved_paths.settings_file}."
        ) from exc
    return CliSettings(api_url=str(payload.get("api_url", "")).strip())


def save_cli_settings(settings: CliSettings, paths: ConfigPaths | None = None) -> None:
    resolved_paths = paths or get_paths()
    _write_json(
        resolved_paths.settings_file,
        {
            "format_version": 1,
            "updated_at": _now(),
            "api_url": settings.api_url,
        },
    )


def set_saved_api_url(api_url: str, paths: ConfigPaths | None = None) -> str:
    normalized = normalize_api_url(api_url)
    save_cli_settings(CliSettings(api_url=normalized), paths=paths)
    return normalized


def reset_cli_settings(paths: ConfigPaths | None = None) -> None:
    resolved_paths = paths or get_paths()
    if resolved_paths.settings_file.exists():
        resolved_paths.settings_file.unlink()


def resolve_api_url(paths: ConfigPaths | None = None) -> ResolvedApiUrl:
    deployment = load_deployment_info()
    resolved_paths = paths or get_paths()
    settings = load_cli_settings(resolved_paths)

    for env_key in ENV_API_URL_KEYS:
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            return ResolvedApiUrl(
                url=normalize_api_url(env_value, source_label=env_key),
                source=f"environment:{env_key}",
                deployment=deployment,
                settings=settings,
            )

    if settings.api_url:
        return ResolvedApiUrl(
            url=normalize_api_url(settings.api_url, source_label="saved API URL"),
            source="local_config",
            deployment=deployment,
            settings=settings,
        )

    if deployment.api_url:
        return ResolvedApiUrl(
            url=normalize_api_url(deployment.api_url, source_label="deployment API URL"),
            source="deployment_metadata",
            deployment=deployment,
            settings=settings,
        )

    raise CheriConfigError(
        "Backend configuration missing\n"
        "Cheri could not determine the backend API URL.\n\n"
        "Set it with:\n"
        "  cheri config set api-url https://cheri.parapanteri.com\n\n"
        "Or export:\n"
        "  CHERI_API_URL=https://cheri.parapanteri.com"
    )


def get_base_url() -> str:
    return resolve_api_url().url
