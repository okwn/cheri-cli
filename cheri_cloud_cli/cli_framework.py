"""CLI help formatting and command guidance for Cheri."""

from __future__ import annotations

from difflib import get_close_matches
from typing import Iterable, Sequence

import click


def _help_records(ctx: click.Context, params: Sequence[click.Parameter]) -> list[tuple[str, str]]:
    records = []
    for param in params:
        if getattr(param, "hidden", False):
            continue
        record = param.get_help_record(ctx)
        if record:
            records.append(record)
    return records


class CheriHelpMixin:
    def __init__(self, *args, examples: Iterable[str] | None = None, **kwargs) -> None:
        self.examples = list(examples or [])
        super().__init__(*args, **kwargs)

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help:
            formatter.write_text(self.help)
            formatter.write_paragraph()
        self.format_usage(ctx, formatter)
        self.format_options(ctx, formatter)
        self._format_examples(formatter)
        self.format_epilog(ctx, formatter)

    def format_options(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        records = _help_records(ctx, self.get_params(ctx))
        if records:
            with formatter.section("Options"):
                formatter.write_dl(records)

    def _format_examples(self, formatter: click.HelpFormatter) -> None:
        if not self.examples:
            return
        with formatter.section("Examples"):
            formatter.indent()
            for example in self.examples:
                formatter.write_text(example)
            formatter.dedent()


class CheriCommand(CheriHelpMixin, click.Command):
    pass


class CheriGroup(CheriHelpMixin, click.Group):
    def __init__(
        self,
        *args,
        command_order: Iterable[str] | None = None,
        commands_heading: str = "Commands",
        help_hint: str = "",
        suggestion_map: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        self.command_order = list(command_order or [])
        self.commands_heading = commands_heading
        self.help_hint = help_hint
        self.suggestion_map = {key.lower(): value for key, value in (suggestion_map or {}).items()}
        super().__init__(*args, **kwargs)

    def list_commands(self, ctx: click.Context) -> list[str]:
        names = list(self.commands)
        ordered = [name for name in self.command_order if name in self.commands]
        ordered.extend(name for name in names if name not in ordered)
        return ordered

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help:
            formatter.write_text(self.help)
            formatter.write_paragraph()
        self.format_usage(ctx, formatter)
        self.format_commands(ctx, formatter)
        self.format_options(ctx, formatter)
        self._format_examples(formatter)
        if self.help_hint:
            formatter.write_paragraph()
            formatter.write_text(self.help_hint)
        self.format_epilog(ctx, formatter)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        rows: list[tuple[str, str]] = []
        for command_name in self.list_commands(ctx):
            command = self.get_command(ctx, command_name)
            if command is None or command.hidden:
                continue
            rows.append((command_name, command.get_short_help_str()))
        if rows:
            with formatter.section(self.commands_heading):
                formatter.write_dl(rows)

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple[str | None, click.Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as exc:
            if not args or args[0].startswith("-") or "No such command" not in str(exc):
                raise
            suggestion = self._build_unknown_command_message(ctx, args[0])
            if suggestion:
                raise click.UsageError(suggestion, ctx=ctx) from exc
            raise

    def _build_unknown_command_message(self, ctx: click.Context, token: str) -> str:
        normalized = token.strip().lower()
        suggestions: list[str] = []
        mapped = self.suggestion_map.get(normalized)
        if mapped:
            suggestions.append(mapped)
        visible_commands = []
        for name in self.list_commands(ctx):
            command = self.get_command(ctx, name)
            if command is None or command.hidden:
                continue
            visible_commands.append(name)
        for match in get_close_matches(normalized, visible_commands, n=3, cutoff=0.5):
            if match not in suggestions:
                suggestions.append(match)
        if not suggestions:
            return ""

        command_path = ctx.command_path.strip()
        lines = [f"Unknown command: `{command_path} {token}`", "Did you mean:"]
        for suggestion in suggestions:
            if suggestion.startswith(command_path):
                lines.append(f"  {suggestion}")
            else:
                lines.append(f"  {command_path} {suggestion}")
        lines.extend(["See:", f"  {command_path} --help"])
        return "\n".join(lines)
