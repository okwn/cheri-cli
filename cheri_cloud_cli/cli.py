"""Cheri CLI entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .activity import show_activity
from .auth import login, logout, register
from .cli_framework import CheriCommand, CheriGroup
from .client import CheriClient, CheriClientError
from .config import CheriConfigError
from .configuration import check_backend, reset_config, set_api_url, show_config
from .files import download_file, list_files, upload_file
from .sessions import JsonCredentialStore
from .task import (
    create_task,
    find_task_targets,
    list_tasks as list_task_definitions,
    pause_task,
    remove_task,
    resume_task,
    run_task,
    show_task_logs,
    start_task,
    stop_task,
    watch_tasks,
)
from .teams import create_invite, list_team, reset_invites
from .workspace import create_workspace, join_workspace, list_workspaces, manage_workspace, use_workspace


console = Console()


def make_client() -> CheriClient:
    return CheriClient()


def make_store() -> JsonCredentialStore:
    return JsonCredentialStore()


def workspace_option(function):
    return click.option(
        "--workspace",
        "workspace",
        default=None,
        help="Use a workspace id or name without changing the saved active workspace.",
    )(function)


def task_definition_options(function, *, hide_advanced: bool = True):
    for decorator in reversed(
        [
            click.option(
                "--file",
                "task_file",
                default=None,
                help="Watch a single file. Cheri checks the current folder first, then Desktop, Documents, and Downloads.",
            ),
            click.option(
                "--directory",
                "task_directory",
                default=None,
                help="Watch a directory. Cheri checks the current folder first, then Desktop, Documents, and Downloads.",
            ),
            click.option("--workspace", default=None, help="Target workspace id or name."),
            click.option(
                "--mode",
                type=click.Choice(["interval", "on-change", "instant", "hybrid"]),
                default=None,
                help="Sync mode.",
            ),
            click.option("--every", default="", help="Interval such as 10m, 30s, or 1h."),
            click.option("--debounce", "debounce_seconds", default=3, show_default=True, type=int, hidden=hide_advanced),
            click.option("--recursive/--no-recursive", default=True, show_default=True, hidden=hide_advanced),
            click.option(
                "--include",
                "include_patterns",
                multiple=True,
                help="Glob include pattern for directory tasks.",
                hidden=hide_advanced,
            ),
            click.option(
                "--exclude",
                "exclude_patterns",
                multiple=True,
                help="Glob exclude pattern for directory tasks.",
                hidden=hide_advanced,
            ),
            click.option(
                "--direction",
                type=click.Choice(["upload-only"]),
                default="upload-only",
                show_default=True,
                hidden=hide_advanced,
            ),
            click.option("--conflict-strategy", default="manual-placeholder", show_default=True, hidden=hide_advanced),
            click.option("--watch-poll-seconds", default=2.0, show_default=True, type=float, hidden=hide_advanced),
        ]
    ):
        function = decorator(function)
    return function


def _show_group_help(ctx: click.Context) -> None:
    click.echo(ctx.get_help())


def _resolve_help_context(root_command: click.Command, command_path: tuple[str, ...]) -> click.Context:
    current_command = root_command
    current_context = click.Context(root_command, info_name="cheri")
    for segment in command_path:
        if not isinstance(current_command, click.MultiCommand):
            raise click.ClickException(f"`{current_context.command_path}` does not accept subcommands.")
        next_command = current_command.get_command(current_context, segment)
        if next_command is None:
            if isinstance(current_command, CheriGroup):
                suggestion = current_command._build_unknown_command_message(current_context, segment)
                if suggestion:
                    raise click.ClickException(suggestion)
            raise click.ClickException(f"Unknown help topic: {' '.join(command_path)}")
        current_context = click.Context(next_command, info_name=segment, parent=current_context)
        current_command = next_command
    return current_context


@click.group(
    cls=CheriGroup,
    help="Cheri - collaborative workspace sync from the command line.",
    command_order=["register", "login", "logout", "config", "workspace", "file", "teams", "activity", "task", "help"],
    commands_heading="Core commands",
    help_hint='Use "cheri <command> --help" for more details.',
    examples=[
        "cheri register",
        "cheri login",
        "cheri config get",
        "cheri file upload ./notes.md",
        "cheri task list",
    ],
    suggestion_map={
        "files": "file list",
        "upload": "file upload",
        "download": "file download",
        "push": "file upload",
        "pull": "file download",
        "configure": "config get",
        "team": "teams list",
        "teamss": "teams list",
        "workspaces": "workspace list",
        "tasks": "task list",
    },
)
def cli() -> None:
    """Cheri root CLI."""


@cli.command(
    "register",
    cls=CheriCommand,
    help="Cheri register - create a new account and first workspace.",
    short_help="Create a new account and workspace",
    examples=[
        "cheri register",
        "cheri help workspace",
    ],
)
def register_cmd() -> None:
    register(console, make_client(), make_store())


@cli.command(
    "login",
    cls=CheriCommand,
    help="Cheri login - sign in with your bootstrap secret and refresh local workspace access.",
    short_help="Sign in and refresh workspace access",
    examples=[
        "cheri login",
        "cheri login --invite CHR-TEAM-8X2K91QZ",
    ],
)
@click.option("--invite", "invite_code", default="", help="Optional team invite code to accept after login.")
@click.option("--force", is_flag=True, help="Ignore saved local session and sign in again.")
def login_cmd(invite_code: str, force: bool) -> None:
    login(console, make_client(), make_store(), invite_code=invite_code, force=force)


@cli.command(
    "logout",
    cls=CheriCommand,
    help="Cheri logout - clear the local session and revoke the current backend session.",
    short_help="Clear the local session",
    examples=[
        "cheri logout",
    ],
)
def logout_cmd() -> None:
    logout(console, make_client(), make_store())


@cli.group(
    "config",
    cls=CheriGroup,
    invoke_without_command=True,
    help="Cheri config - show and change local CLI backend settings.",
    short_help="Show and change local CLI settings",
    command_order=["get", "set", "reset", "check"],
    examples=[
        "cheri config get",
        "cheri config set api-url https://cheri.parapanteri.com",
        "cheri config reset",
        "cheri config check",
    ],
)
@click.pass_context
def config_group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    show_config(console)


@config_group.command(
    "get",
    cls=CheriCommand,
    help="Cheri config get - show the current backend URL and local config state.",
    short_help="Show current backend settings",
    examples=[
        "cheri config get",
    ],
)
def config_get_cmd() -> None:
    show_config(console)


@config_group.group(
    "set",
    cls=CheriGroup,
    help="Cheri config set - persist a local Cheri CLI setting.",
    short_help="Persist a local setting",
    command_order=["api-url"],
    examples=[
        "cheri config set api-url https://cheri.parapanteri.com",
    ],
)
def config_set_group() -> None:
    return


@config_set_group.command(
    "api-url",
    cls=CheriCommand,
    help="Cheri config set api-url - set the backend API URL used by the CLI.",
    short_help="Set the backend API URL",
    examples=[
        "cheri config set api-url https://cheri.parapanteri.com",
    ],
)
@click.argument("url")
def config_set_api_url_cmd(url: str) -> None:
    set_api_url(console, url)


@config_group.command(
    "reset",
    cls=CheriCommand,
    help="Cheri config reset - clear the saved local API URL and return to deployment defaults.",
    short_help="Clear the saved API URL",
    examples=[
        "cheri config reset",
    ],
)
def config_reset_cmd() -> None:
    reset_config(console)


@config_group.command(
    "check",
    cls=CheriCommand,
    help="Cheri config check - verify that the configured backend API is reachable.",
    short_help="Check backend connectivity",
    examples=[
        "cheri config check",
    ],
)
def config_check_cmd() -> None:
    check_backend(console, make_client())


@cli.group(
    "workspace",
    cls=CheriGroup,
    invoke_without_command=True,
    help="Cheri workspace - manage workspaces.",
    short_help="Manage workspaces",
    command_order=["create", "list", "use", "join"],
    examples=[
        "cheri workspace list",
        "cheri workspace create --name docs",
        "cheri workspace use docs",
        "cheri workspace join CHR-TEAM-8X2K91QZ",
    ],
    suggestion_map={
        "select": "use",
        "switch": "use",
        "new": "create",
        "accept": "join",
    },
)
@click.option("--name", default=None, hidden=True)
@click.pass_context
def workspace_group(ctx: click.Context, name: Optional[str]) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if name:
        manage_workspace(console, make_client(), make_store(), name=name)
        return
    list_workspaces(console, make_client(), make_store())


@workspace_group.command(
    "create",
    cls=CheriCommand,
    help="Cheri workspace create - create a workspace and select it as the active workspace.",
    short_help="Create a workspace",
    examples=[
        "cheri workspace create --name docs",
        "cheri workspace create --name team-alpha",
    ],
)
@click.option("--name", required=True, help="Workspace name.")
def workspace_create_cmd(name: str) -> None:
    create_workspace(console, make_client(), make_store(), name=name)


@workspace_group.command(
    "list",
    cls=CheriCommand,
    help="Cheri workspace list - show the workspaces you can access.",
    short_help="List accessible workspaces",
    examples=[
        "cheri workspace list",
    ],
)
def workspace_list_cmd() -> None:
    list_workspaces(console, make_client(), make_store())


@workspace_group.command(
    "use",
    cls=CheriCommand,
    help="Cheri workspace use - switch the saved active workspace by id or name.",
    short_help="Switch the active workspace",
    examples=[
        "cheri workspace use docs",
        "cheri workspace use wksp_1234abcd",
    ],
)
@click.argument("id_or_name")
def workspace_use_cmd(id_or_name: str) -> None:
    use_workspace(console, make_client(), make_store(), identifier=id_or_name)


@workspace_group.command(
    "join",
    cls=CheriCommand,
    help="Cheri workspace join - join a workspace using an invite code.",
    short_help="Join a workspace by invite code",
    examples=[
        "cheri workspace join CHR-TEAM-8X2K91QZ",
    ],
)
@click.argument("invite_code")
def workspace_join_cmd(invite_code: str) -> None:
    join_workspace(console, make_client(), make_store(), invite_code=invite_code)


@cli.group(
    "file",
    cls=CheriGroup,
    invoke_without_command=True,
    help="Cheri file - manage workspace files.",
    short_help="Upload, download, and list files",
    command_order=["upload", "download", "list"],
    examples=[
        "cheri file upload ./notes.md",
        "cheri file download notes.md",
        "cheri file list",
    ],
    suggestion_map={
        "files": "list",
        "push": "upload",
        "pull": "download",
    },
)
@click.pass_context
def file_group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    list_files(console, make_client(), make_store())


@file_group.command(
    "upload",
    cls=CheriCommand,
    help="Cheri file upload - upload a local file or directory to the active workspace.",
    short_help="Upload a file or directory",
    examples=[
        "cheri file upload ./notes.md",
        "cheri file upload ./src",
        "cheri file upload ./report.pdf --workspace docs",
    ],
)
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path))
@workspace_option
def file_upload_cmd(path: Path, workspace: Optional[str]) -> None:
    upload_file(console, make_client(), make_store(), path, workspace=workspace)


@file_group.command(
    "download",
    cls=CheriCommand,
    help="Cheri file download - download a file by name or id from the active workspace.",
    short_help="Download a file",
    examples=[
        "cheri file download notes.md",
        "cheri file download file_1234abcd --dest ./downloads",
        "cheri file download notes.md --force",
    ],
)
@click.argument("file_or_id")
@click.option("--dest", type=click.Path(path_type=Path), default=Path("."), help="Destination directory or file path.")
@click.option("--force", is_flag=True, help="Overwrite an existing destination path.")
@workspace_option
def file_download_cmd(file_or_id: str, dest: Path, force: bool, workspace: Optional[str]) -> None:
    download_file(console, make_client(), make_store(), file_or_id, dest, workspace=workspace, force=force)


@file_group.command(
    "list",
    cls=CheriCommand,
    help="Cheri file list - list files in the active workspace.",
    short_help="List workspace files",
    examples=[
        "cheri file list",
        "cheri file list --workspace docs",
    ],
)
@workspace_option
def file_list_cmd(workspace: Optional[str]) -> None:
    list_files(console, make_client(), make_store(), workspace=workspace)


@cli.group(
    "teams",
    cls=CheriGroup,
    invoke_without_command=True,
    help="Cheri teams - manage workspace invites and members.",
    short_help="Manage team invites and members",
    command_order=["invite", "list", "invite-reset"],
    examples=[
        "cheri teams invite",
        "cheri teams list",
        "cheri teams invite-reset --new",
    ],
    suggestion_map={
        "team": "list",
        "reset": "invite-reset",
    },
)
@click.pass_context
def teams_group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    list_team(console, make_client(), make_store())


@teams_group.command(
    "invite",
    cls=CheriCommand,
    help="Cheri teams invite - create a short invite code for the active workspace.",
    short_help="Create an invite code",
    examples=[
        "cheri teams invite",
        "cheri teams invite --label contractor",
    ],
)
@click.option("--label", default="", help="Optional label for the invite.")
@workspace_option
def teams_invite_cmd(label: str, workspace: Optional[str]) -> None:
    create_invite(console, make_client(), make_store(), label=label, workspace=workspace)


@teams_group.command(
    "list",
    cls=CheriCommand,
    help="Cheri teams list - show workspace members and current invite state.",
    short_help="List members and invite state",
    examples=[
        "cheri teams list",
        "cheri teams list --workspace docs",
    ],
)
@workspace_option
def teams_list_cmd(workspace: Optional[str]) -> None:
    list_team(console, make_client(), make_store(), workspace=workspace)


@teams_group.command(
    "invite-reset",
    cls=CheriCommand,
    help="Cheri teams invite-reset - revoke current invite codes and optionally create a replacement.",
    short_help="Revoke and rotate invite codes",
    examples=[
        "cheri teams invite-reset",
        "cheri teams invite-reset --new --label weekend-access",
    ],
)
@click.option("--new", "create_replacement", is_flag=True, help="Create a replacement invite code after the reset.")
@click.option("--label", default="", help="Optional label for the replacement invite.")
@workspace_option
def teams_invite_reset_cmd(create_replacement: bool, label: str, workspace: Optional[str]) -> None:
    reset_invites(
        console,
        make_client(),
        make_store(),
        create_replacement=create_replacement,
        label=label,
        workspace=workspace,
    )


@cli.command(
    "activity",
    cls=CheriCommand,
    help="Cheri activity - show recent uploads, changes, and collaboration events for a workspace.",
    short_help="Show recent workspace changes",
    examples=[
        "cheri activity",
        "cheri activity --workspace docs",
    ],
)
@workspace_option
def activity_cmd(workspace: Optional[str]) -> None:
    show_activity(console, make_client(), make_store(), workspace=workspace)


@cli.group(
    "task",
    cls=CheriGroup,
    invoke_without_command=True,
    help="Cheri task - create and manage automated sync tasks.",
    short_help="Create and manage sync tasks",
    command_order=["create", "find", "list", "start", "stop", "remove", "run", "logs", "watch"],
    examples=[
        "cheri task create --directory cheri_test_files --mode on-change",
        'cheri task create --directory "C:\\Users\\Name\\Desktop\\cheri_test_files" --mode on-change',
        "cheri task list",
        "cheri task stop task_ab12cd34",
        "cheri task start task_ab12cd34",
    ],
    suggestion_map={
        "delete": "remove",
        "pause": "stop",
        "resume": "start",
    },
)
@click.pass_context
def task_group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    list_task_definitions(console)


@task_group.command(
    "create",
    cls=CheriCommand,
    help="Cheri task create - create a sync task and start watching immediately by default.",
    short_help="Create a sync task",
    examples=[
        "cheri task create --directory cheri_test_files --mode on-change",
        'cheri task create --directory "C:\\Users\\Name\\Desktop\\cheri_test_files" --mode on-change',
        "cheri task create --file notes.md --mode interval --every 10m",
        "cheri task create --directory Downloads --pick",
    ],
)
@task_definition_options
@click.option("--no-start", is_flag=True, help="Create the task without starting background watching.")
@click.option("--pick", is_flag=True, help="Show a selection list when Cheri finds matching folders or files.")
def task_create_cmd(
    task_file: Optional[str],
    task_directory: Optional[str],
    workspace: Optional[str],
    mode: Optional[str],
    every: str,
    debounce_seconds: int,
    recursive: bool,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    direction: str,
    conflict_strategy: str,
    watch_poll_seconds: float,
    no_start: bool,
    pick: bool,
) -> None:
    create_task(
        console,
        make_client(),
        make_store(),
        task_file=task_file,
        task_directory=task_directory,
        workspace=workspace,
        mode=mode,
        on_change=False,
        instant=False,
        every=every,
        debounce_seconds=debounce_seconds,
        recursive=recursive,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        direction=direction,
        conflict_strategy=conflict_strategy,
        watch_poll_seconds=watch_poll_seconds,
        no_start=no_start,
        pick=pick,
    )


@task_group.command(
    "find",
    cls=CheriCommand,
    help="Cheri task find - locate a likely file or directory target in the current folder, Desktop, Documents, or Downloads.",
    short_help="Find a file or directory target",
    examples=[
        "cheri task find cheri_test_files",
        "cheri task find notes.md --file",
    ],
)
@click.argument("query")
@click.option("--file", "target_type", flag_value="file", default="directory", help="Search for a file target.")
@click.option("--directory", "target_type", flag_value="directory", help="Search for a directory target.")
def task_find_cmd(query: str, target_type: str) -> None:
    find_task_targets(console, query, target_type=target_type)


@task_group.command(
    "list",
    cls=CheriCommand,
    help="Cheri task list - list saved sync tasks.",
    short_help="List saved sync tasks",
    examples=[
        "cheri task list",
    ],
)
def task_list_cmd() -> None:
    list_task_definitions(console)


@task_group.command(
    "start",
    cls=CheriCommand,
    help="Cheri task start - start or restart background watching for a saved sync task.",
    short_help="Start background watching",
    examples=[
        "cheri task start task_ab12cd34",
    ],
)
@click.argument("task_id")
def task_start_cmd(task_id: str) -> None:
    start_task(console, make_client(), make_store(), task_id)


@task_group.command(
    "stop",
    cls=CheriCommand,
    help="Cheri task stop - stop background watching without deleting the task definition.",
    short_help="Stop background watching",
    examples=[
        "cheri task stop task_ab12cd34",
    ],
)
@click.argument("task_id")
def task_stop_cmd(task_id: str) -> None:
    stop_task(console, make_client(), make_store(), task_id)


@task_group.command(
    "pause",
    cls=CheriCommand,
    hidden=True,
)
@click.argument("task_id")
def task_pause_cmd(task_id: str) -> None:
    pause_task(console, task_id)


@task_group.command(
    "resume",
    cls=CheriCommand,
    hidden=True,
)
@click.argument("task_id")
def task_resume_cmd(task_id: str) -> None:
    resume_task(console, task_id)


@task_group.command(
    "remove",
    cls=CheriCommand,
    help="Cheri task remove - delete a saved sync task and its local runtime data.",
    short_help="Remove a task",
    examples=[
        "cheri task remove task_ab12cd34",
    ],
)
@click.argument("task_id")
def task_remove_cmd(task_id: str) -> None:
    remove_task(console, task_id)


@task_group.command(
    "run",
    cls=CheriCommand,
    help="Cheri task run - run one sync task immediately.",
    short_help="Run a task now",
    examples=[
        "cheri task run task_ab12cd34",
        "cheri task run task_ab12cd34 --dry-run",
    ],
)
@click.argument("task_id")
@click.option("--dry-run", is_flag=True, help="Show sync decisions without uploading.")
def task_run_cmd(task_id: str, dry_run: bool) -> None:
    run_task(console, make_client(), make_store(), task_id, dry_run=dry_run)


@task_group.command(
    "logs",
    cls=CheriCommand,
    help="Cheri task logs - show recent local execution logs for a task.",
    short_help="Show task logs",
    examples=[
        "cheri task logs task_ab12cd34",
    ],
)
@click.argument("task_id")
def task_logs_cmd(task_id: str) -> None:
    show_task_logs(console, task_id)


@task_group.command(
    "watch",
    cls=CheriCommand,
    help="Cheri task watch - run the foreground watch loop for one task or all enabled tasks.",
    short_help="Watch tasks in the foreground",
    examples=[
        "cheri task watch task_ab12cd34",
        "cheri task watch --all",
        "cheri task watch --all --dry-run",
    ],
)
@click.argument("task_id", required=False)
@click.option("--all", "watch_all", is_flag=True, help="Watch all enabled tasks.")
@click.option("--dry-run", is_flag=True, help="Show sync decisions without uploading.")
@click.option("--poll-seconds", default=None, type=float, hidden=True)
@click.option("--background", is_flag=True, hidden=True)
def task_watch_cmd(
    task_id: Optional[str],
    watch_all: bool,
    dry_run: bool,
    poll_seconds: Optional[float],
    background: bool,
) -> None:
    watch_tasks(
        console,
        make_client(),
        make_store(),
        task_id=task_id,
        watch_all=watch_all,
        dry_run=dry_run,
        poll_seconds=poll_seconds,
        background=background,
    )


@cli.command(
    "help",
    cls=CheriCommand,
    help="Cheri help - show help for Cheri or a command group.",
    short_help="Show command help",
    examples=[
        "cheri help",
        "cheri help file",
        "cheri help task create",
    ],
)
@click.argument("command_path", nargs=-1)
@click.pass_context
def help_cmd(ctx: click.Context, command_path: tuple[str, ...]) -> None:
    root_command = ctx.parent.command if ctx.parent else cli
    target_context = _resolve_help_context(root_command, command_path)
    click.echo(target_context.command.get_help(target_context))


@cli.command("upload", cls=CheriCommand, hidden=True)
@click.argument("path", type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path))
@workspace_option
def upload_alias_cmd(path: Path, workspace: Optional[str]) -> None:
    upload_file(console, make_client(), make_store(), path, workspace=workspace)


@cli.command("download", cls=CheriCommand, hidden=True)
@click.argument("file_or_id")
@click.option("--dest", type=click.Path(path_type=Path), default=Path("."))
@click.option("--force", is_flag=True)
@workspace_option
def download_alias_cmd(file_or_id: str, dest: Path, force: bool, workspace: Optional[str]) -> None:
    download_file(console, make_client(), make_store(), file_or_id, dest, workspace=workspace, force=force)


@cli.command("files", cls=CheriCommand, hidden=True)
@workspace_option
def files_alias_cmd(workspace: Optional[str]) -> None:
    list_files(console, make_client(), make_store(), workspace=workspace)


def main() -> None:
    try:
        cli(standalone_mode=True)
    except (CheriClientError, CheriConfigError) as exc:
        console.print(f"[red]Error:[/] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
