"""Local log storage for Cheri task executions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import ConfigPaths, get_paths
from .models import TaskLogEntry, iso_now


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


class TaskLogStore:
    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self.paths = paths or get_paths()

    def list_logs(self, task_id: Optional[str] = None) -> List[TaskLogEntry]:
        payload = _load_json(self.paths.task_log_file, {"format_version": 1, "logs": []})
        logs = [TaskLogEntry.from_payload(item) for item in payload.get("logs", [])]
        if task_id:
            logs = [entry for entry in logs if entry.task_id == task_id]
        return logs

    def append(self, entry: TaskLogEntry, *, max_entries: int = 500) -> TaskLogEntry:
        logs = self.list_logs()
        logs.insert(0, entry)
        logs = logs[:max_entries]
        _write_json(
            self.paths.task_log_file,
            {
                "format_version": 1,
                "updated_at": iso_now(),
                "logs": [item.to_dict() for item in logs],
            },
        )
        return entry

    def remove_task_logs(self, task_id: str) -> None:
        logs = [entry for entry in self.list_logs() if entry.task_id != task_id]
        _write_json(
            self.paths.task_log_file,
            {
                "format_version": 1,
                "updated_at": iso_now(),
                "logs": [item.to_dict() for item in logs],
            },
        )
