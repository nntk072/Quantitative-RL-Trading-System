"""Focused lifecycle and report-only safety contracts for per-seed training."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest
from omegaconf import OmegaConf

from training.runner import seed, seed_runtime


@pytest.mark.parametrize("trades", [None, pd.DataFrame()])
def test_direction_summary_handles_absent_and_empty_trades(trades: pd.DataFrame | None) -> None:
    assert seed._direction_summary(trades) == {"long": 0, "short": 0, "opens": 0}


def test_direction_summary_handles_missing_direction_and_open_rows() -> None:
    assert seed._direction_summary(pd.DataFrame({"type": ["close"]})) == {
        "long": 0,
        "short": 0,
        "opens": 0,
    }
    assert seed._direction_summary(
        pd.DataFrame({"type": ["open", "open", "close"], "direction": [1, -1, 1]})
    ) == {
        "long": 1,
        "short": 1,
        "opens": 2,
    }
    assert seed._direction_summary(pd.DataFrame({"direction": [1, -1, 0]})) == {
        "long": 1,
        "short": 1,
        "opens": 3,
    }


def test_development_only_seed_cannot_evaluate_report_only_split() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = True

    with pytest.raises(
        RuntimeError, match="development-only runs must not evaluate the report-only split"
    ):
        runner.evaluate_test_split()


def test_test_split_evaluation_requires_a_decision_provider() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(configuration=SimpleNamespace(cfg=SimpleNamespace()))
    )
    runner.seed = 42
    runner.provider = None

    with pytest.raises(RuntimeError, match="decision provider was not created for evaluation"):
        runner.evaluate_test_split()


def test_train_split_evaluation_requires_a_decision_provider() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(configuration=SimpleNamespace(cfg=SimpleNamespace()))
    )
    runner.seed = 42
    runner.final_eval_deterministic = True
    runner.model = object()
    runner.provider = None

    with pytest.raises(RuntimeError, match="decision provider was not created for evaluation"):
        runner.evaluate_train_split()


@pytest.mark.parametrize("normalization_state_exists", [True, False])
def test_write_artifacts_exports_state_or_fails_when_train_fit_state_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    normalization_state_exists: bool,
) -> None:
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    checkpoint = seed_dir / "model.zip"
    checkpoint.write_bytes(b"model")
    feature_cache = tmp_path / "features.parquet"
    feature_cache.write_bytes(b"features")
    Path(f"{feature_cache}.hash").write_text("cache-hash\n", encoding="utf-8")
    normalization_state = tmp_path / "normalization.json"
    if normalization_state_exists:
        normalization_state.write_text('{"fit_scope":"train"}\n', encoding="utf-8")
    schedule = tmp_path / "schedule.csv"
    schedule.write_text("session\n", encoding="utf-8")
    cfg = OmegaConf.create(
        {
            "data": {},
            "env": {"reward_mode": "survival", "block_overnight": True},
            "costs": {},
            "execution": {},
            "account": {"initial_balance": 100_000, "currency": "USD"},
            "evaluation": {"annualization_convention": "trading_days"},
            "output": {
                "save_plots": False,
                "save_html": False,
                "save_csv": False,
                "dpi": 100,
                "max_order_charts": 0,
                "report_profile": "minimal",
            },
        }
    )
    model = SimpleNamespace(num_timesteps=10)
    fit_result = SimpleNamespace(
        training_steps=10,
        requested_steps=12,
        config_identity="config-id",
        input_schema_version="schema-v1",
        dataset=SimpleNamespace(dataset_id="dataset-id", provenance_id="dataset-source"),
        artifact=SimpleNamespace(
            key="checkpoint-key", media_type="application/zip", sha256="model-hash"
        ),
    )
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(resume_checkpoint=None, algo="ppo", arch="mlp"),
                cfg=cfg,
            ),
            run_assets=SimpleNamespace(
                bundle_path=None,
                test_bundle_path=None,
                data_source="fixture",
                is_multi_seed=False,
            ),
            data=SimpleNamespace(
                train_bars=pd.DataFrame({"close": [100.0]}),
                test_bars=pd.DataFrame({"close": [101.0]}),
                train_sec=None,
                test_sec=None,
                feat_cache=feature_cache,
                dataset_records={},
                train_start="2025-01-01",
                train_end="2025-06-30",
                test_start="2025-07-01",
                feature_normalization_state_path=normalization_state,
                primary_ticks=None,
                primary_sym="ES",
                schedule_path=schedule,
            ),
        )
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 42
    runner.model = model
    runner.seed_dir = seed_dir
    runner.train_env = object()
    runner.timesteps = 12
    runner.stop_candidate_schema = {"stops": []}
    runner.model_path = seed_dir / "model"
    runner.fit_result = fit_result
    runner.test_result = None
    runner.test_m = None
    runner.train_result = {"status": "survived"}
    runner.train_m = object()
    runner.phase_timings_seconds = {}
    runner.development_only = False
    captured: dict[str, Any] = {}

    monkeypatch.setattr(seed_runtime, "save_run", lambda **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "write_run_config_snapshot", lambda *_args: None)
    monkeypatch.setattr(
        seed_runtime, "sequence_feature_schema_manifest", lambda _env: {"version": 1}
    )
    monkeypatch.setattr(seed_runtime, "training_protocol_manifest", lambda **_kwargs: {})
    monkeypatch.setattr(seed_runtime, "action_schema_manifest", lambda _env: {"action": "v1"})
    monkeypatch.setattr(
        seed_runtime, "observation_schema_manifest", lambda _env: {"observation": "v1"}
    )
    monkeypatch.setattr(seed_runtime, "evaluation_periods_per_year", lambda _cfg: 252)
    monkeypatch.setattr(
        seed_runtime,
        "resolve_trading_policy",
        lambda _cfg: SimpleNamespace(to_dict=lambda: {"policy": "frozen"}),
    )
    monkeypatch.setattr(seed_runtime, "fill_delay_ms", lambda _cfg: 0)
    monkeypatch.setattr(
        seed_runtime, "_training_architecture_provenance", lambda *_args, **_kwargs: {"arch": "mlp"}
    )

    def file_digest(path: Path) -> str:
        if path == checkpoint:
            return "model-hash"
        return "schedule-hash" if path == schedule else "feature-hash"

    def write_manifest(_path: Path, manifest: dict[str, Any]) -> None:
        captured["manifest"] = manifest

    monkeypatch.setattr(seed_runtime, "file_sha256", file_digest)

    def build_manifest(**kwargs: Any) -> dict[str, Any]:
        return {
            "source": {"available": True, "head": "abc"},
            "feature_cache": {},
            "training_protocol": kwargs["training_protocol"],
        }

    monkeypatch.setattr(seed_runtime, "build_training_run_manifest", build_manifest)
    monkeypatch.setattr(seed_runtime, "write_run_manifest", write_manifest)
    from evaluation.reporting import evaluation_manifest

    monkeypatch.setattr(evaluation_manifest, "write_evaluation_manifest", lambda _path: None)

    if not normalization_state_exists:
        with pytest.raises(FileNotFoundError, match="no train-fitted normalization state"):
            runner.write_artifacts()
        return

    persisted = runner.write_artifacts()

    assert persisted.manifest_path == seed_dir / "run_manifest.json"
    assert persisted.sequence_feature_schema == {"version": 1}
    manifest = captured["manifest"]
    assert manifest["training_protocol"]["training_phase"] == "survival_qualification"
    assert manifest["learning_result"]["dataset_id"] == "dataset-id"
    assert manifest["feature_cache"]["file_sha256"] == "feature-hash"
    assert (seed_dir / "feature_normalization_state.json").read_text(
        encoding="utf-8"
    ) == '{"fit_scope":"train"}\n'


def test_test_split_evaluation_requires_a_saved_final_checkpoint() -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(cfg=SimpleNamespace()),
            run_assets=SimpleNamespace(test_eval_spec=None),
            data=SimpleNamespace(test_bars=None, test_feat=None, primary_ticks=None),
        )
    )
    runner.seed = 42
    runner.provider = object()
    runner.phase_timings_seconds = {}
    runner.eval_common = {}
    runner.model_path = None

    with pytest.raises(RuntimeError, match="learner did not produce a final checkpoint path"):
        runner.evaluate_test_split()


@pytest.mark.parametrize(
    ("model_path", "fit_result", "message"),
    [
        (None, object(), "learner did not produce a final checkpoint path"),
        (Path("model.zip"), None, "seed workflow has no learner fit result"),
    ],
)
def test_artifact_persistence_requires_checkpoint_and_fit_provenance(
    model_path: Path | None, fit_result: object | None, message: str
) -> None:
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(args=SimpleNamespace(), cfg=SimpleNamespace()),
            run_assets=SimpleNamespace(
                run_dir=Path("run"),
                bundle_path=None,
                test_bundle_path=None,
                data_source="frame",
                is_multi_seed=False,
            ),
            data=SimpleNamespace(
                train_bars=None,
                test_bars=None,
                train_sec=None,
                test_sec=None,
                feat_cache=Path("feature-cache"),
                dataset_records=[],
                train_start=None,
                train_end=None,
                test_start=None,
                primary_ticks=None,
                primary_sym="US100.cash",
                schedule_path=None,
            ),
        )
    )
    runner.seed = 42
    runner.model = SimpleNamespace(num_timesteps=10)
    runner.seed_dir = Path("run")
    runner.train_env = object()
    runner.timesteps = 10
    runner.stop_candidate_schema = {}
    runner.model_path = model_path
    runner.test_result = None
    runner.test_m = None
    runner.train_result = {}
    runner.train_m = None
    runner.phase_timings_seconds = {}
    runner.fit_result = fit_result

    with pytest.raises(RuntimeError, match=message):
        runner.write_artifacts()


@pytest.mark.parametrize(
    "algo,quality,trade_setup,expected",
    [
        ("ppo", True, False, True),
        ("ppo", False, True, True),
        ("ppo", False, False, False),
        ("sac", True, True, False),
    ],
)
def test_learning_diagnostics_are_limited_to_ppo_with_enabled_diagnostics(
    algo: str, quality: bool, trade_setup: bool, expected: bool
) -> None:
    assert seed_runtime._learning_diagnostics_enabled(algo, quality, trade_setup) is expected


@pytest.mark.parametrize(
    "survival,train_gate,activity_gate,expected_log",
    [
        (
            True,
            {"ok": True, "hard_risk_ok": True},
            {"ok": True, "status": "ACTIVE"},
            "TRAIN_FULL_SPLIT_SURVIVAL PASS",
        ),
        (
            True,
            {"ok": False, "hard_risk_ok": False},
            {"ok": False, "status": "INACTIVE"},
            "TRAIN_FULL_SPLIT_SURVIVAL FAIL",
        ),
        (
            False,
            {"ok": False},
            {"ok": False},
            "TRAIN_SURVIVAL_GATE FAIL",
        ),
        (
            False,
            {"ok": True},
            {"ok": True, "status": "ACTIVE"},
            "TRAIN_ACTIVITY_GATE PASS",
        ),
    ],
)
def test_seed_survival_status_logs_each_gate_with_its_own_meaning(
    caplog: pytest.LogCaptureFixture,
    survival: bool,
    train_gate: dict[str, Any],
    activity_gate: dict[str, Any],
    expected_log: str,
) -> None:
    with caplog.at_level("INFO", logger=seed_runtime.__name__):
        seed_runtime._log_train_survival_status(
            survival_objective=survival,
            train_result={
                "survived_full_year": survival,
                "completed_data_split": survival,
                "n_breach_sessions": 0 if survival else 1,
            },
            train_gate=train_gate,
            train_activity_gate=activity_gate,
            n_trades=0,
        )

    assert expected_log in caplog.text


def test_seed_runner_initializes_persisted_evaluation_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = SimpleNamespace(evaluation={"development_only": True})
    args = SimpleNamespace()
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(cfg=cfg, args=args),
        )
    )
    monkeypatch.setattr(seed_runtime, "final_evaluation_deterministic", lambda _cfg: False)

    runner = cast(Any, seed_runtime.SeedRunner)(context, "42")

    assert cast(Any, runner.context) is context
    assert runner.seed == 42
    assert runner.development_only is True
    assert runner.final_eval_deterministic is False
    assert runner.fit_result is None
    assert runner.model_path is None
    assert runner.provider is None
    assert runner.test_result is None
    assert runner.test_m is None


def test_bundle_evaluation_factory_binds_the_selected_environment_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from simulation.environment import worker

    calls: list[Any] = []

    def make_bundle_env(spec: Any) -> str:
        calls.append(spec)
        return "env"

    monkeypatch.setattr(worker, "make_bundle_env", make_bundle_env)
    factory = seed_runtime.SeedRunner._bundle_eval_factory("bundle-spec")

    assert factory() == "env"
    assert calls == ["bundle-spec"]


def test_lazy_training_package_entrypoint_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    import training.runner as package
    from training.runner import training

    calls: list[str] = []
    monkeypatch.setattr(training, "main", lambda: calls.append("main"))

    package.main()

    assert calls == ["main"]


@pytest.mark.parametrize("selected_seeds", [[], [99]])
def test_seed_subset_rejects_empty_or_unconfigured_work_before_training(
    monkeypatch: pytest.MonkeyPatch, selected_seeds: list[int]
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = 100

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    with pytest.raises(
        ValueError, match="selected seed work must be a non-empty subset of the configured seeds"
    ):
        seed_runtime.run_seed_training(context, selected_seeds=selected_seeds)

    assert constructed_seeds == []


def test_seed_subset_runs_configured_order_and_returns_last_seed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context: Any = SimpleNamespace(
        preparation=SimpleNamespace(run_assets=SimpleNamespace(seeds=[7, 11, 23]))
    )
    constructed_seeds: list[int] = []

    class RecordingSeedRunner:
        def __init__(self, _context: Any, seed: int) -> None:
            constructed_seeds.append(seed)
            self.seed = seed
            self.timesteps = seed * 1_000

        def run(self) -> dict[str, int]:
            return {"seed": self.seed}

    monkeypatch.setattr(seed_runtime, "SeedRunner", RecordingSeedRunner)

    results, timesteps = seed_runtime.run_seed_training(context, selected_seeds=[23, 7])

    assert constructed_seeds == [7, 23]
    assert results == [{"seed": 7}, {"seed": 23}]
    assert timesteps == 23_000


def test_seed_preparation_rejects_missing_resume_checkpoint_before_model_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_checkpoint = tmp_path / "missing.zip"
    cfg = SimpleNamespace(
        data={"timestamp_clock": "native"},
        ppo=SimpleNamespace(total_timesteps=100),
        training=SimpleNamespace(total_timesteps_mvp=20),
    )
    args = SimpleNamespace(
        algo="ppo",
        reward="dsr",
        mvp=False,
        resume_checkpoint=str(missing_checkpoint),
        arch="mlp",
        use_vae=False,
        allow_legacy_observation_schema=False,
    )
    train_bars = pd.DataFrame({"close": [100.0]})
    train_features = pd.DataFrame({"atr": [1.0]})
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=args,
                cfg=cfg,
                device="cpu",
                lagrangian_cb=None,
            ),
            run_assets=SimpleNamespace(
                seeds=[42],
                is_multi_seed=False,
                run_dir=tmp_path / "run",
                model_dir=tmp_path / "run" / "model",
                train_env_spec=None,
                obs_mmap=None,
            ),
            data=SimpleNamespace(
                train_bars=train_bars,
                train_feat=train_features,
                env_vae=None,
                pre_ny_by_date=None,
                primary_ticks=None,
                vae_model=None,
            ),
        )
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = context
    runner.seed = 42
    calls: dict[str, Any] = {}
    train_env = object()
    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda _seed: None)
    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)
    monkeypatch.setattr(seed_runtime, "ticks_covering", lambda *_args, **_kwargs: "ticks")
    monkeypatch.setattr(
        seed_runtime,
        "make_env",
        lambda *_args, **_kwargs: calls.setdefault("train_env", train_env),
    )
    monkeypatch.setattr(seed_runtime, "_periodic_checkpoint_callback", lambda *_args: object())
    monkeypatch.setattr(
        seed_runtime, "build_agent", lambda *_args, **_kwargs: pytest.fail("must not build a model")
    )

    with pytest.raises(FileNotFoundError, match="resume checkpoint not found"):
        runner.prepare_training()

    assert calls["train_env"] is train_env


def test_seed_preparation_builds_multi_seed_frame_environment_and_callbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "ppo": {"total_timesteps": 50},
            "evaluation": {"development_only": False},
            "training": {"total_timesteps_mvp": 10, "progress_log_every": 0},
            "env": {"trade_setup_actions": False},
            "quality_diagnostics": {"enabled": False},
        }
    )
    bars = pd.DataFrame({"close": [100.0, 101.0]})
    features = pd.DataFrame({"atr": [1.0, 1.0]})
    run_dir = tmp_path / "run"
    model_dir = run_dir / "model"
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(
                    algo="ppo",
                    reward="dsr",
                    mvp=False,
                    resume_checkpoint=None,
                    arch="mlp",
                    use_vae=False,
                    allow_legacy_observation_schema=False,
                ),
                cfg=cfg,
                device="cpu",
                lagrangian_cb=None,
            ),
            run_assets=SimpleNamespace(
                seeds=[7, 11],
                is_multi_seed=True,
                run_dir=run_dir,
                model_dir=model_dir,
                train_env_spec=None,
                obs_mmap=None,
            ),
            data=SimpleNamespace(
                train_bars=bars,
                train_feat=features,
                env_vae=None,
                pre_ny_by_date=None,
                primary_ticks=None,
                vae_model=None,
            ),
        )
    )
    train_env = object()
    model = SimpleNamespace()
    checkpoint = object()
    calls: dict[str, Any] = {}
    monkeypatch.setattr(seed_runtime, "final_evaluation_deterministic", lambda _cfg: True)
    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda seed: calls.setdefault("seed", seed))
    monkeypatch.setattr(seed_runtime, "_training_episodic", lambda _cfg: False)
    monkeypatch.setattr(seed_runtime, "ticks_covering", lambda *_args, **_kwargs: "ticks")
    monkeypatch.setattr(seed_runtime, "make_env", lambda *_args, **_kwargs: train_env)

    def make_checkpoint(_cfg: Any, path: Path) -> object:
        calls["checkpoint_dir"] = path
        return checkpoint

    def build_agent(*_args: Any, **kwargs: Any) -> object:
        calls["model_args"] = kwargs
        return model

    monkeypatch.setattr(seed_runtime, "_periodic_checkpoint_callback", make_checkpoint)
    monkeypatch.setattr(seed_runtime, "build_agent", build_agent)
    monkeypatch.setattr(seed_runtime, "build_stop_candidate_schema", lambda _cfg: {"stops": []})
    monkeypatch.setattr(seed_runtime, "_log_effective_ppo", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "_early_abort_callback", lambda _cfg: None)
    monkeypatch.setattr(seed_runtime, "EpisodeEquityCallback", lambda **_kwargs: "episode")

    runner = cast(Any, seed_runtime.SeedRunner)(context, 11)
    prepared = runner.prepare_training()

    assert prepared.seed == 11
    assert prepared.seed_dir == run_dir / "seeds" / "seed11"
    assert prepared.model_dir == prepared.seed_dir / "model"
    assert prepared.environment is train_env
    assert prepared.model is model
    assert prepared.requested_timesteps == 50
    assert calls["seed"] == 11
    assert calls["checkpoint_dir"] == prepared.model_dir
    assert calls["model_args"]["seed"] == 11
    assert runner.learning_timesteps == 50
    assert runner.stop_candidate_schema == {"stops": []}
    assert runner.callbacks == [checkpoint, "episode"]


@pytest.mark.parametrize(
    ("learning_timesteps", "resume_checkpoint", "viability_failure"),
    [(50, None, None), (0, "resume.zip", "full-split viability failed")],
)
def test_train_model_wires_viability_evaluation_and_persists_fit_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    learning_timesteps: int,
    resume_checkpoint: str | None,
    viability_failure: str | None,
) -> None:
    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {
            "data": {"timestamp_clock": "native"},
            "env": {"reward_mode": "dsr"},
            "ppo": {"log_std_min": -0.7, "log_std_max": 0.0},
            "sac": {"log_interval": 4},
            "training": {"debug": {"enabled": False}},
        }
    )
    bars = pd.DataFrame({"close": [100.0, 101.0]})
    features = pd.DataFrame({"atr": [1.0, 1.0]})
    model = SimpleNamespace(num_timesteps=50, n_steps=5, n_envs=1)
    fit_result = object()
    calls: dict[str, Any] = {}
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(
                    algo="ppo",
                    reward="dsr",
                    arch="mlp",
                    use_vae=False,
                    resume_checkpoint=resume_checkpoint,
                ),
                cfg=cfg,
            ),
            run_assets=SimpleNamespace(
                train_bar_count=2,
                best_bars=None,
                best_features=None,
                obs_mmap=None,
                bundle_path=None,
                train_env_spec=None,
                train_eval_spec=None,
                dashboard_bars=None,
                dashboard_features=None,
            ),
            data=SimpleNamespace(
                train_bars=bars,
                train_feat=features,
                dataset_records={"train_bars": {"source": "fixture"}},
                primary_sym="US100.cash",
                cache_dir=tmp_path,
                feat_cache=Path("features.parquet"),
                primary_ticks=None,
                env_vae=None,
                pre_ny_by_date=None,
            ),
        )
    )
    train_env = SimpleNamespace(_obs_columns=["close", "atr"])
    runner.seed = 11
    runner.train_env = train_env
    runner.model = model
    runner.callbacks = []
    runner.seed_model_dir = tmp_path / "model"
    runner.seed_dir = tmp_path / "seed"
    runner.timesteps = 50
    runner.learning_timesteps = learning_timesteps
    runner.seed_dir.mkdir()
    runner.abort_cb = (
        SimpleNamespace(reason="callback requested stop") if viability_failure else None
    )
    runner.phase_timings_seconds = {}
    checkpoint_evaluations: list[int] = []

    class CheckpointCallback:
        def __init__(self, **kwargs: Any) -> None:
            calls["checkpoint"] = kwargs
            self.viability_failure_reason = viability_failure

        def _run_eval(self) -> None:
            checkpoint_evaluations.append(1)

    class Learner:
        def fit(self, request: Any) -> object:
            calls["fit_request"] = request
            return fit_result

    monkeypatch.setattr(seed_runtime, "ticks_covering", lambda *_args, **_kwargs: "ticks")
    monkeypatch.setattr(seed_runtime, "make_env", lambda *_args, **_kwargs: train_env)
    monkeypatch.setattr(seed_runtime, "BestCheckpointEvalCallback", CheckpointCallback)
    monkeypatch.setattr(seed_runtime, "ProgressLoggerCallback", lambda **_kwargs: "progress")
    monkeypatch.setattr(seed_runtime, "is_sb3_box_model", lambda _model: False)
    monkeypatch.setattr(seed_runtime, "ppo_log_interval", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(
        seed_runtime,
        "build_eval_common",
        lambda *_args, **_kwargs: (
            {"observation_schema_version": "v2"},
            None,
            None,
            None,
            "actions",
        ),
    )
    monkeypatch.setattr(seed_runtime, "build_sb3_provider", lambda *_args: "provider")
    monkeypatch.setattr(seed_runtime, "_dashboard_block", lambda _cfg: {"enabled": False})
    monkeypatch.setattr(seed_runtime, "_initialize_value_head", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(seed_runtime, "build_fit_request", lambda *_args, **_kwargs: "fit-request")

    def build_learner(*_args: Any, **kwargs: Any) -> Learner:
        calls["reset_num_timesteps"] = kwargs["reset_num_timesteps"]
        return Learner()

    monkeypatch.setattr(seed_runtime, "build_training_learner", build_learner)

    trained = runner.train_model()

    assert trained.model_path == runner.seed_model_dir / "ppo_final"
    assert trained.fit_result is fit_result
    assert trained.abort_reason == viability_failure
    assert calls["checkpoint"]["eval_freq"] == 50
    assert calls["checkpoint"]["survival_objective"] is False
    assert calls["fit_request"] == "fit-request"
    assert runner.provider == "provider"
    assert runner.eval_common == {"observation_schema_version": "v2"}
    assert runner.strategy_actions == "actions"
    assert runner.callbacks[-2:] == [runner.best_checkpoint_callback, "progress"]
    assert runner.phase_timings_seconds["ppo_learn"] >= 0.0
    assert checkpoint_evaluations == ([1] if learning_timesteps == 0 else [])
    assert calls["reset_num_timesteps"] is (resume_checkpoint is None)
    if viability_failure:
        assert runner.abort_reason == "full-split viability failed"
        assert json.loads((runner.seed_dir / "early_abort.json").read_text()) == {
            "reason": "full-split viability failed",
            "timesteps": 50,
        }


@pytest.mark.parametrize(
    ("development_only", "allow_selection", "test_result", "expected_role"),
    [
        (True, True, None, "development_only"),
        (
            False,
            False,
            {"entry_diag": {"eligible": 4}, "entry_state_diagnostics": {"valid": True}},
            "final_report_only",
        ),
        (
            False,
            True,
            {"entry_diag": {"eligible": 4}, "entry_state_diagnostics": {"valid": True}},
            "selection_acknowledged",
        ),
    ],
)
def test_build_result_preserves_oos_role_and_per_seed_risk_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    development_only: bool,
    allow_selection: bool,
    test_result: dict[str, Any] | None,
    expected_role: str,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    cfg = SimpleNamespace(
        env={"strategy_actions": True, "trade_setup_actions": False, "agent_entry_execution": 1}
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                args=SimpleNamespace(allow_locked_oos_for_selection=allow_selection), cfg=cfg
            ),
            run_assets=SimpleNamespace(run_dir=run_dir),
        )
    )
    runner.seed = 42
    runner.train_env = object()
    runner.model = SimpleNamespace(num_timesteps=1234)
    runner.test_result = test_result
    runner.test_m = None
    runner.train_result = {"survived_full_year": False, "n_breach_sessions": 1}
    runner.train_m = None
    runner.train_gate = {"hard_risk_ok": False, "reason": "daily_loss"}
    runner.train_activity_gate = {"status": "INACTIVE"}
    runner.best_checkpoint_callback = SimpleNamespace(
        best_checkpoint_status="none", best_n_trades=0, viability_eval_history=[]
    )
    runner.abort_reason = "daily_loss"
    runner.sequence_feature_schema = {"columns": ["close"]}
    runner.phase_timings_seconds = {"ppo_learn": 1.25}
    runner.manifest_path = run_dir / "manifest.json"
    runner.development_only = development_only
    monkeypatch.setattr(seed_runtime, "get_action_space_width", lambda _env: 5)
    monkeypatch.setattr(seed_runtime, "action_schema_manifest", lambda _env: {"width": 5})
    monkeypatch.setattr(seed_runtime, "observation_account_dim", lambda _env: 2)
    monkeypatch.setattr(seed_runtime, "observation_space_shapes", lambda _env: {"policy": [7]})
    monkeypatch.setattr(seed_runtime, "observation_schema_manifest", lambda _env: {"width": 7})

    result = runner.build_result()

    assert result["oos_role"] == expected_role
    assert result["train_result"] == {"survived_full_year": False, "n_breach_sessions": 1}
    assert result["train_gate"] == {"hard_risk_ok": False, "reason": "daily_loss"}
    assert result["env_flags"]["strategy_actions"] is True
    assert result["env_flags"]["trade_setup_actions"] is False
    assert result["env_flags"]["agent_entry_execution"] is True
    assert result["model_num_timesteps"] == 1234
    assert result["run_manifest"] == "manifest.json"
    if test_result is None:
        assert result["entry_diag"] == {}
        assert result["entry_state_diagnostics"] == {}
    else:
        assert result["entry_diag"] == {"eligible": 4}
        assert result["entry_state_diagnostics"] == {"valid": True}


@pytest.mark.parametrize("bundle_eval", [False, True])
@pytest.mark.parametrize("deterministic", [False, True])
def test_test_split_evaluation_preserves_mode_and_uses_selected_eval_source(
    monkeypatch: pytest.MonkeyPatch,
    bundle_eval: bool,
    deterministic: bool,
) -> None:
    cfg = SimpleNamespace(
        data={"timestamp_clock": "native"},
        account=SimpleNamespace(initial_balance=1_000.0, currency="USD"),
    )
    test_bars = pd.DataFrame({"close": [100.0]})
    test_features = pd.DataFrame({"atr": [1.0]})
    primary_ticks = object()
    eval_spec = object() if bundle_eval else None
    context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(cfg=cfg),
            run_assets=SimpleNamespace(test_eval_spec=eval_spec),
            data=SimpleNamespace(
                test_bars=test_bars,
                test_feat=test_features,
                primary_ticks=primary_ticks,
            ),
        )
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.development_only = False
    runner.context = context
    runner.seed = 42
    runner.provider = object()
    runner.phase_timings_seconds = {}
    runner.eval_common = {"configured": "evaluation-options"}
    runner.model_path = Path("seed/model/final.zip")
    runner.final_eval_deterministic = deterministic

    calls: dict[str, Any] = {}
    monkeypatch.setattr(seed_runtime, "_setup_rngs", lambda seed: calls.setdefault("seed", seed))
    monkeypatch.setattr(
        seed_runtime,
        "ticks_covering",
        lambda ticks, bars, source_clock_model: calls.setdefault(
            "ticks", (ticks, bars, source_clock_model)
        ),
    )
    evaluation_result = {
        "equity": [1_000.0, 1_010.0],
        "trades": [],
        "n_sessions": 2,
        "n_breach_sessions": 0,
    }

    def evaluate(provider: Any, **kwargs: Any) -> dict[str, Any]:
        calls["evaluation"] = (provider, kwargs)
        return dict(evaluation_result)

    monkeypatch.setattr(
        seed_runtime,
        "_evaluate_final_split",
        evaluate,
    )
    metrics = SimpleNamespace(
        total_pnl=10.0,
        total_return_pct=1.0,
        max_drawdown=0.0,
        sharpe=0.0,
        profit_factor=1.0,
        win_rate=1.0,
        n_trades=0,
    )
    monkeypatch.setattr(seed_runtime, "calculate_metrics", lambda *args, **kwargs: metrics)
    monkeypatch.setattr(seed_runtime, "evaluation_periods_per_year", lambda _cfg: 252)
    monkeypatch.setattr(seed_runtime, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(seed_runtime, "_direction_summary", lambda _trades: "both")
    if bundle_eval:
        from simulation.environment import worker

        env = object()

        def make_bundle_env(spec: Any) -> object:
            calls["spec"] = spec
            return env

        monkeypatch.setattr(worker, "make_bundle_env", make_bundle_env)

    runner.evaluate_test_split()

    provider, kwargs = calls["evaluation"]
    assert provider is runner.provider
    assert kwargs["deterministic"] is deterministic
    assert kwargs["configured"] == "evaluation-options"
    if bundle_eval:
        assert calls["spec"] is eval_spec
        assert kwargs["env"] is env
        assert kwargs["bars"].empty and kwargs["features"].empty
        assert kwargs["tickbook"] is None
        assert "ticks" not in calls
    else:
        assert kwargs["bars"] is test_bars
        assert kwargs["features"] is test_features
        assert calls["ticks"] == (primary_ticks, test_bars, "native")
        assert kwargs["tickbook"] is calls["ticks"]
    assert calls["seed"] == 42
    assert runner.test_result["policy_action_mode"] == (
        "deterministic" if deterministic else "stochastic"
    )
    assert runner.test_result["action_rng_seed"] == (None if deterministic else 42)
    assert runner.test_result["initial_balance"] == 1_000.0
    assert runner.test_m is metrics
    assert runner.phase_timings_seconds["test_evaluation"] >= 0.0


def test_training_progress_artifacts_use_configured_plot_options_and_optional_trade_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evaluation.reporting import trade_setup_plots
    from training.reporting import training_curves

    cfg = SimpleNamespace(
        env={"trade_setup_actions": True},
        output=SimpleNamespace(dpi=110, save_html=True),
    )
    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(configuration=SimpleNamespace(cfg=cfg))
    )
    runner.seed_model_dir = tmp_path / "model"
    runner.progress_log = tmp_path / "progress.csv"
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def save_training_plots(*args: Any, **kwargs: Any) -> None:
        calls.append(("training", args, kwargs))

    def write_trade_setup(*args: Any, **kwargs: Any) -> list[str]:
        calls.append(("trade_setup", args, kwargs))
        return ["learning.png"]

    def save_dashboard_plots(*args: Any, **kwargs: Any) -> None:
        calls.append(("dashboard", args, kwargs))

    monkeypatch.setattr(training_curves, "save_training_plots", save_training_plots)
    monkeypatch.setattr(training_curves, "save_dashboard_plots", save_dashboard_plots)
    monkeypatch.setattr(trade_setup_plots, "write_trade_setup_learning_plots", write_trade_setup)

    runner._write_training_progress_artifacts()

    assert [kind for kind, _, _ in calls] == ["training", "trade_setup", "dashboard"]
    assert calls[0][1][0] == runner.progress_log
    assert calls[0][2] == {"out_dir": runner.seed_model_dir, "dpi": 110, "save_html": True}
    assert calls[1][1][0] == runner.seed_model_dir / "learning_diagnostics.csv"
    assert calls[2][1][0] == runner.seed_model_dir / "dashboard_log.csv"


def test_training_progress_plot_failure_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from training.reporting import training_curves

    runner: Any = object.__new__(seed_runtime.SeedRunner)
    runner.context = SimpleNamespace(
        preparation=SimpleNamespace(
            configuration=SimpleNamespace(
                cfg=SimpleNamespace(env={}, output=SimpleNamespace(dpi=150, save_html=False))
            )
        )
    )
    runner.seed_model_dir = tmp_path / "model"
    runner.progress_log = tmp_path / "progress.csv"

    def fail_plot(*args: Any, **kwargs: Any) -> None:
        raise OSError("plot export unavailable")

    monkeypatch.setattr(training_curves, "save_training_plots", fail_plot)

    runner._write_training_progress_artifacts()
