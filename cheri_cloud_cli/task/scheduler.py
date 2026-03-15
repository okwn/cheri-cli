"""Scheduling helpers for Cheri task intervals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple

import click

from .models import TaskDefinition


UNIT_ALIASES = {
    "s": "second",
    "sec": "second",
    "secs": "second",
    "second": "second",
    "seconds": "second",
    "m": "minute",
    "min": "minute",
    "mins": "minute",
    "minute": "minute",
    "minutes": "minute",
    "h": "hour",
    "hr": "hour",
    "hrs": "hour",
    "hour": "hour",
    "hours": "hour",
}

UNIT_SECONDS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
}


def parse_every(value: str) -> Tuple[int, str]:
    raw = str(value or "").strip().lower()
    if not raw:
        raise click.ClickException("An interval value is required for interval or hybrid task modes.")
    digits = []
    suffix = []
    for char in raw:
        if char.isdigit() and not suffix:
            digits.append(char)
        elif not char.isspace():
            suffix.append(char)
    if not digits or not suffix:
        raise click.ClickException("Intervals must look like 10m, 5min, 30s, or 1h.")
    interval_value = int("".join(digits))
    interval_unit = UNIT_ALIASES.get("".join(suffix))
    if interval_value <= 0 or not interval_unit:
        raise click.ClickException("Unsupported interval. Use seconds, minutes, or hours.")
    return interval_value, interval_unit


def interval_seconds(task: TaskDefinition) -> int:
    if not task.interval_value or not task.interval_unit:
        return 0
    return task.interval_value * UNIT_SECONDS.get(task.interval_unit, 0)


def next_interval_timestamp(task: TaskDefinition) -> str:
    seconds = interval_seconds(task)
    if seconds <= 0:
        return ""
    return (datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def interval_due(task: TaskDefinition, next_run_at: str) -> bool:
    if task.sync_mode not in {"interval", "hybrid"}:
        return False
    if not next_run_at:
        return True
    try:
        return datetime.fromisoformat(next_run_at) <= datetime.now(tz=timezone.utc)
    except ValueError:
        return True
