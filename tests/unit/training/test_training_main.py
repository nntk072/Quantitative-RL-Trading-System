from __future__ import annotations

import json
import runpy
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from omegaconf import OmegaConf

import training.runner.training as training


def _campaign_setup(tmp_path: Path, args: Namespace) -> SimpleNamespace:
    run_dir = Path(args.survival_campaign_dir)
    cfg = OmegaConf.create({"env": {"reward_mode": "survival"}, "ppo": {"total_timesteps": 100}})
    config = SimpleNamespace(cfg=cfg, args=args, device="cpu")
    data = SimpleNamespace(
        feat_cache=tmp_path / "features.parquet",
        feature_columns=["close"],
        train_bars=None,
        train_sec=None,
        cache_dir=tmp_path,
        primary_sym="ES",
        primary_ticks=None,
        schedule_path=tmp_path / "schedule.csv",
        env_vae=None,
        pre_ny_by_date=None,
        vae_model=None,
    )
    assets = SimpleNamespace(
        is_multi_seed=True,
        run_dir=run_dir,
        train_bar_count=100,
        test_bar_count=50,
        seeds=[42, 43, 44, 45, 46, 47],
    )
    return SimpleNamespace(configuration=config, data=data, run_assets=assets)


def _campaign_args(tmp_path: Path, phase: str) -> Namespace:
    return Namespace(
        survival_campaign_dir=str(tmp_path / "campaign"),
        survival_campaign_phase=phase,
        survival_campaign_seed=42,
        survival_campaign_fold=2,
        resume_checkpoint=None,
        seeds=[42, 43, 44, 45, 46, 47],
        seed=42,
        walk_forward=True,
        mvp=False,
    )


@pytest.mark.parametrize("failure_stage", ["seed_training", "finalization", "walk_forward"])
@pytest.mark.parametrize("gate_failure_kind", ["system_exit", "runtime_error"])
def test_failed_survival_qualification_writes_gate_and_stops_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_stage: str,
    gate_failure_kind: str,
) -> None:
    seeds = [42, 43, 44, 45, 46, 47]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config = SimpleNamespace(
        cfg=OmegaConf.create({"env": {"reward_mode": "survival"}}),
        args=Namespace(),
    )
    data = SimpleNamespace(
        feat_cache=tmp_path / "features.parquet",
        feature_columns=[],
        train_bars=None,
        train_sec=None,
        cache_dir=tmp_path,
        primary_sym="US100.cash",
        primary_ticks=None,
        schedule_path=None,
        env_vae=None,
        pre_ny_by_date=None,
        vae_model=None,
    )
    config.device = "cpu"
    assets = SimpleNamespace(
        is_multi_seed=True,
        run_dir=run_dir,
        train_bar_count=10,
        test_bar_count=5,
        seeds=seeds,
    )
    prep = SimpleNamespace(configuration=config, data=data, run_assets=assets)
    seed_results = [{"seed": seed} for seed in seeds]
    gate_attempts: list[dict[str, Any]] = []

    monkeypatch.setattr(training, "prepare_training_run", lambda: prep)
    monkeypatch.setattr(training, "SeedRunContext", lambda preparation: preparation)

    def fail_seed_training(_context: Any) -> None:
        raise RuntimeError("SEED_TRAINING_FAILED")

    monkeypatch.setattr(
        training,
        "run_seed_training",
        fail_seed_training
        if failure_stage == "seed_training"
        else lambda _context: (seed_results, 100),
    )

    def fail_training(**_kwargs: Any) -> None:
        raise SystemExit("TRAIN_SURVIVAL_FAILED: seeds=[47]")

    def write_failure_gate(**kwargs: Any) -> None:
        gate_attempts.append(kwargs)
        if gate_failure_kind == "runtime_error":
            raise RuntimeError("gate artifact storage failed")
        gate_path = Path(kwargs["run_dir"]) / "survival_phase_gate.json"
        gate_path.write_text(
            json.dumps({"status": "fail", "failures": ["training survival failed"]}),
            encoding="utf-8",
        )
        raise SystemExit("SURVIVAL_PHASE_GATE_FAILED: training survival failed")

    monkeypatch.setattr(
        training,
        "finalize_training_run",
        fail_training if failure_stage == "finalization" else lambda **_kwargs: None,
    )
    monkeypatch.setattr(training, "build_survival_gate", write_failure_gate)
    walk_forward = Mock()
    if failure_stage == "walk_forward":
        walk_forward.side_effect = RuntimeError("WALK_FORWARD_FAILED")
    monkeypatch.setattr(training, "run_walk_forward_validation", walk_forward)

    expected_error = {
        "seed_training": RuntimeError,
        "finalization": SystemExit,
        "walk_forward": RuntimeError,
    }[failure_stage]
    expected_message = {
        "seed_training": "SEED_TRAINING_FAILED",
        "finalization": "TRAIN_SURVIVAL_FAILED",
        "walk_forward": "WALK_FORWARD_FAILED",
    }[failure_stage]
    with pytest.raises(expected_error, match=expected_message):
        training.main()

    assert len(gate_attempts) == 1
    assert gate_attempts[0]["seeds"] == seeds
    assert gate_attempts[0]["forced_failures"][0].startswith(
        "survival qualification execution failed:"
    )
    assert expected_message in gate_attempts[0]["forced_failures"][0]
    gate_path = run_dir / "survival_phase_gate.json"
    if gate_failure_kind == "system_exit":
        assert json.loads(gate_path.read_text())["status"] == "fail"
    else:
        assert not gate_path.exists()
    if failure_stage == "finalization" or failure_stage == "seed_training":
        walk_forward.assert_not_called()
    else:
        walk_forward.assert_called_once()


