"""Typed contracts for the Cheri CLI-first API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _compact_dict(values: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


@dataclass
class ProviderFieldSpec:
    key: str
    label: str
    required: bool = False
    secret: bool = False
    default: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProviderFieldSpec":
        return cls(
            key=payload.get("key", ""),
            label=payload.get("label", ""),
            required=payload.get("required", False),
            secret=payload.get("secret", False),
            default=payload.get("default", ""),
        )


@dataclass
class ProviderMetadata:
    description: str = ""
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
    credential_fields: List[ProviderFieldSpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["credential_fields"] = [field.to_dict() for field in self.credential_fields]
        return payload

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProviderMetadata":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            description=payload.get("description", ""),
            recommended=payload.get("recommended", False),
            temporary=payload.get("temporary", False),
            selectable=payload.get("selectable", True),
            coming_soon=payload.get("coming_soon", False),
            experimental=payload.get("experimental", False),
            reset_policy=payload.get("reset_policy", ""),
            integration_status=payload.get("integration_status", ""),
            supports_direct_transfers=payload.get("supports_direct_transfers", False),
            supports_remote_revision=payload.get("supports_remote_revision", False),
            supports_change_tracking=payload.get("supports_change_tracking", False),
            supports_incremental_sync=payload.get("supports_incremental_sync", False),
            credential_fields=[
                ProviderFieldSpec.from_payload(item)
                for item in payload.get("credential_fields", [])
                if isinstance(item, dict)
            ],
        )


@dataclass
class ProviderValidationState:
    state: str = "pending"
    available: bool = False
    checked_at: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProviderValidationState":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            state=payload.get("state", "pending"),
            available=payload.get("available", False),
            checked_at=payload.get("checked_at", ""),
            warnings=list(payload.get("warnings", [])),
            errors=list(payload.get("errors", [])),
        )


@dataclass
class ProviderConfig:
    kind: str
    label: str
    temporary: bool = False
    recommended: bool = False
    selectable: bool = True
    coming_soon: bool = False
    experimental: bool = False
    warning_acknowledged: bool = False
    reset_policy: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: ProviderMetadata = field(default_factory=ProviderMetadata)
    validation: ProviderValidationState = field(default_factory=ProviderValidationState)

    def to_dict(self) -> Dict[str, Any]:
        payload = _compact_dict(asdict(self))
        payload["metadata"] = self.metadata.to_dict()
        payload["validation"] = self.validation.to_dict()
        return payload

    def to_selection_payload(self) -> Dict[str, Any]:
        return _compact_dict(
            {
                "kind": self.kind,
                "experimental_acknowledged": self.experimental,
                "warning_acknowledged": self.warning_acknowledged,
                "settings": dict(self.settings),
            }
        )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProviderConfig":
        if not isinstance(payload, dict):
            payload = {}
        metadata = ProviderMetadata.from_payload(payload.get("metadata", {}))
        validation = ProviderValidationState.from_payload(payload.get("validation", {}))
        return cls(
            kind=payload.get("kind", "system"),
            label=payload.get("label", "System (recommended)"),
            temporary=payload.get("temporary", metadata.temporary),
            recommended=payload.get("recommended", metadata.recommended),
            selectable=payload.get("selectable", metadata.selectable),
            coming_soon=payload.get("coming_soon", metadata.coming_soon),
            experimental=payload.get("experimental", metadata.experimental),
            warning_acknowledged=payload.get("warning_acknowledged", False),
            reset_policy=payload.get("reset_policy", metadata.reset_policy),
            settings=dict(payload.get("settings") or payload.get("config") or {}),
            metadata=metadata,
            validation=validation,
        )


@dataclass
class UserProfile:
    id: str
    username: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "UserProfile":
        return cls(
            id=payload.get("id", ""),
            username=payload.get("username", ""),
            created_at=payload.get("created_at", ""),
        )


@dataclass
class WorkspaceSummary:
    id: str
    name: str
    slug: str
    role: str
    created_at: str
    joined_at: str = ""
    provider: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(
            kind="system",
            label="System (recommended)",
            temporary=True,
            recommended=True,
            reset_policy="daily",
        )
    )
    member_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["provider"] = self.provider.to_dict()
        return payload

    def matches(self, identifier: str) -> bool:
        normalized = str(identifier or "").strip().lower()
        return bool(normalized) and (
            self.id.lower() == normalized
            or self.name.lower() == normalized
            or self.slug == normalized
        )

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "WorkspaceSummary":
        return cls(
            id=payload.get("id", ""),
            name=payload.get("name", ""),
            slug=payload.get("slug", ""),
            role=payload.get("role", "member"),
            created_at=payload.get("created_at", ""),
            joined_at=payload.get("joined_at", ""),
            provider=ProviderConfig.from_payload(payload.get("provider") or {}),
            member_count=payload.get("member_count", 0),
        )


@dataclass
class SessionContext:
    token: str = ""
    issued_at: str = ""
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], *, fallback_token: str = "", fallback_issued_at: str = "") -> "SessionContext":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            token=payload.get("token") or payload.get("session_token") or fallback_token,
            issued_at=payload.get("issued_at") or fallback_issued_at,
            session_id=payload.get("id", payload.get("session_id", "")),
        )


@dataclass
class BootstrapContext:
    secret: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any], *, fallback_secret: str = "") -> "BootstrapContext":
        if not isinstance(payload, dict):
            payload = {}
        return cls(secret=payload.get("secret") or payload.get("bootstrap_secret") or fallback_secret)


@dataclass
class WorkspaceAccessContext:
    active_workspace_id: str = ""
    workspaces: List[WorkspaceSummary] = field(default_factory=list)

    @property
    def active_workspace(self) -> Optional[WorkspaceSummary]:
        for workspace in self.workspaces:
            if workspace.id == self.active_workspace_id:
                return workspace
        return self.workspaces[0] if self.workspaces else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_workspace_id": self.active_workspace_id,
            "workspaces": [workspace.to_dict() for workspace in self.workspaces],
        }

    @classmethod
    def from_payload(
        cls,
        payload: Dict[str, Any],
        *,
        fallback_active_workspace_id: str = "",
        fallback_workspaces: Optional[List[WorkspaceSummary]] = None,
    ) -> "WorkspaceAccessContext":
        if not isinstance(payload, dict):
            payload = {}
        workspaces = [WorkspaceSummary.from_payload(item) for item in payload.get("workspaces", [])]
        if not workspaces and fallback_workspaces is not None:
            workspaces = fallback_workspaces
        active_workspace_id = (
            payload.get("active_workspace_id")
            or fallback_active_workspace_id
            or (workspaces[0].id if workspaces else "")
        )
        return cls(active_workspace_id=active_workspace_id, workspaces=workspaces)


@dataclass
class AuthState:
    identity: UserProfile
    session: SessionContext = field(default_factory=SessionContext)
    workspace_access: WorkspaceAccessContext = field(default_factory=WorkspaceAccessContext)
    bootstrap: BootstrapContext = field(default_factory=BootstrapContext)

    @property
    def user(self) -> UserProfile:
        return self.identity

    @property
    def session_token(self) -> str:
        return self.session.token

    @session_token.setter
    def session_token(self, value: str) -> None:
        self.session.token = value

    @property
    def workspaces(self) -> List[WorkspaceSummary]:
        return self.workspace_access.workspaces

    @property
    def active_workspace_id(self) -> str:
        return self.workspace_access.active_workspace_id

    @active_workspace_id.setter
    def active_workspace_id(self, value: str) -> None:
        self.workspace_access.active_workspace_id = value

    @property
    def active_workspace(self) -> Optional[WorkspaceSummary]:
        return self.workspace_access.active_workspace

    @property
    def bootstrap_secret(self) -> str:
        return self.bootstrap.secret

    @bootstrap_secret.setter
    def bootstrap_secret(self, value: str) -> None:
        self.bootstrap.secret = value

    @property
    def issued_at(self) -> str:
        return self.session.issued_at

    @issued_at.setter
    def issued_at(self, value: str) -> None:
        self.session.issued_at = value

    def to_headers(self, workspace_id: Optional[str] = None) -> Dict[str, str]:
        headers = {"Authorization": f"Bearer {self.session.token}"}
        resolved_workspace_id = workspace_id or self.workspace_access.active_workspace_id
        if resolved_workspace_id:
            headers["X-Workspace-ID"] = resolved_workspace_id
        return headers

    def to_local_payload(self) -> Dict[str, Any]:
        return {
            "format_version": 1,
            "identity": self.identity.to_dict(),
            "session": self.session.to_dict(),
            "workspace_access": self.workspace_access.to_dict(),
            "bootstrap": self.bootstrap.to_dict(),
        }

    @classmethod
    def from_payload(
        cls,
        payload: Dict[str, Any],
        *,
        session_token: Optional[str] = None,
        bootstrap_secret: Optional[str] = None,
        active_workspace_id: Optional[str] = None,
    ) -> "AuthState":
        identity_payload = payload.get("identity") or payload.get("user") or {}
        workspace_items = [WorkspaceSummary.from_payload(item) for item in payload.get("workspaces", [])]
        workspace_access = WorkspaceAccessContext.from_payload(
            payload.get("workspace_access", {}),
            fallback_active_workspace_id=(
                active_workspace_id
                or payload.get("active_workspace_id")
                or payload.get("default_workspace_id")
                or ""
            ),
            fallback_workspaces=workspace_items,
        )
        session_context = SessionContext.from_payload(
            payload.get("session", {}),
            fallback_token=session_token or payload.get("session_token", ""),
            fallback_issued_at=payload.get("issued_at", ""),
        )
        bootstrap_context = BootstrapContext.from_payload(
            payload.get("bootstrap", {}),
            fallback_secret=bootstrap_secret if bootstrap_secret is not None else payload.get("bootstrap_secret", ""),
        )
        return cls(
            identity=UserProfile.from_payload(identity_payload),
            session=session_context,
            workspace_access=workspace_access,
            bootstrap=bootstrap_context,
        )

    @classmethod
    def from_local_payload(cls, payload: Dict[str, Any]) -> "AuthState":
        return cls.from_payload(
            payload,
            session_token=payload.get("session_token", ""),
            bootstrap_secret=payload.get("bootstrap_secret", ""),
            active_workspace_id=payload.get("active_workspace_id", ""),
        )


@dataclass
class ProviderObjectRef:
    kind: str = ""
    object_key: str = ""
    object_id: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ProviderObjectRef":
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            kind=payload.get("kind", ""),
            object_key=payload.get("object_key", payload.get("provider_object_key", "")),
            object_id=payload.get("object_id", payload.get("provider_object_id", "")),
        )


@dataclass
class RemoteFile:
    id: str
    workspace_id: str
    logical_name: str
    provider_kind: str
    provider_object_key: str = ""
    provider_object_id: str = ""
    size: int = 0
    content_type: str = "application/octet-stream"
    created_at: str = ""
    updated_at: str = ""
    uploaded_at: str = ""
    uploaded_by: str = ""
    last_modified_by: str = ""
    version: int = 1
    revision_marker: str = ""
    remote_revision: str = ""
    checksum: str = ""
    local_modified_at: str = ""
    sync_status: str = "synced"
    conflict_state: str = "clear"
    status: str = "available"

    @property
    def name(self) -> str:
        return self.logical_name

    @property
    def mime_type(self) -> str:
        return self.content_type

    @property
    def modified_at(self) -> str:
        return self.updated_at or self.uploaded_at

    @property
    def uploader(self) -> str:
        return self.uploaded_by

    @property
    def editor(self) -> str:
        return self.last_modified_by or self.uploaded_by

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "RemoteFile":
        logical_name = payload.get("logical_name", payload.get("name", ""))
        content_type = payload.get("content_type", payload.get("mime_type", "application/octet-stream"))
        updated_at = payload.get("updated_at", payload.get("modified_at", payload.get("uploaded_at", "")))
        uploaded_by = payload.get("uploaded_by", payload.get("uploader", ""))
        last_modified_by = payload.get("last_modified_by", payload.get("editor", uploaded_by))
        version = payload.get("version", 1)
        return cls(
            id=payload.get("id", ""),
            workspace_id=payload.get("workspace_id", ""),
            logical_name=logical_name,
            provider_kind=payload.get("provider_kind", "system"),
            provider_object_key=payload.get("provider_object_key", payload.get("storage_key", "")),
            provider_object_id=payload.get("provider_object_id", payload.get("provider_object_key", payload.get("storage_key", ""))),
            size=payload.get("size", 0),
            content_type=content_type,
            created_at=payload.get("created_at", payload.get("uploaded_at", updated_at)),
            updated_at=updated_at,
            uploaded_at=payload.get("uploaded_at", updated_at),
            uploaded_by=uploaded_by,
            last_modified_by=last_modified_by,
            version=int(version or 1),
            revision_marker=payload.get("revision_marker", f"v{int(version or 1)}"),
            remote_revision=payload.get("remote_revision", payload.get("revision_marker", "")),
            checksum=payload.get("checksum", ""),
            local_modified_at=payload.get("local_modified_at", ""),
            sync_status=payload.get("sync_status", "synced"),
            conflict_state=payload.get("conflict_state", "clear"),
            status=payload.get("status", "available"),
        )


@dataclass
class FileUploadRequest:
    filename: str
    size: int
    mime_type: str
    checksum: str
    local_modified_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UploadGrant:
    file_id: str
    upload_url: str
    expires_at: str
    provider: ProviderObjectRef = field(default_factory=ProviderObjectRef)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "UploadGrant":
        return cls(
            file_id=payload.get("file_id", ""),
            upload_url=payload.get("upload_url", ""),
            expires_at=payload.get("expires_at", ""),
            provider=ProviderObjectRef.from_payload(payload.get("provider", {})),
        )


@dataclass
class DownloadGrant:
    file_id: str
    filename: str
    download_url: str
    expires_at: str
    provider: ProviderObjectRef = field(default_factory=ProviderObjectRef)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "DownloadGrant":
        return cls(
            file_id=payload.get("file_id", ""),
            filename=payload.get("filename", ""),
            download_url=payload.get("download_url", ""),
            expires_at=payload.get("expires_at", ""),
            provider=ProviderObjectRef.from_payload(payload.get("provider", {})),
        )


@dataclass
class TeamMember:
    user_id: str
    username: str
    role: str
    joined_at: str

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TeamMember":
        return cls(
            user_id=payload.get("user_id", ""),
            username=payload.get("username", ""),
            role=payload.get("role", "member"),
            joined_at=payload.get("joined_at", ""),
        )


@dataclass
class InviteRecord:
    code: str
    workspace_id: str
    workspace_name: str
    role: str
    status: str
    created_by: str
    created_at: str
    expires_at: str
    label: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "InviteRecord":
        return cls(
            code=payload.get("code", payload.get("invite_code", "")),
            workspace_id=payload.get("workspace_id", ""),
            workspace_name=payload.get("workspace_name", ""),
            role=payload.get("role", "member"),
            status=payload.get("status", "active"),
            created_by=payload.get("created_by", ""),
            created_at=payload.get("created_at", ""),
            expires_at=payload.get("expires_at", ""),
            label=payload.get("label", ""),
        )


@dataclass
class InviteState:
    visible: bool = False
    invite_generation: int = 1
    active_count: int = 0
    accepted_count: int = 0
    revoked_count: int = 0
    expired_count: int = 0

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "InviteState":
        if not isinstance(payload, dict):
            return cls()
        return cls(
            visible=payload.get("visible", False),
            invite_generation=int(payload.get("invite_generation", 1) or 1),
            active_count=int(payload.get("active_count", 0) or 0),
            accepted_count=int(payload.get("accepted_count", 0) or 0),
            revoked_count=int(payload.get("revoked_count", 0) or 0),
            expired_count=int(payload.get("expired_count", 0) or 0),
        )


@dataclass
class TeamSnapshot:
    workspace: WorkspaceSummary
    members: List[TeamMember]
    invites: List[InviteRecord]
    invite_state: InviteState = field(default_factory=InviteState)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TeamSnapshot":
        return cls(
            workspace=WorkspaceSummary.from_payload(payload.get("workspace", {})),
            members=[TeamMember.from_payload(item) for item in payload.get("members", [])],
            invites=[InviteRecord.from_payload(item) for item in payload.get("invites", [])],
            invite_state=InviteState.from_payload(payload.get("invite_state", {})),
        )


@dataclass
class ActivityEntry:
    at: str
    action: str
    actor: str
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ActivityEntry":
        return cls(
            at=payload.get("at", ""),
            action=payload.get("action", ""),
            actor=payload.get("actor", ""),
            summary=payload.get("summary", ""),
            metadata=payload.get("metadata", {}),
        )


@dataclass
class ActivityFeed:
    recent_uploads: List[RemoteFile]
    recent_modified_files: List[RemoteFile]
    recent_actions: List[ActivityEntry]
    recent_collaboration: List[ActivityEntry]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ActivityFeed":
        return cls(
            recent_uploads=[RemoteFile.from_payload(item) for item in payload.get("recent_uploads", [])],
            recent_modified_files=[RemoteFile.from_payload(item) for item in payload.get("recent_modified_files", [])],
            recent_actions=[ActivityEntry.from_payload(item) for item in payload.get("recent_actions", [])],
            recent_collaboration=[ActivityEntry.from_payload(item) for item in payload.get("recent_collaboration", [])],
        )


@dataclass
class TaskRegistryRecord:
    id: str
    workspace_id: str
    workspace_name: str
    target_type: str
    target_label: str
    sync_mode: str
    interval_value: int = 0
    interval_unit: str = ""
    enabled: bool = True
    debounce_seconds: int = 0
    recursive: bool = True
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    status: str = "idle"
    last_run_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    direction: str = "upload-only"
    conflict_strategy: str = "manual-placeholder"
    watch_poll_seconds: float = 2.0
    source: str = "cheri_cli"
    last_synced_by: str = ""
    last_synced_at: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TaskRegistryRecord":
        return cls(
            id=payload.get("id", ""),
            workspace_id=payload.get("workspace_id", ""),
            workspace_name=payload.get("workspace_name", ""),
            target_type=payload.get("target_type", "file"),
            target_label=payload.get("target_label", ""),
            sync_mode=payload.get("sync_mode", "on-change"),
            interval_value=int(payload.get("interval_value", 0) or 0),
            interval_unit=payload.get("interval_unit", ""),
            enabled=payload.get("enabled", True),
            debounce_seconds=int(payload.get("debounce_seconds", 0) or 0),
            recursive=payload.get("recursive", True),
            include_patterns=list(payload.get("include_patterns", [])),
            exclude_patterns=list(payload.get("exclude_patterns", [])),
            status=payload.get("status", "idle"),
            last_run_at=payload.get("last_run_at", ""),
            last_success_at=payload.get("last_success_at", ""),
            last_error=payload.get("last_error", ""),
            created_by=payload.get("created_by", ""),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            direction=payload.get("direction", "upload-only"),
            conflict_strategy=payload.get("conflict_strategy", "manual-placeholder"),
            watch_poll_seconds=float(payload.get("watch_poll_seconds", 2.0) or 2.0),
            source=payload.get("source", "cheri_cli"),
            last_synced_by=payload.get("last_synced_by", ""),
            last_synced_at=payload.get("last_synced_at", ""),
        )
