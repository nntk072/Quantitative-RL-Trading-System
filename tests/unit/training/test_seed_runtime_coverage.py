"""Focused lifecycle and report-only safety contracts for per-seed training."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from training.runner import seed_runtime


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
