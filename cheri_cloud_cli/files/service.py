"""File list, upload, and download flows."""

from __future__ import annotations

import fnmatch
import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import requests
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..client import CheriClient
from ..contracts import FileUploadRequest, RemoteFile
from ..sessions import JsonCredentialStore, load_authenticated_state
from ..workspace import describe_workspace_target, resolve_workspace_id

DEFAULT_DIRECTORY_EXCLUDES = [
    ".git",
    ".git/*",
    ".git/**",
    ".cheri",
    ".cheri/*",
    ".cheri/**",
    "__pycache__",
    "__pycache__/*",
    "__pycache__/**",
    "*.swp",
    "*.tmp",
    "*.part",
    "*.crdownload",
    "*~",
    ".DS_Store",
    "Thumbs.db",
]


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _resolve_file(files, file_or_id: str):
    for item in files:
        if item.id == file_or_id or item.name == file_or_id:
            return item
    raise click.ClickException(f"File not found: {file_or_id}")


def _safe_download_relative_path(filename: str) -> Path:
    parts = [part for part in Path(filename).parts if part not in {"", ".", ".."}]
    if not parts:
        raise click.ClickException("Download target filename is invalid.")
    return Path(*parts)


def _directory_upload_allowed(relative_path: str) -> bool:
    relative_posix = relative_path.replace("\\", "/")
    return not any(fnmatch.fnmatch(relative_posix, pattern) for pattern in DEFAULT_DIRECTORY_EXCLUDES)


def _iter_directory_uploads(root: Path):
    for candidate in root.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        relative_path = candidate.relative_to(root).as_posix()
        if _directory_upload_allowed(relative_path):
            yield candidate, relative_path


def build_upload_request(path: Path, *, logical_name: Optional[str] = None) -> FileUploadRequest:
    mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return FileUploadRequest(
        filename=(logical_name or path.name).replace("\\", "/"),
        size=path.stat().st_size,
        mime_type=mime_type,
        checksum=_file_checksum(path),
        local_modified_at=_local_timestamp(path),
    )


def upload_path_once(
    client: CheriClient,
    state,
    path: Path,
    *,
    workspace_id: Optional[str] = None,
    show_progress: bool = False,
    logical_name: Optional[str] = None,
) -> RemoteFile:
    upload_request = build_upload_request(path, logical_name=logical_name)
    if show_progress:
        with Progress(SpinnerColumn(), TextColumn("[cyan]Requesting upload grant..."), transient=True) as progress:
            progress.add_task("", total=None)
            grant = client.request_upload_grant(state, upload_request, workspace_id=workspace_id)
    else:
        grant = client.request_upload_grant(state, upload_request, workspace_id=workspace_id)

    with path.open("rb") as handle:
        response = requests.put(
            grant.upload_url,
            data=handle,
            headers={"Content-Type": upload_request.mime_type},
            timeout=300,
        )
    response.raise_for_status()
    return client.confirm_file_upload(state, grant.file_id, workspace_id=workspace_id)


def list_files(console: Console, client: CheriClient, store: JsonCredentialStore, *, workspace: Optional[str] = None) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    files = client.list_files(state, workspace_id=workspace_id)
    if not files:
        console.print(f"[yellow]No files found in[/] [white]{describe_workspace_target(state, workspace)}[/].")
        return
    table = Table(box=box.ROUNDED, border_style="blue", title=f"Workspace Files: {describe_workspace_target(state, workspace)}")
    table.add_column("Name", style="white", width=30)
    table.add_column("Version", width=8)
    table.add_column("Size", style="cyan", width=10)
    table.add_column("Editor", style="green", width=18)
    table.add_column("Modified", style="dim", width=20)
    for item in files:
        table.add_row(item.name, str(item.version), f"{item.size / 1024:.1f} KB", item.editor, item.modified_at[:19])
    console.print(table)


def upload_file(console: Console, client: CheriClient, store: JsonCredentialStore, path: Path, *, workspace: Optional[str] = None) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    if path.is_dir():
        uploaded = []
        for file_path, logical_name in _iter_directory_uploads(path):
            uploaded.append(
                upload_path_once(
                    client,
                    state,
                    file_path,
                    workspace_id=workspace_id,
                    show_progress=False,
                    logical_name=logical_name,
                )
            )
        if not uploaded:
            raise click.ClickException("No uploadable files were found in the selected directory.")
        console.print(
            f"[green]Uploaded[/] [white]{len(uploaded)}[/] files from [white]{path}[/] "
            f"to [white]{describe_workspace_target(state, workspace)}[/]."
        )
        return

    remote_file = upload_path_once(client, state, path, workspace_id=workspace_id, show_progress=True)
    console.print(
        f"[green]Uploaded[/] [white]{remote_file.name}[/] "
        f"to [white]{describe_workspace_target(state, workspace)}[/] "
        f"as [cyan]{remote_file.id}[/] version [white]{remote_file.version}[/]."
    )


def download_file(
    console: Console,
    client: CheriClient,
    store: JsonCredentialStore,
    file_or_id: str,
    dest: Path,
    *,
    workspace: Optional[str] = None,
    force: bool = False,
) -> None:
    state = load_authenticated_state(client, store)
    workspace_id = resolve_workspace_id(state, workspace)
    remote_file = _resolve_file(client.list_files(state, workspace_id=workspace_id), file_or_id)
    grant = client.request_download_grant(state, remote_file.id, workspace_id=workspace_id)
    response = requests.get(grant.download_url, timeout=300)
    response.raise_for_status()

    download_relative_path = _safe_download_relative_path(grant.filename)
    if dest.exists() and dest.is_dir():
        output_path = dest / download_relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
    elif dest.suffix:
        output_path = dest
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = dest / download_relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        raise click.ClickException(
            f"Download target already exists: {output_path}. Use --force to overwrite it."
        )

    output_path.write_bytes(response.content)
    console.print(
        f"[green]Downloaded[/] [white]{remote_file.name}[/] "
        f"from [white]{describe_workspace_target(state, workspace)}[/] "
        f"to [white]{output_path}[/]."
    )
