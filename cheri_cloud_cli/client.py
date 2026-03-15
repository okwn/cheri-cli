"""HTTP client for the Cheri workspace sync API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from .config import get_base_url
from .contracts import (
    ActivityFeed,
    AuthState,
    DownloadGrant,
    FileUploadRequest,
    InviteRecord,
    ProviderConfig,
    RemoteFile,
    TaskRegistryRecord,
    TeamSnapshot,
    UploadGrant,
    WorkspaceSummary,
)


class CheriClientError(RuntimeError):
    """Raised when the Cheri API returns an error response."""


class CheriClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or get_base_url()).rstrip("/")

    def healthcheck(self) -> Dict[str, Any]:
        return self._request("get", "/healthz")

    def register(self, username: str, workspace_name: str, provider: Dict[str, Any] | ProviderConfig) -> AuthState:
        payload = self._request(
            "post",
            "/v1/auth/register",
            json={
                "username": username,
                "workspace_name": workspace_name,
                "provider": self._provider_payload(provider),
            },
        )
        return AuthState.from_payload(payload)

    def login(self, username: str, bootstrap_secret: str) -> AuthState:
        payload = self._request(
            "post",
            "/v1/auth/login",
            json={"username": username, "bootstrap_secret": bootstrap_secret},
        )
        return AuthState.from_payload(payload, bootstrap_secret=bootstrap_secret)

    def logout(self, state: AuthState) -> None:
        self._request("post", "/v1/auth/logout", token=state.session_token, json={})

    def get_session(self, state: AuthState) -> AuthState:
        payload = self._request("get", "/v1/session", token=state.session_token)
        return AuthState.from_payload(
            payload,
            session_token=state.session_token,
            bootstrap_secret=state.bootstrap_secret,
        )

    def list_workspaces(self, state: AuthState) -> List[WorkspaceSummary]:
        payload = self._request("get", "/v1/workspaces", token=state.session_token)
        return [WorkspaceSummary.from_payload(item) for item in payload.get("workspaces", [])]

    def get_provider_catalog(self, *, include_experimental: bool = False) -> List[Dict[str, Any]]:
        query = "?include_experimental=1" if include_experimental else ""
        payload = self._request("get", f"/v1/providers{query}")
        return list(payload.get("providers", []))

    def validate_provider_config(
        self,
        provider: Dict[str, Any] | ProviderConfig,
        *,
        allow_experimental: bool = False,
    ) -> ProviderConfig:
        payload = self._request(
            "post",
            "/v1/providers/validate",
            json={
                "provider": self._provider_payload(provider),
                "allow_experimental": allow_experimental,
            },
        )
        return ProviderConfig.from_payload(payload.get("provider", {}))

    def select_workspace(
        self,
        state: AuthState,
        identifier: str,
        *,
        create_if_missing: bool = False,
        provider: Optional[Dict[str, Any] | ProviderConfig] = None,
    ) -> AuthState:
        payload = self._request(
            "post",
            "/v1/workspaces/select",
            token=state.session_token,
            json={
                "identifier": identifier,
                "create_if_missing": create_if_missing,
                "provider": self._provider_payload(provider) if provider else None,
            },
        )
        return AuthState.from_payload(
            payload,
            session_token=state.session_token,
            bootstrap_secret=state.bootstrap_secret,
            active_workspace_id=payload.get("active_workspace_id"),
        )

    def list_files(self, state: AuthState, workspace_id: Optional[str] = None) -> List[RemoteFile]:
        payload = self._request("get", "/v1/files", state=state, workspace_id=workspace_id)
        return [RemoteFile.from_payload(item) for item in payload.get("files", [])]

    def request_upload_grant(self, state: AuthState, request: FileUploadRequest, workspace_id: Optional[str] = None) -> UploadGrant:
        payload = self._request(
            "post",
            "/v1/files/upload-grant",
            state=state,
            workspace_id=workspace_id,
            json=request.to_dict(),
        )
        return UploadGrant.from_payload(payload)

    def confirm_file_upload(self, state: AuthState, file_id: str, workspace_id: Optional[str] = None) -> RemoteFile:
        payload = self._request(
            "post",
            f"/v1/files/{file_id}/complete",
            state=state,
            workspace_id=workspace_id,
            json={},
        )
        return RemoteFile.from_payload(payload.get("file", {}))

    def request_download_grant(self, state: AuthState, file_id: str, workspace_id: Optional[str] = None) -> DownloadGrant:
        payload = self._request(
            "get",
            f"/v1/files/{file_id}/download-grant",
            state=state,
            workspace_id=workspace_id,
        )
        return DownloadGrant.from_payload(payload)

    def list_team(self, state: AuthState, workspace_id: Optional[str] = None) -> TeamSnapshot:
        payload = self._request("get", "/v1/teams", state=state, workspace_id=workspace_id)
        return TeamSnapshot.from_payload(payload)

    def create_team_invite(self, state: AuthState, label: str = "", workspace_id: Optional[str] = None) -> InviteRecord:
        payload = self._request(
            "post",
            "/v1/teams/invites",
            state=state,
            workspace_id=workspace_id,
            json={"label": label},
        )
        return InviteRecord.from_payload(payload.get("invite", {}))

    def reset_team_invites(
        self,
        state: AuthState,
        workspace_id: Optional[str] = None,
        *,
        create_replacement: bool = False,
        label: str = "",
    ) -> Dict[str, Any]:
        return self._request(
            "post",
            "/v1/teams/invites/reset",
            state=state,
            workspace_id=workspace_id,
            json={
                "create_replacement": create_replacement,
                "label": label,
            },
        )

    def accept_team_invite(self, state: AuthState, invite_code: str) -> AuthState:
        payload = self._request(
            "post",
            "/v1/teams/invites/accept",
            token=state.session_token,
            json={"invite_code": invite_code},
        )
        return AuthState.from_payload(
            payload,
            session_token=state.session_token,
            bootstrap_secret=state.bootstrap_secret,
            active_workspace_id=payload.get("active_workspace_id", state.active_workspace_id),
        )

    def list_activity(self, state: AuthState, workspace_id: Optional[str] = None) -> ActivityFeed:
        payload = self._request("get", "/v1/activity", state=state, workspace_id=workspace_id)
        return ActivityFeed.from_payload(payload)

    def list_task_registry(self, state: AuthState, workspace_id: Optional[str] = None) -> List[TaskRegistryRecord]:
        payload = self._request("get", "/v1/tasks", state=state, workspace_id=workspace_id)
        return [TaskRegistryRecord.from_payload(item) for item in payload.get("tasks", [])]

    def upsert_task_registry_record(
        self,
        state: AuthState,
        *,
        workspace_id: str,
        task_payload: Dict[str, Any],
    ) -> TaskRegistryRecord:
        payload = self._request(
            "post",
            "/v1/tasks",
            state=state,
            workspace_id=workspace_id,
            json=task_payload,
        )
        return TaskRegistryRecord.from_payload(payload.get("task", {}))

    def delete_task_registry_record(self, state: AuthState, *, workspace_id: str, task_id: str) -> None:
        self._request("delete", f"/v1/tasks/{task_id}", state=state, workspace_id=workspace_id)

    def record_task_event(
        self,
        state: AuthState,
        *,
        workspace_id: str,
        action: str,
        summary: str,
        metadata: Dict[str, Any],
    ) -> None:
        self._request(
            "post",
            "/v1/task-events",
            state=state,
            workspace_id=workspace_id,
            json={
                "action": action,
                "summary": summary,
                **metadata,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        state: Optional[AuthState] = None,
        token: Optional[str] = None,
        workspace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        headers = kwargs.pop("headers", {})
        if state:
            headers.update(state.to_headers(workspace_id))
        elif token:
            headers["Authorization"] = f"Bearer {token}"
            if workspace_id:
                headers["X-Workspace-ID"] = workspace_id

        try:
            response = requests.request(
                method=method.upper(),
                url=f"{self.base_url}{path}",
                headers=headers,
                timeout=30,
                **kwargs,
            )
        except requests.exceptions.InvalidURL as exc:
            raise CheriClientError(
                "Invalid API URL\n"
                "Cheri could not use the configured backend API URL.\n\n"
                f"Current API URL:\n  {self.base_url}\n\n"
                "Update it with:\n"
                "  cheri config set api-url https://cheri.parapanteri.com"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise CheriClientError(
                "Connection failed\n"
                "Cheri could not reach the backend API.\n\n"
                f"Current API URL:\n  {self.base_url}\n\n"
                "Check your backend deployment or update the API URL with:\n"
                "  cheri config set api-url https://cheri.parapanteri.com"
            ) from exc
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text or response.reason}
            raise CheriClientError(payload.get("error", f"{response.status_code} {response.reason}"))
        if not response.content:
            return {}
        return response.json()

    @staticmethod
    def _provider_payload(provider: Dict[str, Any] | ProviderConfig) -> Dict[str, Any]:
        if isinstance(provider, ProviderConfig):
            return provider.to_selection_payload()
        return dict(provider)
