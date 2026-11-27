from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from simulation.backtest.cross_validation import run as cross_validation


def test_cross_validation_load_data_requires_a_present_nonempty_ohlcv_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from simulation.backtest.cross_validation.utils import data_loader

    path = tmp_path / "bars.csv"
    path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        data_loader,
        "load_data_from_csv",
        lambda _path: SimpleNamespace(dataname=pd.DataFrame()),
    )
    with pytest.raises(ValueError, match="No data loaded"):
        cross_validation.load_data(path)

    monkeypatch.setattr(
        data_loader,
        "load_data_from_csv",
        lambda _path: SimpleNamespace(dataname=pd.DataFrame({"close": [1.0]})),
    )
    with pytest.raises(ValueError, match="Missing required column 'open'"):
        cross_validation.load_data(path)
    with pytest.raises(FileNotFoundError, match="Data file not found"):
        cross_validation.load_data(tmp_path / "missing.csv")


def test_cross_validation_report_explains_each_disagreement(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cross_validation.print_report(
        {
            "backtrader": {"trade_count": 2, "total_pnl": 100.0, "max_drawdown": 0.1},
            "custom": {"trade_count": 1, "total_pnl": 80.0, "max_drawdown": 0.2},
            "agreement": {
                "trade_count_match": False,
                "trade_count_diff": 1,
                "pnl_within_tolerance": False,
                "pnl_diff": 20.0,
                "pnl_tolerance": 1.0,
                "max_drawdown_within_tolerance": False,
                "max_drawdown_diff": 0.1,
                "max_drawdown_tolerance": 0.01,
                "overall_pass": False,
            },
        }
    )

    report = capsys.readouterr().out
    assert "Trade Count Match: ✗ FAIL" in report
    assert "Difference: 1" in report
    assert "Difference: $20.00" in report
    assert "OVERALL FAIL" in report


def test_cross_validation_cli_writes_the_report_and_exits_with_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = pd.DataFrame({"close": [100.0, 101.0]})
    actions = pd.Series([0, 1], index=bars.index)
    results = iter(
        [
            {"trade_count": 1, "total_pnl": 10.0, "max_drawdown": 0.02},
            {"trade_count": 1, "total_pnl": 10.0, "max_drawdown": 0.02},
        ]
    )
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        ["cross-validation", "--data-path", "bars.csv", "--json-output", str(output)],
    )
    monkeypatch.setattr(cross_validation, "load_data", lambda _path: bars)
    monkeypatch.setattr(cross_validation, "_crossover_actions", lambda _close: actions)
    monkeypatch.setattr(
        cross_validation, "run_backtrader_engine", lambda *_args, **_kwargs: next(results)
    )
    monkeypatch.setattr(
        cross_validation, "run_custom_engine", lambda *_args, **_kwargs: next(results)
    )

    with pytest.raises(SystemExit) as exit_info:
        cross_validation.main()

    assert exit_info.value.code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["agreement"]["overall_pass"] is True


def test_cross_validation_cli_reports_loader_failure_as_exit_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["cross-validation", "--data-path", "missing.csv"])

    def fail_loading(_path: str) -> pd.DataFrame:
        raise FileNotFoundError("missing fixture")

    monkeypatch.setattr(cross_validation, "load_data", fail_loading)
    with pytest.raises(SystemExit) as exit_info:
        cross_validation.main()
    assert exit_info.value.code == 1


@pytest.mark.parametrize(
    "engine", [cross_validation.run_backtrader_engine, cross_validation.run_custom_engine]
)
def test_cross_validation_engines_reject_action_traces_from_different_bar_timestamps(
    engine: Callable[..., Any],
) -> None:
    bars = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
        },
        index=pd.date_range("2026-01-02", periods=2, freq="min", tz="UTC"),
    )
    actions = pd.Series([0, 1], index=bars.index + pd.Timedelta(minutes=1))

    with pytest.raises(ValueError, match="actions must align exactly with bar timestamps"):
        engine(bars, actions=actions)
