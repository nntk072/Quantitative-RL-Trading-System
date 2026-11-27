"""Training runner admission and walk-forward resume honor saved run evidence."""

from __future__ import annotations

import json
from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

from training.runner import baselines, training, walk_forward_validation


def test_completed_campaign_seed_requires_its_checkpoint_and_gate_artifacts(
    tmp_path: Path,
) -> None:
    seed_dir = tmp_path / "seed42"
    model_dir = seed_dir / "model"
    model_dir.mkdir(parents=True)
    checkpoint = model_dir / "ppo_latest.zip"
    checkpoint.write_bytes(b"checkpoint payload")
    manifest = {
        "artifact_paths": {"checkpoint": "model/ppo_latest.zip"},
        "checkpoint": {"sha256": cast(Any, training).file_sha256(checkpoint)},
    }
    (seed_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (seed_dir / "train_equity_gate.json").write_text('{"status":"pass"}', encoding="utf-8")
    (seed_dir / "train_path_outcome.json").write_text('{"status":"complete"}', encoding="utf-8")

    training._verify_completed_campaign_seed(seed_dir)

    checkpoint.write_bytes(b"changed checkpoint")
    with pytest.raises(ValueError, match="checkpoint is missing or changed"):
        training._verify_completed_campaign_seed(seed_dir)


def test_walk_forward_resume_skips_already_receipted_folds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "seed-run"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text('{"source":{"identity":"same"}}', encoding="utf-8")
    splits = [
        SimpleNamespace(fold=1, train_idx=np.array([0, 1]), test_idx=np.array([4, 5])),
        SimpleNamespace(fold=2, train_idx=np.array([0, 2]), test_idx=np.array([6, 7])),
    ]
    identity = {"seed": 42, "fingerprint": "saved"}

    def split_digest(train_idx: np.ndarray[Any, Any], test_idx: np.ndarray[Any, Any]) -> str:
        return f"{train_idx.tolist()}:{test_idx.tolist()}"

    def fold_digest(saved_identity: dict[str, object], fold: int, digest: str) -> str:
        return f"{saved_identity['fingerprint']}:{fold}:{digest}"

    receipts = {
        split.fold: {
            "fold": split.fold,
            "split_sha256": split_digest(split.train_idx, split.test_idx),
            "fold_identity_sha256": fold_digest(
                identity, split.fold, split_digest(split.train_idx, split.test_idx)
            ),
            "sharpe": 0.25,
        }
        for split in splits
    }
    monkeypatch.setattr(walk_forward_validation, "source_state", lambda _root: {"identity": "same"})
    monkeypatch.setattr(
        walk_forward_validation, "final_evaluation_deterministic", lambda _cfg: True
    )
    monkeypatch.setattr(
        walk_forward_validation, "build_walk_forward_identity", lambda **_kwargs: identity
    )
    monkeypatch.setattr(
        walk_forward_validation, "purged_walk_forward", lambda *_args, **_kwargs: splits
    )
    monkeypatch.setattr(walk_forward_validation, "fold_split_sha256", split_digest)
    monkeypatch.setattr(walk_forward_validation, "fold_identity_sha256", fold_digest)
    monkeypatch.setattr(
        walk_forward_validation,
        "load_walk_forward_progress",
        lambda *_args, **_kwargs: receipts,
    )

    def progress(**kwargs: object) -> dict[str, object]:
        folds = kwargs["folds"]
        assert isinstance(folds, dict)
        expected_fold_ids = cast(Sequence[object], kwargs["expected_fold_ids"])
        return {
            "status": "complete",
            "splits": len(expected_fold_ids),
            "folds": [folds[key] for key in sorted(folds)],
            "mean_sharpe": 0.25,
            "std_sharpe": 0.0,
        }

    monkeypatch.setattr(walk_forward_validation, "build_walk_forward_progress", progress)
    monkeypatch.setattr(
        walk_forward_validation,
        "build_walkforward_fold_features",
        lambda *_args, **_kwargs: pytest.fail("completed folds must not rebuild features"),
    )

    walk_forward_validation.run_walk_forward_validation(
        args=Namespace(
            walk_forward=True,
            wf_splits=2,
            wf_steps=10,
            purge_bars=0,
            embargo_bars=0,
            algo="ppo",
            reward="dsr",
            use_vae=False,
            arch="mlp",
        ),
        timesteps=10,
        train_bars=pd.DataFrame({"close": range(8)}),
        train_sec=None,
        cfg=SimpleNamespace(),
        cache_dir=tmp_path / "cache",
        primary_sym="ES",
        primary_ticks=None,
        schedule_path=tmp_path / "schedule.csv",
        feature_columns=[],
        run_dir=run_dir,
        env_vae=None,
        pre_ny_by_date=None,
        device="cpu",
        vae_model=None,
        seed=42,
    )

    summary = json.loads((run_dir / "walk_forward.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    assert [fold["fold"] for fold in summary["folds"]] == [1, 2]
    assert not list(run_dir.glob("obs_features_fold*.npy"))


def test_baseline_development_only_runs_and_saves_training_split_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    index = pd.DatetimeIndex(["2025-12-31 14:30:00Z", "2026-01-01 14:30:00Z"])
    source_bars = pd.DataFrame({"close": [100.0, 900_000.0]}, index=index)
    train_bars = source_bars.iloc[:1]
    test_bars = source_bars.iloc[0:0]
    train_features = pd.DataFrame({"signal": [1.0]}, index=train_bars.index)
    test_features = train_features.iloc[0:0]
    cfg = OmegaConf.create(
        {
            "evaluation": {"development_only": True},
            "trading_policy": {"daily_loss_reset_source": "session"},
            "data": {
                "primary": "US100",
                "secondary": "US500",
                "cache_dir": str(tmp_path / "cache"),
                "tz": "UTC",
                "timestamp_clock": "native",
            },
            "env": {"obs_window": 1, "eod_risk": {}},
            "account": {"initial_balance": 100_000, "contract_size": 1.0},
            "backtest": {"validation": {"max_loss_per_trade_usd": 500}},
            "risk": {
                "default_risk_frac": 0.01,
                "rr_ratio_default": 2.0,
                "swing_buffer_pts": 1.0,
                "sl_mode": "fixed",
                "min_lot": 0.01,
                "max_lot": 10.0,
                "lot_step": 0.01,
            },
            "costs": {"use_tick_execution": False},
            "execution": {},
            "session": {"tz": "UTC"},
        }
    )
    observed: dict[str, Any] = {"backtests": [], "features": []}
    monkeypatch.setattr(
        cast(Any, baselines).sys,
        "argv",
        ["baselines", "--strategy", "ema", "--out", str(tmp_path)],
    )
    monkeypatch.setattr(baselines, "load_config", lambda _overrides: cfg)
    monkeypatch.setattr(
        baselines,
        "resolve_trading_policy",
        lambda _cfg: SimpleNamespace(daily_pnl_basis="session"),
    )
    monkeypatch.setattr(baselines, "get_split_config", lambda _cfg: ("2025-12-31", "2026-01-01"))
    monkeypatch.setattr(baselines, "get_train_start_config", lambda _cfg: None)
    monkeypatch.setattr(
        baselines,
        "run_pipeline",
        lambda _cfg, **kwargs: (
            observed.update({"pipeline": kwargs}) or {"US100": {"M1": source_bars.copy()}}
        ),
    )
    monkeypatch.setattr(
        baselines,
        "split_bars",
        lambda frame, **_kwargs: (frame.iloc[:1], frame.iloc[1:]),
    )

    def build_features(bars: pd.DataFrame, **_kwargs: Any) -> pd.DataFrame:
        observed["features"].append(bars.copy())
        return train_features

    monkeypatch.setattr(baselines, "build_split_scoped_features", build_features)
    monkeypatch.setattr(
        baselines,
        "split_train_test",
        lambda *_args: (train_bars, test_bars, train_features, test_features),
    )
    monkeypatch.setattr(
        baselines,
        "build_tick_books",
        lambda _cfg, **kwargs: observed.update({"ticks": kwargs}) or {},
    )
    monkeypatch.setattr(
        baselines,
        "ema_crossover",
        lambda bars, **_kwargs: (
            observed.update({"ema_bars": bars.copy()}) or pd.Series([1], index=bars.index)
        ),
    )
    monkeypatch.setattr(baselines, "cost_model", lambda _cfg: object())
    monkeypatch.setattr(baselines, "eval_guardrail_kwargs", lambda _cfg: {})
    monkeypatch.setattr(
        baselines,
        "run_backtest",
        lambda **kwargs: (
            observed["backtests"].append(kwargs) or {"equity": [100_000.0, 101_000.0], "trades": []}
        ),
    )
    monkeypatch.setattr(
        baselines,
        "calculate_metrics",
        lambda *_args, **_kwargs: SimpleNamespace(
            sharpe=0.5, max_drawdown=0.01, n_trades=1, total_return_pct=1.0
        ),
    )
    monkeypatch.setattr(baselines, "account_path_metric_inputs", lambda _result: {})
    monkeypatch.setattr(
        baselines, "save_run", lambda **kwargs: observed.update({"saved": kwargs}) or tmp_path
    )

    baselines.main()

    assert observed["pipeline"]["end_inclusive"] == "2025-12-31"
    assert observed["features"][0]["close"].tolist() == [100.0]
    assert observed["ema_bars"]["close"].tolist() == [100.0]
    assert len(observed["backtests"]) == 1
    backtest = observed["backtests"][0]
    assert backtest["bars"].equals(train_bars)
    assert backtest["features"].equals(train_features)
    assert backtest["policy"](np.zeros((1, 1))) == 0
    saved = observed["saved"]
    assert saved["train_result"]["initial_balance"] == 100_000
    assert saved["test_result"] is None
    assert saved["test_metrics"] is None
    assert saved["test_bars"].empty
