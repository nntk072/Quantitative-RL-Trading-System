"""Saved-equity summary regeneration contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest

from evaluation.reporting import order_chart_regeneration as regeneration


def test_load_equity_returns_none_when_saved_summary_is_absent(tmp_path: Path) -> None:
    assert regeneration._load_equity(tmp_path) is None


def test_load_equity_uses_the_first_saved_column_and_names_the_series(tmp_path: Path) -> None:
    index = pd.date_range("2025-03-03 15:00", periods=2, freq="min", tz="UTC")
    pd.DataFrame({"portfolio": [100.0, 101.0], "ignored": [7.0, 8.0]}, index=index).to_csv(
        tmp_path / "equity.csv"
    )

    equity = regeneration._load_equity(tmp_path)

    assert equity is not None
    assert equity.name == "equity"
    assert equity.tolist() == [100.0, 101.0]
    assert equity.index.equals(index)


def test_empty_saved_equity_skips_all_summary_plotters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pd.DataFrame({"equity": pd.Series(dtype=float)}).to_csv(tmp_path / "equity.csv")
    plotters = cast(Any, regeneration.__dict__["_plt"])
    interactive = cast(Any, regeneration.__dict__["_pi"])
    for owner in (plotters, interactive):
        for name in ("plot_equity_curve", "plot_drawdown", "plot_daily_pnl"):
            monkeypatch.setattr(
                owner, name, lambda *_args, **_kwargs: pytest.fail("empty series plotted")
            )

    regeneration._replot_split_summary(tmp_path, SimpleNamespace(), dpi=72)


def test_summary_replot_passes_saved_equity_limits_and_outputs_to_plotters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = pd.date_range("2025-03-03 15:00", periods=2, freq="min", tz="UTC")
    pd.DataFrame({"equity": [100.0, 101.0]}, index=index).to_csv(tmp_path / "equity.csv")
    calls: list[tuple[str, dict[str, Any]]] = []
    plotters = cast(Any, regeneration.__dict__["_plt"])
    interactive = cast(Any, regeneration.__dict__["_pi"])

    def record(owner: str, name: str) -> Any:
        def plot(*_args: Any, **kwargs: Any) -> None:
            calls.append((f"{owner}.{name}", kwargs))

        return plot

    for owner_name, owner in (("static", plotters), ("interactive", interactive)):
        for name in ("plot_equity_curve", "plot_drawdown", "plot_daily_pnl"):
            monkeypatch.setattr(owner, name, record(owner_name, name))
    monkeypatch.setattr(regeneration, "_extract_ftmo_limits", lambda _cfg: (10.0, 20.0, 30.0))
    trades = pd.DataFrame({"type": ["open"]})

    regeneration._replot_split_summary(
        tmp_path,
        SimpleNamespace(account=SimpleNamespace(initial_balance=200.0)),
        dpi=144,
        trades=trades,
    )

    assert {name for name, _kwargs in calls} == {
        "static.plot_equity_curve",
        "static.plot_drawdown",
        "static.plot_daily_pnl",
        "interactive.plot_equity_curve",
        "interactive.plot_drawdown",
        "interactive.plot_daily_pnl",
    }
    equity_kwargs = next(kwargs for name, kwargs in calls if name == "static.plot_equity_curve")
    assert equity_kwargs["initial_balance"] == 200.0
    assert equity_kwargs["daily_loss_limit"] == 10.0
    assert equity_kwargs["max_loss_limit"] == 20.0
    assert equity_kwargs["profit_target"] == 30.0
    assert equity_kwargs["trades"] is trades
    assert equity_kwargs["out_path"] == tmp_path / "equity.png"
    assert equity_kwargs["dpi"] == 144
    assert next(kwargs for name, kwargs in calls if name == "static.plot_drawdown")["out_path"] == (
        tmp_path / "drawdown.png"
    )
    assert (
        next(kwargs for name, kwargs in calls if name == "interactive.plot_daily_pnl")["out_path"]
        == tmp_path / "daily_pnl.html"
    )


def test_missing_plotly_backend_skips_remaining_interactive_summary_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = pd.date_range("2025-03-03 15:00", periods=1, freq="min", tz="UTC")
    pd.DataFrame({"equity": [100.0]}, index=index).to_csv(tmp_path / "equity.csv")
    plotters = cast(Any, regeneration.__dict__["_plt"])
    interactive = cast(Any, regeneration.__dict__["_pi"])
    static_calls: list[str] = []
    interactive_calls: list[str] = []
    for name in ("plot_equity_curve", "plot_drawdown", "plot_daily_pnl"):
        monkeypatch.setattr(
            plotters, name, lambda *_args, _name=name, **_kwargs: static_calls.append(_name)
        )

    def unavailable(*_args: Any, **_kwargs: Any) -> None:
        interactive_calls.append("plot_equity_curve")
        raise ImportError("plotly unavailable")

    monkeypatch.setattr(interactive, "plot_equity_curve", unavailable)
    monkeypatch.setattr(
        interactive,
        "plot_drawdown",
        lambda *_args, **_kwargs: interactive_calls.append("plot_drawdown"),
    )
    monkeypatch.setattr(
        interactive,
        "plot_daily_pnl",
        lambda *_args, **_kwargs: interactive_calls.append("plot_daily_pnl"),
    )
    monkeypatch.setattr(regeneration, "_extract_ftmo_limits", lambda _cfg: (None, None, None))

    regeneration._replot_split_summary(tmp_path, SimpleNamespace(), dpi=72)

    assert static_calls == ["plot_equity_curve", "plot_drawdown", "plot_daily_pnl"]
    assert interactive_calls == ["plot_equity_curve"]
