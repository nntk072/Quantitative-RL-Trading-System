"""Train-only checkpoint reanalysis orchestration contracts."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from evaluation.reanalysis import checkpoint_reanalysis
from evaluation.reporting import evaluation_manifest


@dataclass(frozen=True)
class _Metrics:
    sharpe: float = 1.25
    max_drawdown: float = 0.1
    n_trades: int = 2
    total_return_pct: float = 3.5


@pytest.mark.parametrize(
    ("train_only_screen", "stochastic", "seed", "use_current_stop_menu"),
    [
        (True, False, None, False),
        (False, False, None, False),
        (True, True, 42, True),
    ],
)
def test_main_reanalysis_writes_the_requested_split_scope_and_artifacts(
    tmp_path: Path,
    monkeypatch: Any,
    train_only_screen: bool,
    stochastic: bool,
    seed: int | None,
    use_current_stop_menu: bool,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    checkpoint = source / "model.zip"
    checkpoint.write_bytes(b"checkpoint-fixture")
    (source / "config.yaml").write_text("fixture: true\n", encoding="utf-8")
    (source / "run_manifest.json").write_text(
        json.dumps(
            {
                "feature_cache": {"identity": "feature-cache-fixture"},
                "datasets": {"primary_ticks": {"sha256": "source-ticks"}},
                "training_protocol": {"algorithm": "ppo", "seed": 17},
            }
        ),
        encoding="utf-8",
    )
    (source / "training_log.json").write_text(
        json.dumps({"source_training_seed": 17}), encoding="utf-8"
    )
    output = tmp_path / "screen"
    args = SimpleNamespace(
        allow_historical=True,
        allow_legacy_action_schema=False,
        allow_legacy_data_provenance=False,
        allow_legacy_observation_schema=False,
        allow_legacy_sequence_schema=False,
        allow_legacy_stop_schema=False,
        checkpoint=None,
        disable_peak_eod_dd_policy=False,
        export_replay_ledger=False,
        legacy_action_layout=None,
        max_charts=None,
        output=str(output),
        run=str(source),
        save_html=None,
        seed=seed,
        source_feature_cache=False,
        stochastic=stochastic,
        tick_fill_slippage_points=0.0,
        train_only_feature_snapshot=None,
        train_only_screen=train_only_screen,
        use_current_stop_menu=use_current_stop_menu,
        use_recorded_sequence_schema=False,
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_reanalysis_parser",
        lambda: SimpleNamespace(parse_args=lambda: args),
    )
    cfg = OmegaConf.create(
        {
            "risk": {"target_timeframes": ["M5"]},
            "output": {"save_html": False, "max_order_charts": 0},
            "env": {
                "observation_schema_version": "account-state-v1",
                "entry_state_machine": False,
                "entry_state_observation": True,
                "trade_setup_actions": False,
                "candidate_geometry_actions": False,
                "strategy_actions": False,
                "feature_validity_channels": False,
            },
            "account": {"initial_balance": 100_000.0},
            "evaluation": {},
        }
    )
    monkeypatch.setattr(checkpoint_reanalysis, "_load_run_config", lambda _run: cfg)
    current_stop_menu = ["M15", "H1"]
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "load_config",
        lambda: SimpleNamespace(risk=SimpleNamespace(target_timeframes=current_stop_menu)),
    )
    seeded_values: list[int] = []
    monkeypatch.setattr(random, "seed", seeded_values.append)
    monkeypatch.setattr(np.random, "seed", seeded_values.append)
    monkeypatch.setattr(checkpoint_reanalysis, "seed_sb3", seeded_values.append)
    monkeypatch.setattr(checkpoint_reanalysis, "resolve_checkpoint", lambda *_args: checkpoint)
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "validate_checkpoint_manifest_hash",
        lambda *_args: "hash_verified",
    )
    model = SimpleNamespace()
    monkeypatch.setattr(checkpoint_reanalysis, "load_checkpoint", lambda *_args, **_kwargs: model)
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_stop_candidate_schema",
        lambda _cfg: {"stop_menu_timeframes": ["M5"]},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis, "validate_stop_candidate_schema", lambda **_kwargs: "matched"
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "resolve_trading_policy",
        lambda _cfg: SimpleNamespace(
            repeated_payout=False, to_dict=lambda: {"policy": "fixture-policy"}
        ),
    )
    observation_schema = SimpleNamespace(
        version="fixture-observation-v1", to_dict=lambda: {"version": "fixture-observation-v1"}
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_observation_schema",
        lambda *_args, **_kwargs: observation_schema,
    )
    for name in (
        "validate_sb3_observation_schema",
        "validate_model_trade_setup_observation_schema",
        "validate_model_candidate_geometry_observation_schema",
    ):
        monkeypatch.setattr(checkpoint_reanalysis, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(checkpoint_reanalysis, "is_sb3_box_model", lambda _model: False)
    monkeypatch.setattr(checkpoint_reanalysis, "is_sb3_discrete_model", lambda _model: False)

    train_index = pd.date_range("2025-01-02", periods=2, freq="min", tz="UTC")
    test_index = pd.date_range("2025-02-02", periods=1, freq="min", tz="UTC")
    train_bars = pd.DataFrame({"close": [100.0, 101.0]}, index=train_index)
    test_bars = pd.DataFrame({"close": [200.0]}, index=test_index)
    train_features = pd.DataFrame({"atr": [1.0, 1.1]}, index=train_index)
    test_features = pd.DataFrame({"atr": [2.0]}, index=test_index)
    feature_cache = tmp_path / "cache" / "features.parquet"
    datasets = SimpleNamespace(
        primary_ticks=object(),
        features=pd.concat([train_features, test_features]),
        train_bars=train_bars,
        test_bars=test_bars,
        train_features=train_features,
        test_features=test_features,
        train_secondary=None,
        test_secondary=None,
        train_end="2025-01-02",
        test_start="2025-02-02",
        feature_cache=feature_cache,
        feature_cache_disposition="verified_source_cache",
        evaluated_feature_cache_hash="cache-content-hash",
        evaluated_feature_cache_file_sha256="cache-file-hash",
        source_cache_replay_path=None,
        dataset_records={"train_features": {"sha256": "train-feature-identity"}},
        dataset_parity_disposition="matched",
        training_data_source="source_feature_cache",
        backend_parity_disposition="not_required",
        train_feature_snapshot_path=None,
    )
    monkeypatch.setattr(
        checkpoint_reanalysis, "reconstruct_reanalysis_datasets", lambda **_kwargs: datasets
    )
    monkeypatch.setattr(
        checkpoint_reanalysis, "ticks_covering", lambda _ticks, bars: f"ticks:{len(bars)}"
    )
    eval_common = {
        "eod_risk": {"peak_trailing_dd_limit_usd": 900.0},
        "tick_execution_required": False,
        "randomized_fill_latency_ms": 0,
        "cost_model": SimpleNamespace(slippage_points=0.25),
        "guardrail_kwargs": {"daily_loss_limit": 500.0, "max_loss_limit": 1_000.0},
    }
    strategy = SimpleNamespace(raw_columns=())
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_eval_common",
        lambda *_args, **_kwargs: (eval_common, strategy, None, None, None),
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "select_obs_columns",
        lambda *_args: SimpleNamespace(columns=["atr"]),
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_sequence_feature_schema",
        lambda columns, **_kwargs: {"columns": list(columns), "width": len(columns)},
    )
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "validate_sequence_feature_schema",
        lambda *_args, **_kwargs: "matched",
    )
    monkeypatch.setattr(checkpoint_reanalysis, "validate_sequence_input_width", lambda *_args: None)
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "SB3DecisionProvider",
        lambda *_args, **_kwargs: SimpleNamespace(metadata={}, predict=lambda *_args: None),
    )

    evaluations: list[dict[str, Any]] = []
    split_evaluations: list[dict[str, Any]] = []

    def evaluate_train(_provider: Any, **kwargs: Any) -> tuple[dict[str, Any], _Metrics]:
        evaluations.append(kwargs)
        return (
            {
                "equity": pd.Series([100_000.0, 103_500.0], index=train_index),
                "trades": pd.DataFrame([{"pnl": 3_500.0}, {"pnl": 0.0}]),
                "survived_full_year": True,
                "completed_data_split": True,
                "episode_end_reason": "data_end",
            },
            _Metrics(),
        )

    monkeypatch.setattr(checkpoint_reanalysis, "evaluate_train_split", evaluate_train)

    def evaluate_split(_provider: Any, **kwargs: Any) -> dict[str, Any]:
        split_evaluations.append(kwargs)
        split_bars = kwargs["bars"]
        return {
            "equity": pd.Series(
                [100_000.0 + 250.0 * offset for offset in range(len(split_bars))],
                index=split_bars.index,
            ),
            "trades": pd.DataFrame([{"pnl": 250.0}]),
            "n_breach_sessions": 0,
            "survived_full_year": True,
            "completed_data_split": True,
            "episode_end_reason": "data_end",
        }

    monkeypatch.setattr(checkpoint_reanalysis, "evaluate_checkpoint_split", evaluate_split)
    monkeypatch.setattr(
        checkpoint_reanalysis, "calculate_metrics", lambda *_args, **_kwargs: _Metrics()
    )
    monkeypatch.setattr(checkpoint_reanalysis, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "_evaluation_dataset_records",
        lambda **kwargs: {
            "train_bars": {"count": len(kwargs["train_bars"])},
            "train_features": {"count": len(kwargs["train_features"])},
            "train_secondary": None,
            "primary_ticks": {"partition": "training"},
            "test_bars": {"count": len(kwargs["test_bars"])},
            "test_features": {"count": len(kwargs["test_features"])},
        },
    )
    monkeypatch.setattr(checkpoint_reanalysis, "evaluation_periods_per_year", lambda _cfg: 252)
    monkeypatch.setattr(
        checkpoint_reanalysis,
        "build_evaluation_provenance",
        lambda _root: {"source_revision": "fixture-revision"},
    )

    save_calls: list[dict[str, Any]] = []

    def save_run(**kwargs: Any) -> None:
        save_calls.append(kwargs)
        OmegaConf.save(config=kwargs["cfg"], f=str(kwargs["run_dir"] / "config.yaml"))

    monkeypatch.setattr(checkpoint_reanalysis, "save_run", save_run)
    manifest_lineage: list[dict[str, Any]] = []
    monkeypatch.setattr(
        evaluation_manifest,
        "write_evaluation_manifest",
        lambda _output, *, lineage: manifest_lineage.append(lineage),
    )

    checkpoint_reanalysis.main()

    assert len(evaluations) == 1
    assert evaluations[0]["bars"] is train_bars
    assert evaluations[0]["features"] is train_features
    assert evaluations[0]["tickbook"] == "ticks:2"
    assert evaluations[0]["stochastic"] is stochastic
    assert seeded_values == ([42, 42, 42] * (1 if train_only_screen else 2) if seed else [])
    if use_current_stop_menu:
        assert list(cfg.risk.target_timeframes) == current_stop_menu
    if train_only_screen:
        report = json.loads((output / "train_only_screen.json").read_text(encoding="utf-8"))
        assert split_evaluations == []
        assert save_calls == []
        assert report["artifact_role"] == (
            "changed_policy_train_only_diagnostic"
            if use_current_stop_menu
            else "candidate_screen_train_only"
        )
        assert report["policy_comparison_disposition"] == (
            "current_8_timeframe_stop_menu_changed_policy_diagnostic"
            if use_current_stop_menu
            else "source_stop_menu_compatibility_replay"
        )
        assert report["test_split_evaluated"] is False
        assert report["training_split"]["bar_count"] == 2
        assert report["training_split"]["trade_count"] == 2
        assert report["training_input_identity"] == {
            "train_bars": {"count": 2},
            "train_features": {"count": 2},
            "train_secondary": None,
            "primary_ticks": {"partition": "training"},
        }
        assert report["checkpoint_sha256"]
        assert report["feature_cache"]["content_hash"] == "cache-content-hash"
        assert report["evaluation_protocol"]["sequence_feature_schema"] == {
            "columns": ["atr", "reachable_r"],
            "width": 2,
        }
        assert report["evaluation_provenance"] == {"source_revision": "fixture-revision"}
        assert not (output / "reanalysis_manifest.json").exists()
    else:
        assert len(split_evaluations) == 1
        assert split_evaluations[0]["bars"] is test_bars
        assert split_evaluations[0]["features"] is test_features
        assert split_evaluations[0]["tickbook"] == "ticks:1"
        assert len(save_calls) == 1
        assert save_calls[0]["train_bars"] is train_bars
        assert save_calls[0]["test_bars"] is test_bars
        assert save_calls[0]["max_order_charts"] == 0
        training_log = json.loads((output / "training_log.json").read_text(encoding="utf-8"))
        assert training_log["source_training_seed"] == 17
        assert training_log["test_trades"] == 2
        assert training_log["eval_checkpoint"] == checkpoint.name
        manifest = json.loads((output / "reanalysis_manifest.json").read_text(encoding="utf-8"))
        assert manifest["artifact_role"] == "historical_reanalysis"
        assert manifest["historical_holdout_inspected"] is True
        assert manifest["evaluation_provenance"] == {"source_revision": "fixture-revision"}
        assert manifest["source_datasets"] == {"primary_ticks": {"sha256": "source-ticks"}}
        assert manifest["trading_policy"] == {"policy": "fixture-policy"}
        assert manifest["execution_cost_override"]["configured_cost_model_slippage_points"] == 0.25
        assert manifest["evaluation_risk_overrides"]["daily_loss_limit_usd"] == 500.0
        assert (output / "config.yaml").is_file()
        assert manifest_lineage == [
            {
                "source_run": str(source.resolve()),
                "source_run_manifest_sha256": checkpoint_reanalysis.__dict__["file_sha256"](
                    source / "run_manifest.json"
                ),
                "checkpoint_sha256": checkpoint_reanalysis.__dict__["file_sha256"](checkpoint),
                "dataset_parity_disposition": "matched",
                "historical_holdout_inspected": True,
            }
        ]
