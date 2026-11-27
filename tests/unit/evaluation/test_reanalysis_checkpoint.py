"""Checkpoint resolution stays deterministic for complete and interrupted runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.reanalysis.checkpoint import resolve_checkpoint


def test_resolve_checkpoint_prefers_explicit_relative_or_absolute_path(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    model_dir = run_dir / "model"
    model_dir.mkdir(parents=True)
    explicit = run_dir / "custom.zip"
    absolute = tmp_path / "external.zip"
    explicit.touch()
    absolute.touch()
    (model_dir / "ppo_final.zip").touch()

    assert resolve_checkpoint(run_dir, "custom.zip") == explicit
    assert resolve_checkpoint(run_dir, str(absolute)) == absolute
    with pytest.raises(SystemExit, match="Checkpoint not found"):
        resolve_checkpoint(run_dir, "missing.zip")


def test_resolve_checkpoint_uses_final_then_latest_step_checkpoint(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    first = model_dir / "ppo_ckpt_100_steps.zip"
    latest = model_dir / "ppo_ckpt_250_steps.zip"
    first.touch()
    latest.touch()

    assert resolve_checkpoint(tmp_path, None) == latest
    assert "using latest checkpoint" in caplog.text

    final = model_dir / "ppo_final.zip"
    final.touch()
    assert resolve_checkpoint(tmp_path, None) == final


def test_resolve_checkpoint_reports_missing_model_artifacts(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="No model checkpoints found"):
        resolve_checkpoint(tmp_path, None)
