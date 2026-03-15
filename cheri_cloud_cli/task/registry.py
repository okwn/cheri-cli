"""Local persistence for Cheri task definitions and runtime state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import ConfigPaths, get_paths
from .models import TaskDefinition, TaskRuntimeState, iso_now


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


class TaskRegistry:
    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self.paths = paths or get_paths()

    def list_tasks(self) -> List[TaskDefinition]:
        payload = _load_json(self.paths.task_registry_file, {"format_version": 1, "tasks": []})
        return [TaskDefinition.from_payload(item) for item in payload.get("tasks", [])]

    def save_tasks(self, tasks: List[TaskDefinition]) -> None:
        _write_json(
            self.paths.task_registry_file,
            {
                "format_version": 1,
                "updated_at": iso_now(),
                "tasks": [task.to_dict() for task in tasks],
            },
        )

    def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        return next((task for task in self.list_tasks() if task.id == task_id), None)

    def upsert_task(self, task: TaskDefinition) -> TaskDefinition:
        tasks = [existing for existing in self.list_tasks() if existing.id != task.id]
        tasks.append(task)
        tasks.sort(key=lambda item: item.created_at or item.id)
        self.save_tasks(tasks)
        return task

    def remove_task(self, task_id: str) -> None:
        tasks = [task for task in self.list_tasks() if task.id != task_id]
        self.save_tasks(tasks)

    def load_runtimes(self) -> Dict[str, TaskRuntimeState]:
        payload = _load_json(self.paths.task_runtime_file, {"format_version": 1, "runtimes": {}})
        return {
            task_id: TaskRuntimeState.from_payload(runtime_payload)
            for task_id, runtime_payload in payload.get("runtimes", {}).items()
        }

    def get_runtime(self, task_id: str) -> TaskRuntimeState:
        return self.load_runtimes().get(task_id, TaskRuntimeState(task_id=task_id, updated_at=iso_now()))

    def save_runtime(self, runtime: TaskRuntimeState) -> TaskRuntimeState:
        runtimes = self.load_runtimes()
        runtime.updated_at = iso_now()
        runtimes[runtime.task_id] = runtime
        _write_json(
            self.paths.task_runtime_file,
            {
                "format_version": 1,
                "updated_at": iso_now(),
                "runtimes": {task_id: item.to_dict() for task_id, item in runtimes.items()},
            },
        )
        return runtime

    def remove_runtime(self, task_id: str) -> None:
        runtimes = self.load_runtimes()
        runtimes.pop(task_id, None)
        _write_json(
            self.paths.task_runtime_file,
            {
                "format_version": 1,
                "updated_at": iso_now(),
                "runtimes": {existing_task_id: item.to_dict() for existing_task_id, item in runtimes.items()},
            },
        )
