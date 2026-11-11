"""Tests for the decomposed train_rl.py helper functions.

Verifies that parse_train_args, _setup_rngs, load_merged_config, and
build_training_log behave correctly after the main() decomposition.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import torch

from configuration.configuration_loader import load_config
from evaluation.metrics import PerformanceMetrics
from training.artifacts import (
    action_space_width,
    build_training_log,
    sequence_feature_schema_manifest,
    write_evaluation_artifacts,
)
from training.artifacts.aggregation import aggregate_seed_results
from training.callbacks.activity import assess_train_activity
from training.configuration.cli import load_merged_config, parse_train_args
from training.runner.data_stage import _clip_data_to_development_end, _prepare_training_data
from training.runner.reporting_runtime import (
    _hard_risk_pass,
    _peak_dd_policy_only_miss,
    finalize_training_run,
)
from training.runner.seed import _setup_rngs
from training.runner.seed_runtime import SeedRunner, _log_train_survival_status
from training.runner.stages import TrainingConfigurationStage
from training.setup.environments import _training_episodic, cost_model
from training.setup.model_state import _initialize_value_head


def test_training_runtime_hard_risk_flags_require_typed_consistent_values() -> None:
    assert _hard_risk_pass({"hard_risk_ok": True, "breached": False}) is True
    assert _hard_risk_pass({"breached": False}) is True
    assert _hard_risk_pass({"hard_risk_ok": True}) is True
    assert _hard_risk_pass({"hard_risk_ok": "true", "breached": False}) is False


def test_development_only_runner_skips_report_only_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = object.__new__(SeedRunner)
    runner.development_only = True
    calls: list[str] = []

    monkeypatch.setattr(SeedRunner, "prepare_training", lambda self: calls.append("prepare"))
    monkeypatch.setattr(SeedRunner, "train_model", lambda self: calls.append("train"))
    monkeypatch.setattr(
        SeedRunner, "_write_training_progress_artifacts", lambda self: calls.append("progress")
    )
    monkeypatch.setattr(
        SeedRunner,
        "evaluate_test_split",
        lambda self: pytest.fail("development-only run invoked report-only evaluator"),
    )
    monkeypatch.setattr(
        SeedRunner, "evaluate_train_split", lambda self: calls.append("train_evaluation")
    )
    monkeypatch.setattr(SeedRunner, "write_artifacts", lambda self: calls.append("persist"))
    monkeypatch.setattr(SeedRunner, "build_result", lambda self: {"evaluation_scope": "dev"})

    assert runner.run() == {"evaluation_scope": "dev"}
    assert calls == ["prepare", "train", "progress", "train_evaluation", "persist"]


def test_development_only_training_log_does_not_fabricate_test_metrics() -> None:
    result = build_training_log(
        seed=42,
        mvp=False,
        algo="ppo",
        arch="tcn",
        reward="dsr",
        timesteps=2_000_000,
        train_bars=100,
        test_bars=10,
        test_m=None,
        test_result=None,
        train_result={"entry_diag": {}, "entry_state_diagnostics": {}},
        oos_role="development_only",
    )

    assert result["evaluation_scope"] == "development_only"
    assert result["test_evaluation_status"] == "not_run"
    assert result["test_sharpe"] is None
    assert result["test_trades"] is None
    assert set(result["entry_funnel_by_split"]) == {"train"}
    assert result["oos_role"] == "development_only"


def test_default_training_log_scope_is_not_relabelled_when_test_is_absent() -> None:
    result = build_training_log(
        seed=42,
        mvp=False,
        algo="ppo",
        arch="mlp",
        reward="survival",
        timesteps=10,
        train_bars=100,
        test_bars=10,
        test_m=None,
        test_result=None,
    )

    assert result["evaluation_scope"] == "all_configured_splits"
    assert result["test_evaluation_status"] == "not_run"
    assert result["oos_role"] == "final_report_only"


def test_development_only_data_is_clipped_before_feature_consumers() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-12-31 23:59:00+00:00",
            "2025-12-31 23:59:59.500+00:00",
            "2026-01-01 00:00:00+00:00",
        ]
    )
    bars = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=index)

    clipped = _clip_data_to_development_end({"US100": {"M1": bars}}, train_end="2025-12-31")

    assert clipped["US100"]["M1"].index.equals(index[:2])
    assert clipped["US100"]["M1"]["close"].tolist() == [1.0, 2.0]
    assert _hard_risk_pass({"hard_risk_ok": True, "breached": True}) is False
    assert _hard_risk_pass({}) is False
    assert (
        _peak_dd_policy_only_miss({"ok": "false", "breached": False, "reason": "peak_trailing_dd"})
        is False
    )


def test_training_data_stage_clips_sentinel_rows_before_feature_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = load_config(config_path="config/research/survival_qualification.yaml")
    cfg.evaluation.development_only = True
    cfg.costs.use_tick_execution = False
    cfg.data.cache_dir = str(tmp_path / "cache")
    index = pd.DatetimeIndex(["2025-12-31 14:30", "2026-01-01 14:30"])
    bars = pd.DataFrame(
        {
            "open": [100.0, 900_001.0],
            "high": [101.0, 900_002.0],
            "low": [99.0, 900_000.0],
            "close": [100.5, 900_001.5],
        },
        index=index,
    )
    timeframes = {timeframe: bars.copy() for timeframe in cfg.data.timeframes}
    observed: dict[str, Any] = {}

    def fake_run_pipeline(_cfg: Any, *, force: bool, **kwargs: Any) -> dict[str, Any]:
        observed["bar_cutoff"] = kwargs.get("end_inclusive")
        assert force is False
        return {
            symbol: {timeframe: frame.copy() for timeframe, frame in timeframes.items()}
            for symbol in cfg.data.symbols
        }

    def fake_build_features(primary_m1: pd.DataFrame, **_kwargs: Any) -> pd.DataFrame:
        observed["feature_input"] = primary_m1.copy()
        return pd.DataFrame({"feature": primary_m1["close"]}, index=primary_m1.index)

    def fake_tick_books(_cfg: Any, **kwargs: Any) -> dict[str, None]:
        observed["tick_cutoff"] = kwargs.get("end_inclusive")
        return {str(cfg.data.primary): None}

    monkeypatch.setattr("training.runner.data_stage.run_pipeline", fake_run_pipeline)
    monkeypatch.setattr("training.runner.data_stage.build_features", fake_build_features)
    monkeypatch.setattr("training.runner.data_stage.build_tick_books", fake_tick_books)
    monkeypatch.setattr(
        "training.runner.data_stage.feature_cache_path",
        lambda *_args, **_kwargs: tmp_path / "features.parquet",
    )
    monkeypatch.setattr(
        "training.runner.data_stage.attach_policy_market_context",
        lambda _bars, features, *_args, **_kwargs: features,
    )
    stage = TrainingConfigurationStage(
        args=SimpleNamespace(
            force=False,
            mvp=False,
            use_vae=False,
            algo="ppo",
            arch="tcn",
            strategy="baseline",
            reward="dsr",
            walk_forward=True,
            wf_splits=5,
            allow_locked_oos_for_selection=False,
            seed=42,
            seeds=[42, 43, 44, 45, 46, 47],
        ),
        cfg=cfg,
        device="cpu",
        lagrangian_cb=None,
    )

    prepared = _prepare_training_data(stage)

    assert observed["bar_cutoff"] == "2025-12-31"
    assert observed["tick_cutoff"] == "2025-12-31"
    assert observed["feature_input"].index.equals(index[:1])
    assert observed["feature_input"]["close"].tolist() == [100.5]
    assert len(prepared.test_bars) == 0
    assert len(prepared.test_feat) == 0


def test_training_aggregation_requires_explicit_boolean_gate_passes() -> None:
    metrics = SimpleNamespace(
        sharpe=0.0,
        sortino=0.0,
        max_drawdown=0.0,
        total_return_pct=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        avg_trade=0.0,
        turnover=0.0,
        n_trades=0,
    )
    result = {
        "seed": 7,
        "test_m": metrics,
        "train_m": metrics,
        "train_gate": {
            "ok": "false",
            "end_equity": 100_000.0,
            "slope": 0.0,
            "reason": "malformed flag",
        },
        "train_activity_gate": {"ok": "false", "status": "INACTIVE", "n_trades": 0},
        "abort_reason": "",
        "model_num_timesteps": 10,
    }

    aggregated = aggregate_seed_results(
        seed_results=[result],
        seed=7,
        mvp=False,
        algo="ppo",
        arch="mlp",
        reward="survival",
        timesteps=10,
        train_bars=20,
        test_bars=10,
        strategy="baseline",
        strategy_actions=False,
        cfg=SimpleNamespace(env={}, evaluation={}),
        args=SimpleNamespace(allow_locked_oos_for_selection=False),
        run_dir=Path("."),
    )

    assert aggregated["train_equity_ok"] is False
    assert aggregated["train_activity_ok_by_seed"] == {"7": False}


def test_training_log_does_not_truth_coerce_report_split_flags() -> None:
    metrics = PerformanceMetrics(
        total_return_pct=0.0,
        total_pnl=0.0,
        max_drawdown=0.0,
        sharpe=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        n_trades=0,
    )
    log = build_training_log(
        seed=7,
        mvp=False,
        algo="ppo",
        arch="mlp",
        reward="survival",
        timesteps=10,
        train_bars=20,
        test_bars=10,
        test_m=metrics,
        test_result={
            "survived_full_year": "false",
            "completed_data_split": "false",
            "n_breach_sessions": "0",
        },
    )

    assert log["test_survived_full_year"] is False
    assert log["test_completed_data_split"] is False
    assert log["test_breaches"] is None


def test_survival_training_logs_profit_and_activity_checks_as_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="training.runner.seed_runtime")

    _log_train_survival_status(
        survival_objective=True,
        train_result={
            "survived_full_year": True,
            "completed_data_split": True,
            "n_breach_sessions": 0,
        },
        train_gate={
            "ok": False,
            "hard_risk_ok": True,
            "reason": "peak_trailing_dd",
        },
        train_activity_gate={"ok": False, "status": "INACTIVE", "n_trades": 0},
        n_trades=0,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert "TRAIN_FULL_SPLIT_SURVIVAL PASS" in messages
    assert "TRAIN_PORTFOLIO_FIT_DIAGNOSTIC MISS reason=peak_trailing_dd" in messages
    assert "TRAIN_ACTIVITY_DIAGNOSTIC status=INACTIVE trades=0" in messages
    assert "TRAIN_SURVIVAL_GATE FAIL" not in " ".join(messages)
    assert "TRAIN_ACTIVITY_GATE FAIL" not in " ".join(messages)


def test_survival_training_logs_any_incomplete_or_breached_path_as_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="training.runner.seed_runtime")

    _log_train_survival_status(
        survival_objective=True,
        train_result={
            "survived_full_year": False,
            "completed_data_split": True,
            "n_breach_sessions": 1,
        },
        train_gate={
            "ok": False,
            "hard_risk_ok": False,
            "reason": "daily_loss",
        },
        train_activity_gate={"ok": False, "status": "INACTIVE"},
        n_trades=0,
    )

    assert any(
        record.levelno == logging.ERROR
        and record.getMessage().startswith("TRAIN_FULL_SPLIT_SURVIVAL FAIL")
        for record in caplog.records
    )


def test_sequence_feature_schema_manifest_preserves_column_order() -> None:
    manifest = sequence_feature_schema_manifest(SimpleNamespace(_obs_columns=("close", "volume")))

    assert manifest["columns"] == ["close", "volume"]
    assert manifest["width"] == 2


def test_training_episode_mode_defaults_to_full_split() -> None:
    assert _training_episodic(SimpleNamespace(training={}, env={})) is False
    assert (
        _training_episodic(SimpleNamespace(training={"episode_mode": "full_split"}, env={}))
        is False
    )


def test_bundle_viability_factory_uses_spec_after_training_frames_are_released() -> None:
    from simulation.environment.worker import make_bundle_env

    env_spec = SimpleNamespace(bundle_dir="shared/train")

    factory = SeedRunner._bundle_eval_factory(env_spec)

    assert factory.func is make_bundle_env
    assert factory.args == (env_spec,)


def test_training_episode_mode_can_preserve_legacy_risk_terminated_behavior() -> None:
    cfg = SimpleNamespace(
        training={"episode_mode": "risk_terminated"},
        env={"max_episode_steps": 100},
    )
    assert _training_episodic(cfg) is True


def test_training_episode_mode_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="training.episode_mode"):
        _training_episodic(SimpleNamespace(training={"episode_mode": "random_start"}, env={}))


def test_full_split_training_rejects_artificial_episode_cap() -> None:
    cfg = SimpleNamespace(
        training={"episode_mode": "full_split"},
        env={"max_episode_steps": 100},
    )
    with pytest.raises(ValueError, match="env.max_episode_steps=null"):
        _training_episodic(cfg)


def testaction_space_width_handles_legacy_discrete_space() -> None:
    assert action_space_width(SimpleNamespace(action_space=SimpleNamespace(shape=(), n=20))) == 20
    assert action_space_width(SimpleNamespace(action_space=SimpleNamespace(shape=(5,)))) == 5
    assert action_space_width(SimpleNamespace(action_space=SimpleNamespace(shape=()))) is None


def test_evaluation_artifacts_separate_train_and_report_only_test(tmp_path: Path) -> None:
    train_metrics = PerformanceMetrics(
        total_return_pct=-1.0,
        total_pnl=-1000.0,
        max_drawdown=0.04,
        sharpe=-0.5,
        profit_factor=0.8,
        win_rate=0.4,
        n_trades=10,
    )
    test_metrics = PerformanceMetrics(
        total_return_pct=-6.76,
        total_pnl=-6760.0,
        max_drawdown=0.087,
        sharpe=-4.25,
        profit_factor=0.75,
        win_rate=0.459,
        n_trades=122,
    )

    write_evaluation_artifacts(
        run_dir=tmp_path,
        seed=42,
        completed_timesteps=106_496,
        train_result={
            "policy_action_mode": "stochastic",
            "action_rng_seed": 42,
            "n_sessions": 100,
            "days_traded": 80,
            "completed_data_split": True,
            "episode_end_reason": "data_end",
            "peak_eod_trailing_dd_limit_usd": 10_000.0,
            "max_peak_eod_trailing_dd_usd": 10_660.88,
            "peak_eod_dd_policy_ok": False,
        },
        test_result={
            "policy_action_mode": "stochastic",
            "action_rng_seed": 42,
            "n_sessions": 130,
            "days_traded": 32,
            "completed_data_split": False,
            "episode_end_reason": "max_episode_steps",
            "fail_time": "2026-02-16",
            "peak_eod_trailing_dd_limit_usd": 10_000.0,
            "max_peak_eod_trailing_dd_usd": 11_449.77,
            "peak_eod_dd_policy_ok": False,
        },
        train_metrics=train_metrics,
        test_metrics=test_metrics,
        train_gate={"ok": False, "breached": True, "reason": "max_loss_stopped_trading"},
        train_activity_gate=assess_train_activity(train_metrics.n_trades),
        account_currency="USD",
    )

    evaluation_dir = tmp_path / "evaluations"
    train = json.loads((evaluation_dir / "train_in_sample.json").read_text())
    test = json.loads((evaluation_dir / "test_report_only.json").read_text())
    summary = (evaluation_dir / "summary.md").read_text()
    summary_json = json.loads((evaluation_dir / "summary.json").read_text())

    assert train["role"] == "in_sample_training_evaluation"
    assert train["policy_action_mode"] == "stochastic"
    assert train["action_rng_seed"] == 42
    assert train["metrics"]["total_pnl"] == -1000.0
    assert train["equity_gate"]["ok"] is False
    assert train["activity_gate"]["status"] == "ACTIVE"
    assert train["peak_eod_dd_policy_fit"]["enabled"] is True
    assert train["peak_eod_dd_policy_fit"]["status"] == "MISS"
    assert summary_json["peak_eod_dd_policy_fit"]["observed_usd"] == pytest.approx(10_660.88)
    assert summary_json["test_peak_eod_dd_policy_fit"]["status"] == "MISS"
    assert "(MISS); report-only test limit=$10,000, observed=$11,449.77 (MISS)" in summary
    assert "it does not terminate the replay" in summary
    assert train["zero_trade_diagnosis"] is None
    assert train["peak_dd_policy_fit"]["status"] == "DISABLED"
    assert test["role"] == "report_only_test_evaluation"
    assert test["policy_action_mode"] == "stochastic"
    assert test["action_rng_seed"] == 42
    assert test["metrics"]["total_pnl"] == -6760.0
    assert test["oos_role"].startswith("previously_inspected_holdout")
    assert train["completed_data_split"] is True
    assert train["episode_end_reason"] == "data_end"
    assert test["completed_data_split"] is False
    assert test["episode_end_reason"] == "max_episode_steps"
    assert "| Test (report-only; previously inspected) | -6.76% | -6760.00 USD |" in summary
    assert "Both final replays use stochastic policy actions, matching PPO training." in summary
    assert "Peak-DD training policy: DISABLED" in summary
    assert "Hard-risk survival: FAIL" in summary
    assert json.loads((evaluation_dir / "summary.json").read_text())["training_admissible"] is False


def test_development_only_evaluation_writes_no_report_only_artifacts(tmp_path: Path) -> None:
    metrics = PerformanceMetrics(
        total_return_pct=0.0,
        total_pnl=0.0,
        max_drawdown=0.0,
        sharpe=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        n_trades=0,
    )
    write_evaluation_artifacts(
        run_dir=tmp_path,
        seed=42,
        completed_timesteps=2_000_000,
        train_result={"completed_data_split": True, "survived_full_year": True},
        test_result=None,
        train_metrics=metrics,
        test_metrics=None,
        train_gate={"ok": True, "hard_risk_ok": True, "breached": False},
        train_activity_gate=assess_train_activity(0),
        account_currency="USD",
        survival_objective=True,
        development_only=True,
    )

    evaluation_dir = tmp_path / "evaluations"
    summary = json.loads((evaluation_dir / "summary.json").read_text())
    report = (evaluation_dir / "summary.md").read_text()
    assert summary["evaluation_scope"] == "development_only"
    assert summary["test_evaluation_status"] == "not_run"
    assert summary["test_report_only"] is None
    assert not (evaluation_dir / "test_report_only.json").exists()
    assert "| Test (report-only" not in report
    assert "report-only test split was intentionally excluded" in report


@pytest.mark.parametrize("training_completed", [True, False])
def test_survival_evaluation_summary_ignores_profit_and_activity(
    tmp_path: Path, training_completed: bool
) -> None:
    metrics = PerformanceMetrics(
        total_return_pct=-2.0,
        total_pnl=-2_000.0,
        max_drawdown=0.05,
        sharpe=-0.5,
        profit_factor=0.7,
        win_rate=0.0,
        n_trades=0,
    )
    result: dict[str, Any] = {
        "survived_full_year": True,
        "completed_data_split": True,
        "n_breach_sessions": 0,
        "n_sessions": 100,
        "days_traded": 0,
        "equity": [],
        "peak_eod_trailing_dd_limit_usd": 10_000.0,
        "max_peak_eod_trailing_dd_usd": 12_000.0,
        "peak_eod_dd_policy_ok": False,
    }
    write_evaluation_artifacts(
        run_dir=tmp_path,
        seed=42,
        completed_timesteps=1_000_000,
        train_result=result,
        test_result=result,
        train_metrics=metrics,
        test_metrics=metrics,
        train_gate={
            "ok": False,
            "hard_risk_ok": True,
            "breached": False,
            "peak_trailing_dd_limit": 0.10,
            "max_peak_trailing_dd": 0.12,
        },
        train_activity_gate=assess_train_activity(0),
        account_currency="USD",
        survival_objective=True,
        training_completed=training_completed,
        training_incomplete_reason=None if training_completed else "nonfinite",
    )

    summary_json = json.loads((tmp_path / "evaluations" / "summary.json").read_text())
    summary = (tmp_path / "evaluations" / "summary.md").read_text()
    assert summary_json["schema_version"] == 4
    assert summary_json["training_phase"] == "survival_qualification"
    assert summary_json["train_split_survival_ok"] is True
    assert summary_json["train_activity_ok"] is False
    assert summary_json["training_completed"] is training_completed
    assert summary_json["training_admissible"] is training_completed
    assert summary_json["training_admissibility_basis"] == (
        "completed_training_and_breach_free_train_split"
    )
    assert summary_json["training_admissibility_scope"] == "single_seed_train_split"
    assert "survival_qualification_ok" not in summary_json
    assert summary_json["peak_dd_policy_fit"]["status"] == "MISS"
    assert summary_json["peak_dd_policy_fit"]["retraining_recommended"] is False
    assert summary_json["peak_eod_dd_policy_fit"]["status"] == "MISS"
    assert summary_json["peak_eod_dd_policy_fit"]["retraining_recommended"] is False
    train_payload = json.loads((tmp_path / "evaluations" / "train_in_sample.json").read_text())
    assert train_payload["training_admissible"] is training_completed
    assert train_payload["train_split_survival_ok"] is True
    assert train_payload["metrics"]["profit_factor"] is None
    assert train_payload["metrics"]["metric_availability"]["profit_factor"] == (
        "not_applicable_no_completed_positions"
    )
    assert (
        "| Train (in-sample) | -2.00% | -2000.00 USD | 5.00% | -0.500 | N/A | N/A | 0 |" in summary
    )
    assert f"Training complete: {'PASS' if training_completed else 'FAIL'}" in summary
    assert "Train-split survival: PASS" in summary
    assert f"Train-split admissible: {'PASS' if training_completed else 'FAIL'}" in summary
    assert "does not establish cross-seed and walk-forward qualification" in summary
    assert "does not affect train-split survival" in summary
    assert "Train activity diagnostic: INACTIVE (trades=0)" in summary


def test_evaluation_writer_rejects_truthy_malformed_survival_flags(tmp_path: Path) -> None:
    metrics = PerformanceMetrics(
        total_return_pct=0.0,
        total_pnl=0.0,
        max_drawdown=0.0,
        sharpe=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        n_trades=0,
    )
    result = {
        "survived_full_year": "false",
        "completed_data_split": "false",
        "n_breach_sessions": 0,
        "n_sessions": 10,
        "days_traded": 0,
        "equity": [],
    }
    write_evaluation_artifacts(
        run_dir=tmp_path,
        seed=7,
        completed_timesteps=10,
        train_result=result,
        test_result=result,
        train_metrics=metrics,
        test_metrics=metrics,
        train_gate={"ok": "false", "hard_risk_ok": True, "breached": False},
        train_activity_gate={"ok": "false", "status": "INACTIVE", "n_trades": 0},
        account_currency="USD",
        survival_objective=True,
        training_completed=True,
    )

    summary = json.loads((tmp_path / "evaluations" / "summary.json").read_text())
    assert summary["train_split_survival_ok"] is False
    assert summary["training_admissible"] is False
    assert summary["train_activity_ok"] is False


@pytest.mark.parametrize("breach_count", [False, "0", 0.0, -1, None])
def test_evaluation_writer_rejects_malformed_breach_counts(
    tmp_path: Path, breach_count: object
) -> None:
    metrics = PerformanceMetrics(
        total_return_pct=0.0,
        total_pnl=0.0,
        max_drawdown=0.0,
        sharpe=0.0,
        profit_factor=0.0,
        win_rate=0.0,
        n_trades=0,
    )
    result: dict[str, Any] = {
        "survived_full_year": True,
        "completed_data_split": True,
        "n_sessions": 10,
        "days_traded": 0,
        "equity": [],
    }
    if breach_count is not None:
        result["n_breach_sessions"] = breach_count
    write_evaluation_artifacts(
        run_dir=tmp_path,
        seed=7,
        completed_timesteps=10,
        train_result=result,
        test_result=result,
        train_metrics=metrics,
        test_metrics=metrics,
        train_gate={"ok": True, "hard_risk_ok": True, "breached": False},
        train_activity_gate={"ok": False, "status": "INACTIVE", "n_trades": 0},
        account_currency="USD",
        survival_objective=True,
        training_completed=True,
    )

    train_payload = json.loads((tmp_path / "evaluations" / "train_in_sample.json").read_text())
    assert train_payload["breach_events"] is None
    assert train_payload["train_split_survival_ok"] is False


def test_peak_dd_policy_miss_does_not_fail_completed_training_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import training.runner.reporting_runtime as reporting_runtime

    monkeypatch.setattr(reporting_runtime, "build_training_log", lambda **_kwargs: {})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text("effective: true\n")
    feature_cache = tmp_path / "features.parquet"
    Path(f"{feature_cache}.hash").write_text("feature-hash\n")
    result = {
        "seed": 50,
        "test_m": object(),
        "test_result": {},
        "train_gate": {
            "ok": False,
            "end_equity": 102_000.0,
            "slope": 0.0,
            "max_peak_trailing_dd": 0.101,
            "peak_trailing_dd_limit": 0.10,
            "breached": False,
            "reason": "peak_trailing_dd",
        },
        "train_activity_gate": assess_train_activity(2),
        "train_result": {
            "entry_state_diagnostics": {"entry_state_machine": True, "candidate_created": 2},
            "entry_diag": {},
        },
        "abort_reason": None,
        "model_num_timesteps": 2_007_040,
        "best_checkpoint_status": "ACTIVE",
        "best_checkpoint_n_trades": 2,
        "deterministic_viability_evaluations": [],
        "phase_timings_seconds": {},
        "run_manifest": "manifest.json",
    }
    cfg = SimpleNamespace(env={}, strategy={})
    args = SimpleNamespace(
        strategy="baseline",
        mvp=False,
        seed=50,
        algo="ppo",
        arch="tcn",
        reward="dsr",
        wandb=False,
        allow_locked_oos_for_selection=False,
    )

    training_log = finalize_training_run(
        cfg=cfg,
        args=args,
        is_multi_seed=False,
        seed_results=[result],
        timesteps=2_000_000,
        train_bar_count=100,
        test_bar_count=50,
        run_dir=run_dir,
        feat_cache=feature_cache,
        feature_columns=["close"],
        seeds=[50],
    )

    assert training_log["training_completed"] is True
    assert training_log["training_admissible"] is False
    assert training_log["overall_status"] == "COMPLETED_POLICY_MISS_RETRAIN_REQUIRED"
    assert training_log["policy_fit_miss_seeds"] == [50]
    assert training_log["hard_survival_failure_seeds"] == []
    assert training_log["hard_risk_ok_by_seed"] == {"50": True}
    assert training_log["retraining_recommended"] is True


def test_survival_qualification_precedes_profit_activity_and_policy_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import training.runner.reporting_runtime as reporting_runtime

    monkeypatch.setattr(reporting_runtime, "build_training_log", lambda **_kwargs: {})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text("effective: true\n")
    feature_cache = tmp_path / "features.parquet"
    Path(f"{feature_cache}.hash").write_text("feature-hash\n")
    result = {
        "seed": 42,
        "test_m": object(),
        "test_result": {},
        "train_gate": {
            "ok": "false",
            "end_equity": 98_000.0,
            "slope": -1.0,
            "reason": "peak_trailing_dd",
            "breached": False,
            "hard_risk_ok": True,
        },
        "train_activity_gate": {"ok": "false", "status": "INACTIVE", "n_trades": 0},
        "train_result": {
            "survived_full_year": True,
            "completed_data_split": True,
            "n_breach_sessions": 0,
            "entry_state_diagnostics": {},
            "entry_diag": {},
        },
        "abort_reason": None,
        "model_num_timesteps": 1_000,
        "best_checkpoint_status": "NO_ACTIVE_CHECKPOINT",
        "best_checkpoint_n_trades": 0,
        "deterministic_viability_evaluations": [],
        "phase_timings_seconds": {},
        "run_manifest": "manifest.json",
    }
    cfg = SimpleNamespace(env={"reward_mode": "survival"}, strategy={})
    args = SimpleNamespace(
        strategy="baseline",
        mvp=False,
        seed=42,
        algo="ppo",
        arch="tcn",
        reward="survival",
        wandb=False,
        allow_locked_oos_for_selection=False,
    )

    training_log = finalize_training_run(
        cfg=cfg,
        args=args,
        is_multi_seed=False,
        seed_results=[result],
        timesteps=1_000,
        train_bar_count=100,
        test_bar_count=50,
        run_dir=run_dir,
        feat_cache=feature_cache,
        feature_columns=["close"],
        seeds=[42],
    )

    assert training_log["train_split_survival_ok"] is True
    assert training_log["train_activity_ok"] is False
    assert training_log["train_activity_ok_by_seed"] == {"42": False}
    assert training_log["train_activity_status"] == "INACTIVE"
    assert training_log["inactive_seeds"] == [42]
    assert training_log["train_portfolio_fit_ok_by_seed"] == {"42": False}
    assert training_log["train_equity_ok"] is True
    assert training_log["training_completed"] is True
    assert training_log["training_admissible"] is True
    assert training_log["overall_status"] == "PASS_TRAIN_SPLIT_SURVIVAL"
    assert training_log["training_admissibility_scope"] == "all_configured_train_splits_only"
    assert training_log["qualification_gate_artifact"] == "survival_phase_gate.json"
    assert training_log["policy_fit_status"] == "MISS"
    assert training_log["retraining_recommended"] is False

    missing_run_dir = tmp_path / "missing-seed-run"
    missing_run_dir.mkdir()
    (missing_run_dir / "config.yaml").write_text("effective: true\n")
    missing_feature_cache = tmp_path / "missing-seed-features.parquet"
    Path(f"{missing_feature_cache}.hash").write_text("feature-hash\n")
    incomplete_log = finalize_training_run(
        cfg=cfg,
        args=args,
        is_multi_seed=False,
        seed_results=[result],
        timesteps=1_000,
        train_bar_count=100,
        test_bar_count=50,
        run_dir=missing_run_dir,
        feat_cache=missing_feature_cache,
        feature_columns=["close"],
        seeds=[42, 43],
    )
    assert incomplete_log["seed_results_cover_request"] is False
    assert incomplete_log["missing_seed_results"] == [43]
    assert incomplete_log["train_split_survival_ok"] is False
    assert incomplete_log["train_equity_ok"] is False
    assert incomplete_log["training_completed"] is False
    assert incomplete_log["training_admissible"] is False
    assert incomplete_log["overall_status"] == "INCOMPLETE"


def test_zero_train_trades_fail_closed_in_portfolio_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import training.runner.reporting_runtime as reporting_runtime

    monkeypatch.setattr(reporting_runtime, "build_training_log", lambda **_kwargs: {})
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "config.yaml").write_text("effective: true\n")
    feature_cache = tmp_path / "features.parquet"
    Path(f"{feature_cache}.hash").write_text("feature-hash\n")
    result = {
        "seed": 50,
        "test_m": object(),
        "test_result": {},
        "train_gate": {"ok": True, "end_equity": 100_000.0, "slope": 0.0, "reason": ""},
        "train_activity_gate": assess_train_activity(0),
        "train_result": {
            "entry_state_diagnostics": {"entry_state_machine": True, "candidate_created": 0},
            "entry_diag": {},
        },
        "abort_reason": None,
        "model_num_timesteps": 20_000_000,
        "best_checkpoint_status": "NO_ACTIVE_CHECKPOINT",
        "best_checkpoint_n_trades": 0,
        "deterministic_viability_evaluations": [
            {"timestep": 5_000_000, "deterministic_n_trades": 0}
        ],
        "phase_timings_seconds": {},
        "run_manifest": "manifest.json",
    }
    cfg = SimpleNamespace(env={}, strategy={})
    args = SimpleNamespace(
        strategy="baseline",
        mvp=False,
        seed=50,
        algo="ppo",
        arch="tcn",
        reward="dsr",
        wandb=False,
        allow_locked_oos_for_selection=False,
    )

    with pytest.raises(SystemExit, match="TRAIN_ACTIVITY_FAILED"):
        finalize_training_run(
            cfg=cfg,
            args=args,
            is_multi_seed=False,
            seed_results=[result],
            timesteps=20_000_000,
            train_bar_count=100,
            test_bar_count=50,
            run_dir=run_dir,
            feat_cache=feature_cache,
            feature_columns=["close"],
            seeds=[50],
        )

    training_log = json.loads((run_dir / "training_log.json").read_text())
    assert training_log["train_split_survival_ok"] is None
    assert training_log["train_activity_ok"] is False
    assert training_log["train_activity_status"] == "INACTIVE"
    assert training_log["overall_status"] == "FAIL_INACTIVE"
    assert training_log["training_admissible"] is False
    assert training_log["zero_trade_diagnosis"] == "FAIL_ENTRY_PATH"
    assert (
        training_log["deterministic_viability_evaluations_by_seed"]["50"]
        == result["deterministic_viability_evaluations"]
    )


def test_resuming_preserves_loaded_value_head_while_fresh_runs_zero_it() -> None:
    model = SimpleNamespace(policy=SimpleNamespace(value_net=torch.nn.Linear(2, 1)))
    with torch.no_grad():
        model.policy.value_net.weight.fill_(3.0)
        model.policy.value_net.bias.fill_(4.0)

    _initialize_value_head(model, resumed=True)
    assert torch.all(model.policy.value_net.weight == 3.0)
    assert torch.all(model.policy.value_net.bias == 4.0)

    _initialize_value_head(model, resumed=False)
    assert torch.all(model.policy.value_net.weight == 0.0)
    assert torch.all(model.policy.value_net.bias == 0.0)


class TestParseTrainArgs:
    """Tests for parse_train_args()."""

    def test_default_args(self) -> None:
        """Default args match the expected baseline config."""
        with patch("sys.argv", ["train_rl"]):
            args = parse_train_args()
        assert args.seed == 42
        assert args.algo == "ppo"
        # Leave the architecture unset so config/quality-variant resolution
        # can select it; train_rl falls back to tcn after config is loaded.
        assert args.arch is None
        assert args.reward == "dsr"
        assert args.strategy == "baseline"
        assert args.mvp is False
        assert args.force is False
        assert args.use_vae is False
        assert args.wandb is False
        assert args.walk_forward is False

    def test_custom_seed(self) -> None:
        with patch("sys.argv", ["train_rl", "--seed", "123"]):
            args = parse_train_args()
        assert args.seed == 123

    def test_mvp_flag(self) -> None:
        with patch("sys.argv", ["train_rl", "--mvp"]):
            args = parse_train_args()
        assert args.mvp is True

    def test_sac_algo(self) -> None:
        with patch("sys.argv", ["train_rl", "--algo", "sac"]):
            args = parse_train_args()
        assert args.algo == "sac"

    def test_variant_supplies_unset_algorithm_and_encoder_defaults(self) -> None:
        with patch("sys.argv", ["train_rl", "--variant", "sustainable_growth_sac_log"]):
            args = parse_train_args()
        assert args.algo == "sac"
        assert args.arch == "tcn"
        assert args.use_vae is False

    def test_mtf_reasoning_architecture(self) -> None:
        with patch("sys.argv", ["train_rl", "--arch", "mtf_reasoning"]):
            args = parse_train_args()
        assert args.arch == "mtf_reasoning"

    def test_sweep_reward(self) -> None:
        with patch("sys.argv", ["train_rl", "--reward", "sweep"]):
            args = parse_train_args()
        assert args.reward == "sweep"


class TestSetupRngs:
    """Tests for _setup_rngs()."""

    def test_numpy_seed_reproducible(self) -> None:
        """Same seed produces same random sequence."""
        _setup_rngs(42)
        a = np.random.random(5)
        _setup_rngs(42)
        b = np.random.random(5)
        np.testing.assert_array_equal(a, b)


class TestBuildTrainingLog:
    """Tests for build_training_log()."""

    def test_log_contains_required_keys(self) -> None:
        """Training log has all required fields."""
        test_m = type(
            "Metrics",
            (),
            {
                "sharpe": 1.5,
                "max_drawdown": 0.05,
                "n_trades": 10,
                "total_return_pct": 0.02,
            },
        )()
        test_result = {"n_breach_sessions": 0}
        log = build_training_log(
            seed=42,
            mvp=True,
            algo="ppo",
            arch="tcn",
            reward="dsr",
            timesteps=8192,
            train_bars=11700,
            test_bars=49925,
            test_m=test_m,
            test_result=test_result,
            environment_reward_mode="equity_log_growth",
            equity_log_growth_scale=25.0,
            action_schema={
                "version": "overlay-action-v2",
                "key": "6_dir",
                "width": 6,
                "coordinates": ["direction", "intensity", "stop", "risk", "target", "exit"],
            },
        )
        assert log["seed"] == 42
        assert log["mvp"] is True
        assert log["algo"] == "ppo"
        assert log["arch"] == "tcn"
        assert log["reward"] == "dsr"
        assert log["environment_reward_mode"] == "equity_log_growth"
        assert log["equity_log_growth_scale"] == 25.0
        assert log["timesteps"] == 8192
        assert log["train_bars"] == 11700
        assert log["test_bars"] == 49925
        assert log["test_sharpe"] == 1.5
        assert log["test_max_dd"] == 0.05
        assert log["test_trades"] == 10
        assert log["test_return"] == 0.02
        assert log["test_breaches"] == 0
        assert log["strategy"] == "baseline"
        assert log["strategy_actions"] is False
        assert log["action_schema"]["coordinates"][0] == "direction"
        assert "timestamp" in log

    def test_log_breaches_default_zero(self) -> None:
        """Missing n_breach_sessions defaults to 0."""
        test_m = type(
            "Metrics",
            (),
            {
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "n_trades": 0,
                "total_return_pct": 0.0,
            },
        )()
        log = build_training_log(
            seed=0,
            mvp=False,
            algo="sac",
            arch="gru",
            reward="sweep",
            timesteps=1000,
            train_bars=100,
            test_bars=200,
            test_m=test_m,
            test_result={},  # no n_breach_sessions
        )
        assert log["test_breaches"] == 0

    def test_entry_funnels_keep_training_and_test_diagnostics_separate(self) -> None:
        test_m = type(
            "Metrics",
            (),
            {"sharpe": 0.0, "max_drawdown": 0.0, "n_trades": 0, "total_return_pct": 0.0},
        )()
        log = build_training_log(
            seed=50,
            mvp=False,
            algo="ppo",
            arch="tcn",
            reward="dsr",
            timesteps=20_000_000,
            train_bars=100,
            test_bars=50,
            test_m=test_m,
            train_result={
                "entry_diag": {"opened": 3, "rejected_gate": 7},
                "entry_state_diagnostics": {"candidate_created": 11, "entered": 3},
            },
            test_result={
                "entry_diag": {"opened": 5, "rejected_gate": 13},
                "entry_state_diagnostics": {"candidate_created": 22, "entered": 5},
            },
        )

        funnels = log["entry_funnel_by_split"]
        assert funnels["train"]["entry_opened"] == 3
        assert funnels["train"]["candidate_created"] == 11
        assert funnels["test"]["entry_opened"] == 5
        assert funnels["test"]["candidate_created"] == 22
        assert "entry_opened" not in log


class TestLoadMergedConfig:
    """Tests for load_merged_config() override ordering (SL Phase 0.1)."""

    def test_overrides_win_over_strategy_overlay(self) -> None:
        """CLI overrides apply after the Idea 1 variant merge.

        ``config/2_po3_ifvg.yaml`` pins ``env.reward_mode: pnl``; an
        explicit ``env.reward_mode=rr`` override must survive the merge
        instead of being silently reverted to pnl.
        """
        import argparse

        ns = argparse.Namespace(config=None, strategy="po3_ifvg", overrides=["env.reward_mode=rr"])
        cfg = load_merged_config(ns)
        assert str(cfg.env.reward_mode) == "rr"

    def test_baseline_leaves_overrides_intact(self) -> None:
        import argparse

        ns = argparse.Namespace(config=None, strategy="baseline", overrides=["env.reward_mode=rr"])
        cfg = load_merged_config(ns)
        assert str(cfg.env.reward_mode) == "rr"

    def test_variant_strategy_overrides_cli_strategy_without_double_merge(self) -> None:
        import argparse

        ns = argparse.Namespace(
            config=None,
            strategy="distribution",
            variant="ladder_a4b_po3_ifvg",
            quality_variant=None,
            overrides=[],
        )
        cfg = load_merged_config(ns)

        assert str(cfg.strategy.name) == "po3_ifvg"
        assert str(cfg.strategy.variant_id) == "po3_confirmed_ifvg_htf_mtf_v1"

    def test_variant_applies_reward_and_declared_config_overrides(self) -> None:
        import argparse

        ns = argparse.Namespace(
            config=None,
            strategy="baseline",
            variant="ladder_a4a_dollar_band_q5_on",
            quality_variant=None,
            vae_path=None,
            overrides=[],
        )
        cfg = load_merged_config(ns)

        assert str(cfg.env.reward_mode) == "dsr"
        assert bool(cfg.constrained_rl.enabled) is True
        assert float(cfg.constrained_rl.episode_cost_budget) == 0.1
        assert str(cfg.env.risk_mode) == "dollar_band"


class TestCostModel:
    """Tests for cost_model() YAML wiring (SL Phase 0.5)."""

    def test_cost_model_matches_default_yaml(self) -> None:
        from configuration import load_config

        cfg = load_config([])
        model = cost_model(cfg)
        assert model.slippage_points == float(cfg.costs.slippage_points) == 5.0
        assert model.spread_points == float(cfg.costs.spread_us100)
        assert float(cfg.risk.min_sl_points) == 0.0
        assert float(cfg.risk.min_sl_atr_mult) > 0.0
