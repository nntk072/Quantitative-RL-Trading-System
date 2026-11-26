"""Contracts for the public evaluation command dispatcher."""

from __future__ import annotations

import sys

import pytest

import evaluation.cli as evaluation_cli
import evaluation.reanalysis.checkpoint_reanalysis as checkpoint_reanalysis


def test_reanalyze_forwards_arguments_and_restores_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    original_argv = ["qrl-evaluate", "reanalyze", "--checkpoint", "latest"]
    monkeypatch.setattr(sys, "argv", original_argv)
    forwarded_argv: list[list[str]] = []

    def fake_reanalysis_main() -> None:
        forwarded_argv.append(sys.argv.copy())

    monkeypatch.setattr(checkpoint_reanalysis, "main", fake_reanalysis_main)

    evaluation_cli.main()

    assert forwarded_argv == [["qrl-evaluate", "--checkpoint", "latest"]]
    assert sys.argv == original_argv


def test_reanalyze_restores_argv_when_handler_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    original_argv = ["qrl-evaluate", "reanalyze", "--checkpoint", "latest"]
    monkeypatch.setattr(sys, "argv", original_argv)

    def fail_reanalysis() -> None:
        raise RuntimeError("reanalysis failed")

    monkeypatch.setattr(checkpoint_reanalysis, "main", fail_reanalysis)

    with pytest.raises(RuntimeError, match="reanalysis failed"):
        evaluation_cli.main()

    assert sys.argv == original_argv


def test_invalid_command_uses_stable_program_name_and_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["pytest", "train"])

    with pytest.raises(SystemExit) as error:
        evaluation_cli.main()

    assert error.value.code == 2
    assert "usage: qrl-evaluate" in capsys.readouterr().err
