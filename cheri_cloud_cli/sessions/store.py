"""Local credential storage backends."""

from __future__ import annotations

import json
import os
import stat
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..config import get_legacy_config_dir, get_paths
from ..contracts import AuthState


class CredentialStore(ABC):
    @abstractmethod
    def load(self) -> Optional[AuthState]:
        raise NotImplementedError

    @abstractmethod
    def save(self, state: AuthState, *, persist_bootstrap_secret: bool | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _best_effort_restrict_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(path, 0o700)
    except OSError:
        return


def _best_effort_restrict_file(path: Path) -> None:
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
        else:
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        return


def _write_json(path: Path, payload: dict, *, private: bool) -> None:
    _best_effort_restrict_directory(path.parent)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if private:
        _best_effort_restrict_file(tmp_path)
    tmp_path.replace(path)
    if private:
        _best_effort_restrict_file(path)


class JsonCredentialStore(CredentialStore):
    """File-backed storage with public state split from secret-bearing credentials."""

    def __init__(self) -> None:
        self.paths = get_paths()

    @property
    def location(self) -> Path:
        return self.paths.state_file

    @property
    def secret_location(self) -> Path:
        return self.paths.secret_file

    @property
    def legacy_location(self) -> Path:
        return get_legacy_config_dir() / "state.json"

    def has_saved_state(self) -> bool:
        return self.location.exists() or self.secret_location.exists() or self.legacy_location.exists()

    def describe_locations(self) -> str:
        return f"{self.location} and {self.secret_location}"

    def _load_split_payload(self) -> Optional[dict]:
        if self.location.exists() or self.secret_location.exists():
            public_payload = _read_json(self.location) if self.location.exists() else {"format_version": 2}
            secret_payload = _read_json(self.secret_location) if self.secret_location.exists() else {"format_version": 2}
            return {
                "format_version": 2,
                **public_payload,
                **secret_payload,
            }
        if self.legacy_location.exists():
            return _read_json(self.legacy_location)
        return None

    def _public_payload(self, state: AuthState) -> dict:
        return {
            "format_version": 2,
            "identity": state.identity.to_dict(),
            "workspace_access": state.workspace_access.to_dict(),
        }

    def _secret_payload(self, state: AuthState, *, persist_bootstrap_secret: bool) -> dict:
        return {
            "format_version": 2,
            "session": state.session.to_dict(),
            "bootstrap": {"secret": state.bootstrap.secret if persist_bootstrap_secret else ""},
        }

    def load(self) -> Optional[AuthState]:
        payload = self._load_split_payload()
        if not payload:
            return None
        return AuthState.from_local_payload(payload)

    def save(self, state: AuthState, *, persist_bootstrap_secret: bool | None = None) -> None:
        existing = self.load()
        should_persist_bootstrap = (
            bool(existing.bootstrap_secret) if persist_bootstrap_secret is None and existing else persist_bootstrap_secret
        )
        public_payload = self._public_payload(state)
        secret_payload = self._secret_payload(state, persist_bootstrap_secret=bool(should_persist_bootstrap))
        _write_json(self.location, public_payload, private=False)
        _write_json(self.secret_location, secret_payload, private=True)
        if self.legacy_location.exists() and self.legacy_location != self.location:
            try:
                self.legacy_location.unlink()
            except OSError:
                pass

    def clear(self) -> None:
        for path in (self.location, self.secret_location, self.legacy_location):
            if path.exists():
                path.unlink()
