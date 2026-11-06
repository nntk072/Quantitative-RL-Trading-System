from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from omegaconf import OmegaConf

import training.runner.training as training


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
