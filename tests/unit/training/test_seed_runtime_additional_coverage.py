"""Deterministic seed setup and checkpoint-resume lifecycle contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest
from omegaconf import OmegaConf

from training.runner import seed_runtime


def _preparation_context(
    tmp_path: Path,
    *,
    cfg: Any,
    args: Any,
    train_env_spec: object | None,
    lagrangian_cb: object | None = None,
) -> Any:
    run_dir = tmp_path / "run"
    return SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=args,
                cfg=cfg,
                device="cpu",
                lagrangian_cb=lagrangian_cb,
            ),
            run_assets=SimpleNamespace(
                seeds=[17, 29],
                is_multi_seed=True,
                run_dir=run_dir,
                model_dir=run_dir / "model",
                train_env_spec=train_env_spec,
                obs_mmap=None,
            ),
            data=SimpleNamespace(
                train_bars=None,
                train_feat=None,
                env_vae=None,
                pre_ny_by_date=None,
                primary_ticks=None,
                vae_model=None,
            ),
        )
    )


def _args(*, resume_checkpoint: str | None = None, **kwargs: Any) -> Any:
    values = {
        "algo": "ppo",
        "reward": "dsr",
        "mvp": False,
        "resume_checkpoint": resume_checkpoint,
        "arch": "mlp",
        "use_vae": False,
        "allow_legacy_observation_schema": False,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def _resume_runner_with_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    model: Any,
    stop_schema: dict[str, Any],
) -> seed_runtime.SeedRunner:
    from learning.rl import agent
    from simulation.environment import worker

    checkpoint_path = tmp_path / "resume.zip"
    checkpoint_path.touch()
    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "ppo": {"total_timesteps": 30},
            "training": {"total_timesteps_mvp": 10, "progress_log_every": 0},
            "env": {"trade_setup_actions": False},
            "quality_diagnostics": {"enabled": False},
        }
    )
    train_env = SimpleNamespace(
        observation_schema={"version": "obs-v2"},
        trade_setup_observation_schema={"version": "setup-v1"},
        candidate_geometry_observation_schema={"version": "geometry-v1"},
    )
    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda _seed: None)
    monkeypatch.setattr(seed_runtime, "_periodic_checkpoint_callback", lambda *_args: object())
    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)
    monkeypatch.setattr(worker, "make_bundle_env", lambda _spec: train_env)
    monkeypatch.setattr(agent, "build_vector_env", lambda *_args: "vec")
    monkeypatch.setattr(
        seed_runtime, "load_sb3_training_checkpoint", lambda *_args, **_kwargs: model
    )
    monkeypatch.setattr(agent, "validate_model_architecture", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(agent, "validate_model_observation_schema", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        agent, "validate_model_trade_setup_observation_schema", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        agent,
        "validate_model_candidate_geometry_observation_schema",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(seed_runtime, "build_stop_candidate_schema", lambda _cfg: stop_schema)
    context = _preparation_context(
        tmp_path,
        cfg=cfg,
        args=_args(resume_checkpoint=str(checkpoint_path)),
        train_env_spec=object(),
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 29
    return cast(seed_runtime.SeedRunner, runner)


def test_bundle_seed_preparation_wires_optional_training_callbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from simulation.environment import worker

    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "ppo": {"total_timesteps": 40},
            "training": {"total_timesteps_mvp": 10, "progress_log_every": 8},
            "env": {"trade_setup_actions": True},
            "quality_diagnostics": {"enabled": True},
            "auxiliary": {"aux_weight": 0.2, "prediction_horizon": 3},
        }
    )
    env_spec = object()
    model = SimpleNamespace()
    checkpoint = object()
    lagrangian = object()
    train_env = object()
    calls: dict[str, Any] = {}

    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda seed: calls.setdefault("seed", seed))
    monkeypatch.setattr(seed_runtime, "_periodic_checkpoint_callback", lambda *_args: checkpoint)
    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)

    def make_bundle_env(spec: object) -> object:
        calls["spec"] = spec
        return train_env

    monkeypatch.setattr(worker, "make_bundle_env", make_bundle_env)
    monkeypatch.setattr(seed_runtime, "build_agent", lambda *_args, **_kwargs: model)
    monkeypatch.setattr(seed_runtime, "build_stop_candidate_schema", lambda _cfg: {"stops": [1]})
    monkeypatch.setattr(seed_runtime, "_log_effective_ppo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "_early_abort_callback", lambda _cfg: "abort")
    monkeypatch.setattr(seed_runtime, "EpisodeEquityCallback", lambda **_kwargs: "episode")
    monkeypatch.setattr(
        seed_runtime, "TrainingProgressCallback", lambda **kwargs: ("progress", kwargs)
    )
    monkeypatch.setattr(
        seed_runtime, "LearningDiagnosticsCallback", lambda **_kwargs: "learning-diagnostics"
    )
    monkeypatch.setattr(
        seed_runtime,
        "AuxiliaryTrainerCallback",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    context = _preparation_context(
        tmp_path,
        cfg=cfg,
        args=_args(),
        train_env_spec=env_spec,
        lagrangian_cb=lagrangian,
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 29

    prepared = runner.prepare_training()

    assert prepared.environment is train_env
    assert calls == {"seed": 29, "spec": env_spec}
    assert prepared.seed_dir == tmp_path / "run" / "seeds" / "seed29"
    assert prepared.model_dir == prepared.seed_dir / "model"
    assert prepared.requested_timesteps == 40
    assert runner.learning_timesteps == 40
    assert runner.stop_candidate_schema == {"stops": [1]}
    assert runner.callbacks[0] is lagrangian
    assert runner.callbacks[1] is checkpoint
    assert runner.callbacks[2].aux_weight == 0.2
    assert runner.callbacks[2].prediction_horizon == 3
    assert runner.callbacks[3][0] == "progress"
    assert runner.callbacks[4:] == ["episode", "learning-diagnostics", "abort"]
    assert runner.env_factory() is train_env


def test_resume_preparation_validates_model_contracts_and_only_learns_remaining_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from learning.rl import agent
    from simulation.environment import worker

    checkpoint_path = tmp_path / "resume.zip"
    checkpoint_path.touch()
    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "ppo": {"total_timesteps": 30},
            "training": {"total_timesteps_mvp": 10, "progress_log_every": 0},
            "env": {"trade_setup_actions": False},
            "quality_diagnostics": {"enabled": False},
        }
    )
    schema = {"stops": ["fixed"]}
    train_env = SimpleNamespace(
        observation_schema={"version": "obs-v2"},
        trade_setup_observation_schema={"version": "setup-v1"},
        candidate_geometry_observation_schema={"version": "geometry-v1"},
    )
    model = SimpleNamespace(num_timesteps=12, stop_candidate_schema=schema)
    calls: list[tuple[Any, ...]] = []
    checkpoint_callback = object()

    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda _seed: None)
    monkeypatch.setattr(
        seed_runtime, "_periodic_checkpoint_callback", lambda *_args: checkpoint_callback
    )
    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)
    monkeypatch.setattr(worker, "make_bundle_env", lambda _spec: train_env)

    def build_vector_env(*args: Any) -> str:
        calls.append(("vector", *args))
        return "vec"

    def load_checkpoint(path: Any, **kwargs: Any) -> Any:
        calls.append(("load", path, kwargs))
        return model

    monkeypatch.setattr(agent, "build_vector_env", build_vector_env)
    monkeypatch.setattr(
        seed_runtime,
        "load_sb3_training_checkpoint",
        load_checkpoint,
    )
    monkeypatch.setattr(
        agent,
        "validate_model_architecture",
        lambda *args, **kwargs: calls.append(("architecture", *args, kwargs)),
    )
    monkeypatch.setattr(
        agent,
        "validate_model_observation_schema",
        lambda *args, **kwargs: calls.append(("observation", *args, kwargs)),
    )
    monkeypatch.setattr(
        agent,
        "validate_model_trade_setup_observation_schema",
        lambda *args: calls.append(("trade_setup", *args)),
    )
    monkeypatch.setattr(
        agent,
        "validate_model_candidate_geometry_observation_schema",
        lambda *args: calls.append(("candidate_geometry", *args)),
    )
    monkeypatch.setattr(
        seed_runtime, "build_agent", lambda *_args, **_kwargs: pytest.fail("resume must load")
    )
    monkeypatch.setattr(seed_runtime, "build_stop_candidate_schema", lambda _cfg: schema)
    monkeypatch.setattr(seed_runtime, "_log_effective_ppo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "_early_abort_callback", lambda _cfg: None)
    monkeypatch.setattr(seed_runtime, "EpisodeEquityCallback", lambda **_kwargs: "episode")

    context = _preparation_context(
        tmp_path,
        cfg=cfg,
        args=_args(resume_checkpoint=str(checkpoint_path), allow_legacy_observation_schema=True),
        train_env_spec=object(),
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 29

    prepared = runner.prepare_training()

    assert prepared.model is model
    assert runner.learning_timesteps == 18
    assert model.stop_candidate_schema == schema
    assert [call[0] for call in calls] == [
        "vector",
        "load",
        "architecture",
        "observation",
        "trade_setup",
        "candidate_geometry",
    ]
    assert calls[1][1] == checkpoint_path
    assert calls[1][2] == {"env": "vec", "device": "cpu", "algo": "ppo"}
    assert calls[3][3]["allow_legacy_v1"] is True
    assert runner.callbacks == [checkpoint_callback, "episode"]


def test_resume_preparation_rejects_checkpoint_past_requested_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _resume_runner_with_model(
        tmp_path,
        monkeypatch,
        model=SimpleNamespace(num_timesteps=31, stop_candidate_schema={"stops": [1]}),
        stop_schema={"stops": [1]},
    )

    with pytest.raises(ValueError, match="exceeding requested 30"):
        runner.prepare_training()


def test_resume_preparation_rejects_a_changed_stop_candidate_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _resume_runner_with_model(
        tmp_path,
        monkeypatch,
        model=SimpleNamespace(num_timesteps=12, stop_candidate_schema={"stops": [1]}),
        stop_schema={"stops": [2]},
    )

    with pytest.raises(ValueError, match="stop-candidate schema is missing or differs"):
        runner.prepare_training()


def test_dashboard_eval_uses_training_prefix_and_reports_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "env": {"reward_mode": "dsr"},
            "account": {"currency": "USD"},
            "ppo": {},
            "sac": {},
            "training": {},
        }
    )
    train_bars = pd.DataFrame({"close": range(8)})
    train_features = pd.DataFrame({"signal": range(8)})
    expected_bars = train_bars.iloc[:3]
    expected_features = train_features.iloc[:3]
    ticks = object()
    tickbook = object()
    provider = object()
    result = {
        "equity": [100.0, 101.0],
        "trades": [],
        "n_steps": 2,
        "reward_sum": 4.0,
    }
    metrics = SimpleNamespace(
        total_return_pct=1.0,
        total_pnl=1.0,
        sharpe=2.0,
        sortino=3.0,
        max_drawdown=0.1,
        profit_factor=1.5,
        win_rate=0.5,
        avg_trade=1.0,
        n_trades=2,
        turnover=4.0,
    )
    captured: dict[str, Any] = {}

    class DashboardCallback:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    class Learner:
        def fit(self, _request: Any) -> object:
            return object()

    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)
    monkeypatch.setattr(seed_runtime, "make_env", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        seed_runtime,
        "BestCheckpointEvalCallback",
        lambda **_kwargs: SimpleNamespace(viability_failure_reason=None),
    )
    monkeypatch.setattr(seed_runtime, "ProgressLoggerCallback", lambda **_kwargs: object())
    monkeypatch.setattr(seed_runtime, "is_sb3_box_model", lambda _model: False)
    monkeypatch.setattr(
        seed_runtime,
        "build_eval_common",
        lambda *_args, **_kwargs: ({"observation_schema_version": "obs-v2"}, None, None, None, []),
    )
    monkeypatch.setattr(seed_runtime, "build_sb3_provider", lambda *_args: provider)
    monkeypatch.setattr(
        seed_runtime, "_dashboard_block", lambda _cfg: {"enabled": True, "eval_bars": 3}
    )
    monkeypatch.setattr(seed_runtime, "TrainingDashboardCallback", DashboardCallback)
    monkeypatch.setattr(seed_runtime, "ppo_log_interval", lambda **_kwargs: 1)
    monkeypatch.setattr(seed_runtime, "_initialize_value_head", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "build_fit_request", lambda **_kwargs: object())
    monkeypatch.setattr(seed_runtime, "build_training_learner", lambda **_kwargs: Learner())
    monkeypatch.setattr(
        seed_runtime,
        "evaluate_provider",
        lambda actual_provider, **kwargs: (
            captured.update({"provider": actual_provider, "evaluation": kwargs}) or result
        ),
    )
    monkeypatch.setattr(seed_runtime, "calculate_metrics", lambda *_args, **_kwargs: metrics)
    monkeypatch.setattr(seed_runtime, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(seed_runtime, "evaluation_periods_per_year", lambda _cfg: 252)
    monkeypatch.setattr(
        seed_runtime,
        "ticks_covering",
        lambda actual_ticks, actual_bars, **_kwargs: (
            tickbook if actual_ticks is ticks and actual_bars.equals(expected_bars) else object()
        ),
    )

    from evaluation.metrics import decision_diversity

    monkeypatch.setattr(decision_diversity, "format_diversity_text", lambda *_args: "diverse")
    monkeypatch.setattr(decision_diversity, "thresholds_from_mapping", lambda value: value)

    context = _preparation_context(
        tmp_path,
        cfg=cfg,
        args=_args(),
        train_env_spec=None,
    )
    assets = context.preparation.run_assets
    assets.train_bar_count = len(train_bars)
    assets.best_bars = None
    assets.best_features = None
    assets.bundle_path = None
    assets.train_eval_spec = None
    assets.dashboard_bars = None
    assets.dashboard_features = None
    data = context.preparation.data
    data.train_bars = train_bars
    data.train_feat = train_features
    data.cache_dir = tmp_path
    data.feat_cache = tmp_path / "features.parquet"
    data.primary_ticks = ticks
    data.env_vae = None
    data.pre_ny_by_date = None
    data.dataset_records = {"train_bars": {}}
    data.primary_sym = "ES"

    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 17
    runner.train_env = SimpleNamespace(_obs_columns=["close", "signal"])
    runner.model = SimpleNamespace(n_steps=1, n_envs=1, num_timesteps=0)
    runner.callbacks = []
    runner.seed_model_dir = tmp_path / "seed-model"
    runner.seed_dir = tmp_path / "seed"
    runner.timesteps = 10
    runner.learning_timesteps = 10
    runner.abort_cb = None
    runner.phase_timings_seconds = {}

    runner.train_model()
    emitted = captured["eval_fn"]()

    assert captured["provider"] is provider
    assert captured["evaluation"]["bars"].equals(expected_bars)
    assert captured["evaluation"]["features"].equals(expected_features)
    assert captured["evaluation"]["tickbook"] is tickbook
    assert captured["evaluation"]["deterministic"] is False
    assert emitted["evaluated_bars"] == 3
    assert emitted["evaluation_split"] == "training_prefix_monitor"
    assert emitted["reward_mean"] == 2.0
    assert emitted["account_currency"] == "USD"
    assert emitted["diversity_text"] == "diverse"