def test_train_seed_campaign_resumes_existing_checkpoint_in_selected_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training.configuration import cli

    args = _campaign_args(tmp_path, "train_seed")
    prep = _campaign_setup(tmp_path, args)
    checkpoint = prep.run_assets.run_dir / "seeds" / "seed42" / "model" / "ppo_latest.zip"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"partial checkpoint")
    calls: list[list[int]] = []
    monkeypatch.setattr(sys, "argv", ["training", "--survival-campaign-phase", "train_seed"])
    monkeypatch.setattr(cli, "parse_train_args", lambda: args)
    monkeypatch.setattr(training, "prepare_training_run", lambda _args: prep)
    monkeypatch.setattr(training, "SeedRunContext", lambda preparation: preparation)

    def run_selected_seeds(_context: Any, *, selected_seeds: list[int]) -> tuple[list[Any], int]:
        calls.append(selected_seeds)
        return [], 100

    monkeypatch.setattr(
        training,
        "run_seed_training",
        run_selected_seeds,
    )

    training.main()

    assert args.resume_checkpoint == str(checkpoint.resolve())
    assert calls == [[42]]


def test_walk_forward_campaign_requires_completed_seed_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training.configuration import cli

    args = _campaign_args(tmp_path, "walk_forward_fold")
    prep = _campaign_setup(tmp_path, args)
    monkeypatch.setattr(sys, "argv", ["training", "--survival-campaign-phase", "walk_forward_fold"])
    monkeypatch.setattr(cli, "parse_train_args", lambda: args)
    monkeypatch.setattr(training, "prepare_training_run", lambda _args: prep)
    monkeypatch.setattr(training, "SeedRunContext", lambda preparation: preparation)
    monkeypatch.setattr(training, "run_walk_forward_validation", Mock())

    with pytest.raises(SystemExit, match="must finish training before walk-forward"):
        training.main()


