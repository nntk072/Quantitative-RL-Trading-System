from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from market_data.news.guard import NewsGuardConfig
from simulation.backtest import run_backtest
from trading.execution import CostModel


def _entry_requests_from_bar_five() -> Callable[[object], int]:
    """Request a long entry on every decision from bar 5 (the policy is called once per bar)."""
    calls = {"n": -1}

    def policy(_observation: object) -> int:
        calls["n"] += 1
        return 1 if calls["n"] >= 4 else 0

    return policy


def _run(tmp_path: Path, *, guard_on: bool) -> pd.DataFrame:
    index = pd.date_range("2026-01-05 14:00", periods=30, freq="1min", tz="UTC")
    close = np.full(len(index), 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
            "volume": 1000.0,
        },
        index=index,
    )
    features = pd.DataFrame(
        {"atr_5": np.ones(len(index)), "last_swing_low": np.full(len(index), 99.0)}, index=index
    )
    calendar = tmp_path / "calendar.csv"
    calendar.write_text(
        "utc_time,category,summary,source,source_sha256,retrieved_on\n"
        f"{index[10].strftime('%Y-%m-%dT%H:%M:%SZ')},CPI,CPI,x,y,z\n",
        encoding="utf-8",
    )
    guard = (
        NewsGuardConfig(
            calendar_path=calendar,
            exempt_open_manipulation=False,
            baseline_lookback_sessions=5,
        )
        if guard_on
        else None
    )
    result = run_backtest(
        bars,
        features,
        _entry_requests_from_bar_five(),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        rr_ratio=1.0,
        open_manipulation_bars=0,
        hold_on_zero=True,
        block_overnight=False,
        news_guard=guard,
    )
    return cast(pd.DataFrame, result["trades"])


def test_backtest_rejects_entries_inside_release_window(tmp_path: Path) -> None:
    trades = _run(tmp_path, guard_on=True)

    rejects = trades[trades["type"].eq("reject") & trades["reason"].eq("news_spike_blocked")]
    assert not rejects.empty
    assert rejects["decision_bar"].min() == 5
    assert rejects["decision_bar"].max() == 15


def test_backtest_guard_off_has_no_news_rejects(tmp_path: Path) -> None:
    trades = _run(tmp_path, guard_on=False)

    assert "reason" not in trades.columns or not trades["reason"].eq("news_spike_blocked").any()
