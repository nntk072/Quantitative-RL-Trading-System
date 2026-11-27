"""Checkpoint reanalysis keeps its source run and existing outputs untouched."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from evaluation.reanalysis import checkpoint_reanalysis


def _argv(source: Path, output: Path) -> list[str]:
    return [
        "checkpoint-reanalysis",
        "--run",
        str(source),
        "--output",
        str(output),
        "--allow-historical",
    ]


def test_reanalysis_rejects_output_nested_inside_source_before_loading_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source-run"
    source.mkdir()
    output = source / "reanalysis"
    monkeypatch.setattr(sys, "argv", _argv(source, output))
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_load_run_config",
        lambda *_args: pytest.fail("source/output overlap must fail before config loading"),
    )

    with pytest.raises(ValueError, match="separate output outside the source run"):
        checkpoint_reanalysis.main()

    assert not output.exists()


def test_reanalysis_refuses_to_reuse_an_existing_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source-run"
    output = tmp_path / "existing-output"
    source.mkdir()
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", _argv(source, output))
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_load_run_config",
        lambda *_args: pytest.fail("existing destination must fail before config loading"),
    )

    with pytest.raises(FileExistsError, match="reanalysis output already exists"):
        checkpoint_reanalysis.main()

    assert sentinel.read_text(encoding="utf-8") == "preserve"
