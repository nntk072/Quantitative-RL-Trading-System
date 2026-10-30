"""Stable console command composition tests for Orchestra."""

from click.testing import CliRunner

from orchestra.cli import main


def test_orchestra_cli_keeps_the_supported_command_surface() -> None:
    assert set(main.commands) == {
        "run",
        "doctor",
        "stats",
        "roster",
        "tasks",
        "show",
        "fix",
        "cleanup",
        "plan",
        "cost",
        "cost-task",
        "perf",
        "restore",
    }


def test_orchestra_cli_help_lists_commands_without_running_them() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "cost-task" in result.output
    assert "restore" in result.output