def test_survival_campaign_finalize_validates_and_writes_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training.configuration import cli

    args = _campaign_args(tmp_path, "finalize")
    prep = _campaign_setup(tmp_path, args)
    validated: list[Path] = []
    gates: list[list[int]] = []
    monkeypatch.setattr(sys, "argv", ["training", "--survival-campaign-phase", "finalize"])
    monkeypatch.setattr(cli, "parse_train_args", lambda: args)
    monkeypatch.setattr(
        training, "_prepare_training_configuration", lambda _args: prep.configuration
    )
    monkeypatch.setattr(
        training,
        "validate_survival_campaign",
        lambda **kwargs: validated.append(kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        training,
        "build_survival_gate",
        lambda **kwargs: gates.append(kwargs["seeds"]),
    )

    training.main()

    assert validated == [Path(args.survival_campaign_dir).resolve()]
    assert gates == [args.seeds]


def test_successful_survival_training_finalizes_gate_and_all_seed_folds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prep = _campaign_setup(tmp_path, _campaign_args(tmp_path, "finalize"))
    results = [{"seed": seed} for seed in prep.run_assets.seeds]
    calls: dict[str, Any] = {"folds": [], "gates": []}
    monkeypatch.setattr(sys, "argv", ["training"])
    monkeypatch.setattr(training, "prepare_training_run", lambda: prep)
    monkeypatch.setattr(training, "SeedRunContext", lambda preparation: preparation)
    monkeypatch.setattr(training, "run_seed_training", lambda _context: (results, 100))
    monkeypatch.setattr(training, "finalize_training_run", lambda **_kwargs: None)
    monkeypatch.setattr(
        training,
        "run_walk_forward_validation",
        lambda **kwargs: calls["folds"].append(kwargs["seed"]),
    )
    monkeypatch.setattr(
        training,
        "build_survival_gate",
        lambda **kwargs: calls["gates"].append(kwargs["seeds"]),
    )

    training.main()

    assert calls["folds"] == prep.run_assets.seeds
    assert calls["gates"] == [prep.run_assets.seeds]


def test_successful_portfolio_training_validates_only_the_last_seed_fold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prep = _campaign_setup(tmp_path, _campaign_args(tmp_path, "finalize"))
    prep.configuration.cfg.env.reward_mode = "dsr"
    results = [{"seed": 42}, {"seed": 43}]
    folds: list[int] = []
    gates: list[object] = []
    monkeypatch.setattr(sys, "argv", ["training"])
    monkeypatch.setattr(training, "prepare_training_run", lambda: prep)
    monkeypatch.setattr(training, "SeedRunContext", lambda preparation: preparation)
    monkeypatch.setattr(training, "run_seed_training", lambda _context: (results, 100))
    monkeypatch.setattr(training, "finalize_training_run", lambda **_kwargs: None)
    monkeypatch.setattr(
        training,
        "run_walk_forward_validation",
        lambda **kwargs: folds.append(kwargs["seed"]),
    )
    monkeypatch.setattr(training, "build_survival_gate", lambda **kwargs: gates.append(kwargs))

    training.main()

    assert folds == [43]
    assert gates == []


def test_training_module_entrypoint_runs_with_fully_stubbed_training_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from training.runner import (
        reporting_runtime,
        seed_runtime,
        setup_runtime,
        walk_forward_validation,
    )

    prep = _campaign_setup(tmp_path, _campaign_args(tmp_path, "finalize"))
    prep.configuration.cfg.env.reward_mode = "dsr"
    monkeypatch.setattr(setup_runtime, "prepare_training_run", lambda: prep)
    monkeypatch.setattr(seed_runtime, "SeedRunContext", lambda preparation: preparation)
    monkeypatch.setattr(seed_runtime, "run_seed_training", lambda _context: ([{"seed": 42}], 10))
    monkeypatch.setattr(reporting_runtime, "finalize_training_run", lambda **_kwargs: None)
    monkeypatch.setattr(
        walk_forward_validation, "run_walk_forward_validation", lambda **_kwargs: None
    )
    monkeypatch.setattr(sys, "argv", ["training"])

    runpy.run_path(str(Path(training.__file__)), run_name="__main__")
