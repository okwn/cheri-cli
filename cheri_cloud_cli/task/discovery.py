"""Friendly target discovery for Cheri task creation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


COMMON_FOLDER_NAMES = ("Desktop", "Documents", "Downloads")


@dataclass(frozen=True)
class TaskTargetCandidate:
    path: Path
    source_label: str


@dataclass(frozen=True)
class TaskTargetSearchResult:
    raw_target: str
    target_type: str
    candidates: List[TaskTargetCandidate]
    searched_locations: List[Path]


def is_simple_target_name(raw_target: str) -> bool:
    raw = (raw_target or "").strip()
    if not raw:
        return False
    path = Path(raw)
    if path.is_absolute():
        return False
    if any(part in {".", "..", "~"} for part in path.parts):
        return False
    if len(path.parts) != 1:
        return False
    return "\\" not in raw and "/" not in raw


def common_search_roots(cwd: Path | None = None) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    current = (cwd or Path.cwd()).resolve()
    roots.append(("Current directory", current))
    home = Path.home()
    for folder_name in COMMON_FOLDER_NAMES:
        candidate = home / folder_name
        if candidate.exists() and candidate.resolve() != current:
            roots.append((folder_name, candidate.resolve()))
    return roots


def search_task_targets(raw_target: str, target_type: str, *, cwd: Path | None = None) -> TaskTargetSearchResult:
    current = (cwd or Path.cwd()).resolve()
    raw = (raw_target or "").strip()
    explicit_path = Path(raw).expanduser()
    searched_locations: list[Path] = []
    candidates: list[TaskTargetCandidate] = []

    if not is_simple_target_name(raw):
        searched_locations.append(_candidate_search_path(explicit_path, base=current))
        candidate = _candidate_if_valid(explicit_path, target_type, source_label="Explicit path", base=current)
        if candidate:
            candidates.append(candidate)
        return TaskTargetSearchResult(
            raw_target=raw,
            target_type=target_type,
            candidates=_unique_candidates(candidates),
            searched_locations=_unique_paths(searched_locations),
        )

    for source_label, root in common_search_roots(current):
        searched_locations.append(root)
        direct_match = root / raw
        candidate = _candidate_if_valid(direct_match, target_type, source_label=source_label, base=current)
        if candidate:
            candidates.append(candidate)
            continue
        case_insensitive_matches = _case_insensitive_matches(root, raw, target_type)
        candidates.extend(
            TaskTargetCandidate(path=match, source_label=source_label) for match in case_insensitive_matches
        )

    return TaskTargetSearchResult(
        raw_target=raw,
        target_type=target_type,
        candidates=_unique_candidates(candidates),
        searched_locations=_unique_paths(searched_locations),
    )


def describe_search_locations(paths: Sequence[Path]) -> str:
    return "\n".join(f"- {path}" for path in _unique_paths(list(paths)))


def _candidate_if_valid(path: Path, target_type: str, *, source_label: str, base: Path) -> TaskTargetCandidate | None:
    try:
        resolved = _safe_resolve(path, base=base)
    except FileNotFoundError:
        return None
    if target_type == "file" and not resolved.is_file():
        return None
    if target_type == "directory" and not resolved.is_dir():
        return None
    return TaskTargetCandidate(path=resolved, source_label=source_label)


def _candidate_search_path(path: Path, *, base: Path) -> Path:
    candidate = path if path.is_absolute() else base / path
    return candidate.expanduser()


def _case_insensitive_matches(root: Path, raw_name: str, target_type: str) -> Iterable[Path]:
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    matches: list[Path] = []
    lowered = raw_name.lower()
    for entry in entries:
        if entry.name.lower() != lowered:
            continue
        if target_type == "file" and not entry.is_file():
            continue
        if target_type == "directory" and not entry.is_dir():
            continue
        matches.append(entry.resolve())
    return matches


def _safe_resolve(path: Path, *, base: Path) -> Path:
    candidate = path if path.is_absolute() else base / path
    return candidate.expanduser().resolve(strict=True)


def _unique_candidates(candidates: Sequence[TaskTargetCandidate]) -> list[TaskTargetCandidate]:
    unique: list[TaskTargetCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.path).lower()
        if key in seen:
            continue
        unique.append(candidate)
        seen.add(key)
    return unique


def _unique_paths(paths: Sequence[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        unique.append(path)
        seen.add(key)
    return unique
