"""Stable command-line entrypoint for the Orchestra package."""

from __future__ import annotations

import click

from orchestra.commands import status, task_lifecycle


@click.group()
def main() -> None:
    """Oasis Multi-Model Coding Orchestra."""


for command_group in (task_lifecycle.command_group, status.command_group):
    for command in command_group.commands.values():
        main.add_command(command)


if __name__ == "__main__":
    main()
