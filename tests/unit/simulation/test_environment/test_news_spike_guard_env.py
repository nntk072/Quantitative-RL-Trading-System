from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

from market_data.news.guard import NewsGuardConfig
from simulation.environment.env import TradingEnv
from trading.execution import CostModel


def _env(tmp_path: Path, *, guard_on: bool) -> TradingEnv:
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
            "session": "london",
            "volume": 1000.0,
        },
        index=index,
    )
    features = pd.DataFrame({"atr_5": np.ones(len(index))}, index=index)
    calendar = tmp_path / "calendar.csv"
    release = index[10].strftime("%Y-%m-%dT%H:%M:%SZ")
    calendar.write_text(
        f"utc_time,category,summary,source,source_sha256,retrieved_on\n{release},CPI,CPI,x,y,z\n",
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
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        block_overnight=False,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        news_guard=guard,
    )
    env.reset(seed=1)
    return env


def _run_entries(env: TradingEnv, steps: int) -> list[tuple[int, int]]:
    """Return (decision bar, cumulative gate rejections) after each entry request."""
    out = []
    for _ in range(steps):
        bar = env.step_idx
        env.step(1)
        out.append((bar, int(env._entry_diag["rejected_gate"])))
    return out


def test_entries_inside_release_window_are_rejected(tmp_path: Path) -> None:
    rows = _run_entries(_env(tmp_path, guard_on=True), 12)
    rejected_bars = [bar for bar, count in rows if count > 0]

    # The release is at bar 10, so bars 5 through 15 are blocked and bars before 5 are not.
    assert rejected_bars and min(rejected_bars) == 5
    assert all(bar >= 5 for bar in rejected_bars)


def test_guard_off_never_rejects_for_news(tmp_path: Path) -> None:
    rows = _run_entries(_env(tmp_path, guard_on=False), 12)

    assert all(count == 0 for _bar, count in rows)


def test_bundle_environments_share_identified_news_mask(tmp_path: Path) -> None:
    from simulation.environment.bundles import build_env_bundle
    from trading.strategies import BaselineStrategy

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
            "session": "london",
            "volume": 1000.0,
        },
        index=index,
    )
    features = pd.DataFrame({"atr_5": np.ones(len(index))}, index=index)
    path = build_env_bundle(
        tmp_path,
        bars,
        features,
        OmegaConf.create(
            {
                "env": {"strategy_actions": False, "obs_window": 1},
                "data": {"raw_dir": str(tmp_path)},
            }
        ),
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="news-mask-shared-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )
    guard = NewsGuardConfig(
        calendar_path=tmp_path / "calendar.csv",
        exempt_open_manipulation=False,
        baseline_lookback_sessions=5,
    )
    guard.calendar_path.write_text(
        "utc_time,category,summary,source,source_sha256,retrieved_on\n",
        encoding="utf-8",
    )
    common = {
        "obs_window": 1,
        "block_overnight": False,
        "cost_model": CostModel(spread_points=0.0, point_size=0.01),
        "news_guard": guard,
    }
    first = TradingEnv.from_bundle(path, **common)
    second = TradingEnv.from_bundle(path, **common)

    first.step(1)
    second.step(1)

    assert first._news_mask_bundle_identity == second._news_mask_bundle_identity
    assert first._news_block_mask is second._news_block_mask
    assert first._news_block_mask is not None
    assert not first._news_block_mask.flags.writeable


def test_resting_limit_is_cancelled_when_release_blackout_starts(tmp_path: Path) -> None:
    env = _env(tmp_path, guard_on=True)
    bar_time = env._bar_time(env.step_idx)
    env._pending_entry_order = {
        "order_id": "test:limit",
        "order_type": "limit",
        "decision_id": "test",
        "session_id": int(env._session_ids_arr[env.step_idx])
        if env._session_ids_arr is not None
        else 1,
        "decision_time": bar_time,
        "decision_bar_time": bar_time,
        "order_submission_time": bar_time,
        "expiry_time": bar_time + pd.Timedelta(minutes=60),
        "limit_price": 99.0,
        "selected": {},
        "fill_idx": env.step_idx + 1,
        "direction": 1,
    }
    # Advance into the release window (bar 10 is the release, so bar 5 onward is blocked).
    while env.step_idx < 6:
        env.step(0)

    cancels = [row for row in env.trade_log if row.get("type") == "order_cancel"]
    assert env._pending_entry_order is None
    assert cancels and cancels[-1]["reason"] == "news_spike_before_limit_fill"
