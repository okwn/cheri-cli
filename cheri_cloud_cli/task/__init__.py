"""Task automation command handlers."""

from .service import (
    create_task,
    find_task_targets,
    list_tasks,
    pause_task,
    remove_task,
    resume_task,
    run_task,
    show_task_logs,
    start_task,
    stop_task,
    watch_tasks,
)

__all__ = [
    "create_task",
    "find_task_targets",
    "list_tasks",
    "pause_task",
    "remove_task",
    "resume_task",
    "run_task",
    "show_task_logs",
    "start_task",
    "stop_task",
    "watch_tasks",
]
