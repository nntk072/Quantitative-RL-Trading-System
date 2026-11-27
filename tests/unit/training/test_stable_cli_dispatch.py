from __future__ import annotations

import sys
from types import ModuleType

import pytest

from training import cli


@pytest.mark.parametrize(
    ("argv", "module_name", "expected_args"),
    [
        (
            ["train", "--config", "config.yaml"],
            "training.runner.training",
            ["--config", "config.yaml"],
        ),
        (["backtest", "--seed", "7"], "training.runner.backtest", ["--seed", "7"]),
        (["baselines", "--help"], "training.runner.baselines", ["--help"]),
        (
            ["lstm-baseline", "--bars", "bars.csv"],
            "training.runner.lstm_baseline",
            ["--bars", "bars.csv"],
        ),
        (["vae", "--epochs", "2"], "training.runner.vae", ["--epochs", "2"]),
        (["--config", "config.yaml"], "training.runner.training", ["--config", "config.yaml"]),
    ],
)
def test_main_dispatches_legacy_and_named_commands(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    module_name: str,
    expected_args: list[str],
) -> None:
    seen: list[list[str]] = []
    module = ModuleType(module_name)

    def command_main() -> None:
        seen.append(sys.argv[1:])

    module.main = command_main  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    import training.runner

    monkeypatch.setattr(
        training.runner,
        module_name.rsplit(".", maxsplit=1)[-1],
        module,
        raising=False,
    )
    monkeypatch.setattr(sys, "argv", ["qrl", *argv])

    cli.main()

    assert seen == [expected_args]
    assert sys.argv == ["qrl", *argv]


def test_forward_raises_nonzero_integer_and_restores_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["qrl", "train"])

    with pytest.raises(SystemExit, match="3"):
        cli._forward(lambda: 3, ["--bad"])

    assert sys.argv == ["qrl", "train"]


def test_forward_restores_argv_when_command_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["qrl", "train"])

    def fail() -> None:
        raise RuntimeError("runner failed")

    with pytest.raises(RuntimeError, match="runner failed"):
        cli._forward(fail, ["--bad"])

    assert sys.argv == ["qrl", "train"]


def test_forward_ignores_zero_exit_code() -> None:
    cli._forward(lambda: 0, [])


def test_train_help_after_argument_separator_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "training.runner.training"
    module = ModuleType(module_name)
    seen: list[list[str]] = []
    module.main = lambda: seen.append(sys.argv[1:])  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setattr(sys, "argv", ["qrl", "train", "--", "--help"])

    cli.main()

    assert seen == [["--", "--help"]]


def test_train_help_uses_stable_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["qrl", "train", "--help"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0
    assert sys.argv == ["qrl", "train", "--help"]
