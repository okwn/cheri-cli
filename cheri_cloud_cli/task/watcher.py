"""Watch-loop helpers for Cheri task automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import TaskDefinition, TaskRuntimeState, iso_now
from .runtime import TaskScanResult


@dataclass
class WatchDecision:
    should_run: bool
    reason: str
    scan: TaskScanResult


def poll_interval(task: TaskDefinition, override_seconds: Optional[float] = None) -> float:
    if override_seconds is not None and override_seconds > 0:
        return override_seconds
    return max(float(task.watch_poll_seconds or 2.0), 0.5)


def note_change(runtime: TaskRuntimeState) -> TaskRuntimeState:
    if not runtime.last_detected_change_at:
        runtime.last_detected_change_at = iso_now()
    return runtime


def clear_pending_change(runtime: TaskRuntimeState) -> TaskRuntimeState:
    runtime.last_detected_change_at = ""
    return runtime


def mark_watcher_started(runtime: TaskRuntimeState, *, pid: int, log_path: Path | None = None) -> TaskRuntimeState:
    started_at = iso_now()
    runtime.watcher_pid = int(pid or 0)
    runtime.watcher_started_at = started_at
    runtime.watcher_heartbeat_at = started_at
    runtime.watcher_log_path = str(log_path) if log_path else runtime.watcher_log_path
    return runtime


def touch_watcher(runtime: TaskRuntimeState) -> TaskRuntimeState:
    runtime.watcher_heartbeat_at = iso_now()
    return runtime


def clear_watcher(runtime: TaskRuntimeState) -> TaskRuntimeState:
    runtime.watcher_pid = 0
    runtime.watcher_started_at = ""
    runtime.watcher_heartbeat_at = ""
    runtime.watcher_log_path = ""
    return runtime


def watcher_active(task: TaskDefinition, runtime: TaskRuntimeState) -> bool:
    if not runtime.watcher_pid or not runtime.watcher_heartbeat_at:
        return False
    try:
        heartbeat_at = datetime.fromisoformat(runtime.watcher_heartbeat_at)
    except ValueError:
        return False
    elapsed = (datetime.now(tz=timezone.utc) - heartbeat_at).total_seconds()
    return elapsed <= max(float(task.watch_poll_seconds or 2.0) * 3, 10.0)


def debounce_elapsed(runtime: TaskRuntimeState, task: TaskDefinition) -> bool:
    if not runtime.last_detected_change_at:
        return False
    detected_at = datetime.fromisoformat(runtime.last_detected_change_at)
    elapsed = (datetime.now(tz=timezone.utc) - detected_at).total_seconds()
    return elapsed >= max(task.debounce_seconds, 0)


def has_changes(scan: TaskScanResult) -> bool:
    return bool(scan.changed_paths or scan.deleted_paths)
