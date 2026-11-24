"""Dispatch of the stable compute command surface to its Slurm command modules."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from compute import cli

COMMAND_MODULES = {
    "capacity": "compute.slurm.capacity",
    "resources": "compute.slurm.resources",
    "continuation": "compute.slurm.continuation",
    "worker": "compute.slurm.worker_dispatch",
}


def _stub_module(monkeypatch: pytest.MonkeyPatch, module: str, result: object) -> list[list[str]]:
    """Replace a command module's main with a recorder that returns ``result``."""
    calls: list[list[str]] = []

    def fake_main() -> object:
        calls.append(list(sys.argv))
        return result

    stub = type(sys)("stub")
    stub.main = fake_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module, stub)
    return calls


@pytest.mark.parametrize("command", sorted(COMMAND_MODULES))
def test_each_command_forwards_its_remaining_arguments(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    calls = _stub_module(monkeypatch, COMMAND_MODULES[command], 0)
    monkeypatch.setattr(sys, "argv", ["qrl-compute", command, "--flag", "value"])

    cli.main()

    assert calls == [["qrl-compute", "--flag", "value"]]


def test_nonzero_command_result_becomes_a_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_module(monkeypatch, COMMAND_MODULES["capacity"], 3)
    monkeypatch.setattr(sys, "argv", ["qrl-compute", "capacity"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 3


def test_non_integer_result_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_module(monkeypatch, COMMAND_MODULES["resources"], None)
    monkeypatch.setattr(sys, "argv", ["qrl-compute", "resources"])

    cli.main()

    assert len(calls) == 1


def test_argv_is_restored_after_the_command_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_module(monkeypatch, COMMAND_MODULES["worker"], 0)
    original = ["qrl-compute", "worker", "--x"]
    monkeypatch.setattr(sys, "argv", list(original))

    cli.main()

    assert sys.argv == original


def test_argv_is_restored_when_the_command_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_main() -> Any:
        raise RuntimeError("boom")

    stub = type(sys)("stub")
    stub.main = failing_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, COMMAND_MODULES["continuation"], stub)
    original = ["qrl-compute", "continuation"]
    monkeypatch.setattr(sys, "argv", list(original))

    with pytest.raises(RuntimeError, match="boom"):
        cli.main()

    assert sys.argv == original


def test_unknown_command_is_rejected_by_the_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["qrl-compute", "unknown"])

    with pytest.raises(SystemExit):
        cli.main()


def test_pytest_program_name_uses_the_compute_prog(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["/usr/bin/pytest", "--help"])

    with pytest.raises(SystemExit):
        cli.main()

    assert "qrl-compute" in capsys.readouterr().out
