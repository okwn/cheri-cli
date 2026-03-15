"""Local task models for Cheri automation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class TaskDefinition:
    id: str
    workspace_id: str
    workspace_name: str
    target_type: str
    target_path: str
    sync_mode: str
    interval_value: int = 0
    interval_unit: str = ""
    enabled: bool = True
    debounce_seconds: int = 3
    recursive: bool = True
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    last_run_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    status: str = "idle"
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    direction: str = "upload-only"
    conflict_strategy: str = "manual-placeholder"
    watch_poll_seconds: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def mode_label(self) -> str:
        if self.sync_mode == "interval" and self.interval_value and self.interval_unit:
            suffix = "s" if self.interval_value != 1 and not self.interval_unit.endswith("s") else ""
            return f"every {self.interval_value} {self.interval_unit}{suffix}"
        if self.sync_mode == "hybrid" and self.interval_value and self.interval_unit:
            suffix = "s" if self.interval_value != 1 and not self.interval_unit.endswith("s") else ""
            return f"on-change + every {self.interval_value} {self.interval_unit}{suffix}"
        if self.sync_mode == "instant":
            return "instant"
        if self.sync_mode == "on-change":
            return f"on-change ({self.debounce_seconds}s debounce)"
        return self.sync_mode

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TaskDefinition":
        return cls(
            id=payload.get("id", ""),
            workspace_id=payload.get("workspace_id", ""),
            workspace_name=payload.get("workspace_name", ""),
            target_type=payload.get("target_type", "file"),
            target_path=payload.get("target_path", ""),
            sync_mode=payload.get("sync_mode", "on-change"),
            interval_value=int(payload.get("interval_value", 0) or 0),
            interval_unit=payload.get("interval_unit", ""),
            enabled=payload.get("enabled", True),
            debounce_seconds=int(payload.get("debounce_seconds", 3) or 3),
            recursive=payload.get("recursive", True),
            include_patterns=list(payload.get("include_patterns", [])),
            exclude_patterns=list(payload.get("exclude_patterns", [])),
            last_run_at=payload.get("last_run_at", ""),
            last_success_at=payload.get("last_success_at", ""),
            last_error=payload.get("last_error", ""),
            status=payload.get("status", "idle"),
            created_by=payload.get("created_by", ""),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            direction=payload.get("direction", "upload-only"),
            conflict_strategy=payload.get("conflict_strategy", "manual-placeholder"),
            watch_poll_seconds=float(payload.get("watch_poll_seconds", 2.0) or 2.0),
        )


@dataclass
class TaskRuntimeState:
    task_id: str
    snapshot: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_detected_change_at: str = ""
    next_interval_run_at: str = ""
    active_run_id: str = ""
    active_run_started_at: str = ""
    watcher_pid: int = 0
    watcher_started_at: str = ""
    watcher_heartbeat_at: str = ""
    watcher_log_path: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TaskRuntimeState":
        return cls(
            task_id=payload.get("task_id", ""),
            snapshot=dict(payload.get("snapshot", {})),
            last_detected_change_at=payload.get("last_detected_change_at", ""),
            next_interval_run_at=payload.get("next_interval_run_at", ""),
            active_run_id=payload.get("active_run_id", ""),
            active_run_started_at=payload.get("active_run_started_at", ""),
            watcher_pid=int(payload.get("watcher_pid", 0) or 0),
            watcher_started_at=payload.get("watcher_started_at", ""),
            watcher_heartbeat_at=payload.get("watcher_heartbeat_at", ""),
            watcher_log_path=payload.get("watcher_log_path", ""),
            updated_at=payload.get("updated_at", ""),
        )


@dataclass
class TaskLogEntry:
    id: str
    task_id: str
    started_at: str
    finished_at: str
    status: str
    summary: str
    target_label: str
    workspace_name: str
    mode: str
    dry_run: bool = False
    uploaded_count: int = 0
    changed_count: int = 0
    deleted_count: int = 0
    skipped_count: int = 0
    error: str = ""
    details: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TaskLogEntry":
        return cls(
            id=payload.get("id", ""),
            task_id=payload.get("task_id", ""),
            started_at=payload.get("started_at", ""),
            finished_at=payload.get("finished_at", ""),
            status=payload.get("status", "success"),
            summary=payload.get("summary", ""),
            target_label=payload.get("target_label", ""),
            workspace_name=payload.get("workspace_name", ""),
            mode=payload.get("mode", ""),
            dry_run=payload.get("dry_run", False),
            uploaded_count=int(payload.get("uploaded_count", 0) or 0),
            changed_count=int(payload.get("changed_count", 0) or 0),
            deleted_count=int(payload.get("deleted_count", 0) or 0),
            skipped_count=int(payload.get("skipped_count", 0) or 0),
            error=payload.get("error", ""),
            details=list(payload.get("details", [])),
        )
