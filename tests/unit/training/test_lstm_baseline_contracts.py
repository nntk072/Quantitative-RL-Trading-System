"""Fast orchestration contracts for the supervised LSTM baseline CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
import torch
from omegaconf import OmegaConf

from training.runner import lstm_baseline


def test_parse_args_exposes_training_and_chronological_split_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lstm-baseline",
            "--bars-csv",
            "bars.csv",
            "--features-csv",
            "features.csv",
            "--train-start",
            "2025-01-01",
            "--train-end",
            "2025-12-31",
            "--test-start",
            "2026-01-01",
            "--epochs",
            "2",
        ],
    )

    args = lstm_baseline.parse_args()

    assert args.bars_csv == "bars.csv"
    assert args.features_csv == "features.csv"
    assert args.train_start == "2025-01-01"
    assert args.train_end == "2025-12-31"
    assert args.test_start == "2026-01-01"
    assert args.epochs == 2
    assert args.window == 60


def test_load_csv_normalizes_non_datetime_index(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame({"close": [1.0]}, index=["2026-01-02"])
    read_csv = Mock(return_value=frame)
    monkeypatch.setattr(cast(Any, lstm_baseline).pd, "read_csv", read_csv)

    result = lstm_baseline._load_csv("bars.csv", "timestamp")

    read_csv.assert_called_once_with("bars.csv", index_col="timestamp", parse_dates=True)
    assert isinstance(result.index, pd.DatetimeIndex)


def test_load_csv_preserves_datetime_index(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pd.DatetimeIndex(["2026-01-02"])
    frame = pd.DataFrame({"close": [1.0]}, index=index)
    monkeypatch.setattr(cast(Any, lstm_baseline).pd, "read_csv", lambda *_args, **_kwargs: frame)

    result = lstm_baseline._load_csv("bars.csv", None)

    assert result.index is index


def _args(out: Path, *, features_csv: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        seed=42,
        bars_csv="bars.csv",
        features_csv=features_csv,
        config="config.yaml",
        train_start=None,
        train_end="2025-12-31",
        test_start="2026-01-01",
        window=2,
        horizon=1,
        hidden_size=2,
        epochs=1,
        batch_size=2,
        lr=0.001,
        obs_window=2,
        out=str(out),
    )


def _install_minimal_training_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    args: SimpleNamespace,
    split: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    dates = pd.date_range("2025-01-01", periods=4)
    bars = pd.DataFrame(
        {"close": [100.0, 101.0, 102.0, 103.0]},
        index=dates,
    )
    features = pd.DataFrame({"feature": [0.0, 1.0, 2.0, 3.0]}, index=dates)
    events: list[str] = []
    train = (bars.iloc[:3], bars.iloc[3:], features.iloc[:3], features.iloc[3:])
    monkeypatch.setattr(lstm_baseline, "parse_args", lambda: args)
    monkeypatch.setattr(lstm_baseline, "get_device", lambda: torch.device("cpu"))
    monkeypatch.setattr(lstm_baseline, "_load_csv", lambda *_args: bars)
    monkeypatch.setattr(
        cast(Any, lstm_baseline).OmegaConf, "load", lambda _path: OmegaConf.create({})
    )
    monkeypatch.setattr(cast(Any, lstm_baseline).OmegaConf, "select", lambda *_args: None)
    monkeypatch.setattr(
        lstm_baseline,
        "build_split_scoped_features",
        lambda *_args, **_kwargs: features,
    )
    monkeypatch.setattr(
        lstm_baseline,
        "validate_feature_csv_against_canonical",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        lstm_baseline,
        "split_train_test",
        lambda *_args: split if split is not None else train,
    )

    def build_dataset(
        received_bars: pd.DataFrame, *_args: Any, **_kwargs: Any
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        events.append("train_dataset" if received_bars is train[0] else "report_dataset")
        if received_bars is train[0]:
            return np.ones((2, 2, 1), dtype=np.float32), np.array([1, 0], dtype=np.int64)
        return np.ones((1, 2, 1), dtype=np.float32), np.array([1], dtype=np.int64)

    monkeypatch.setattr(lstm_baseline, "build_sweep_dataset", build_dataset)

    def run_episode(_env: Any, action_fn: Any) -> dict[str, int]:
        events.append("episode")
        result = action_fn(None)
        return result if result else {"n_trades": 0}

    monkeypatch.setattr(lstm_baseline, "run_episode", run_episode)
    monkeypatch.setattr(
        lstm_baseline, "build_run_report", lambda _metrics, _trades: {"n_trades": 0}
    )
    monkeypatch.setattr(
        lstm_baseline,
        "TradingEnv",
        lambda **kwargs: SimpleNamespace(trade_log=[], step_idx=2, **kwargs),
    )
    monkeypatch.setattr(
        lstm_baseline,
        "LSTMStrategy",
        lambda *_args, **_kwargs: SimpleNamespace(act_at=lambda _idx: 0.0),
    )
    return bars, features, events


def test_main_runs_fixed_schedule_before_report_and_writes_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _args(tmp_path / "reports" / "sweep.pt")
    bars, features, events = _install_minimal_training_inputs(monkeypatch, args=args)
    adam = torch.optim.Adam

    def tracked_adam(parameters: Any, *, lr: float) -> Any:
        optimizer = adam(parameters, lr=lr)
        original_step = optimizer.step

        def step() -> None:
            events.append("optimizer_step")
            original_step()

        cast(Any, optimizer).step = step
        return optimizer

    monkeypatch.setattr(cast(Any, lstm_baseline).torch.optim, "Adam", tracked_adam)

    lstm_baseline.main()

    checkpoint = tmp_path / "reports" / "sweep.pt"
    metrics_path = tmp_path / "reports" / "sweep_metrics.json"
    assert checkpoint.is_file()
    report = json.loads(metrics_path.read_text())
    assert report["run_name"] == "lstm_sweep_baseline"
    assert report["evaluation_role"] == "exposed_report_only"
    assert report["split"]["train_bars"] == 3
    assert report["split"]["test_bars"] == 1
    assert report["exposed_report_only"] == {"n_trades": 0}
    assert events.index("report_dataset") > events.index("train_dataset")
    assert events.index("optimizer_step") < events.index("report_dataset")
    assert events[-1] == "episode"
    assert len(bars) == len(features)
    output = capsys.readouterr().out
    assert "exposed_report_only sweep samples: 1" in output
    assert "saved model to" in output


def test_main_rejects_invalid_supplied_feature_csv_before_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _args(tmp_path / "unused.pt", features_csv="provided.csv")
    _bars, _features, _events = _install_minimal_training_inputs(monkeypatch, args=args)
    monkeypatch.setattr(
        lstm_baseline,
        "validate_feature_csv_against_canonical",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("column mismatch")),
    )
    split = Mock(side_effect=AssertionError("split must not follow invalid feature input"))
    monkeypatch.setattr(lstm_baseline, "split_train_test", split)

    with pytest.raises(SystemExit, match="invalid --features-csv: column mismatch"):
        lstm_baseline.main()

    split.assert_not_called()


def test_main_rejects_empty_chronological_split_before_model_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _args(tmp_path / "unused.pt")
    empty = pd.DataFrame()
    _install_minimal_training_inputs(
        monkeypatch,
        args=args,
        split=(empty, empty, empty, empty),
    )
    monkeypatch.setattr(
        lstm_baseline,
        "LSTMSweepClassifier",
        lambda *_args, **_kwargs: pytest.fail("empty splits must stop before model construction"),
    )

    with pytest.raises(SystemExit, match="empty split"):
        lstm_baseline.main()


def test_module_entrypoint_requires_bars_argument(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import runpy

    monkeypatch.setattr(sys, "argv", ["training.runner.lstm_baseline"])
    with pytest.raises(SystemExit) as error:
        runpy.run_module("training.runner.lstm_baseline", run_name="__main__")
    assert error.value.code == 2
    assert "--bars-csv" in capsys.readouterr().err
