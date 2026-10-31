from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import numpy as np
import pandas as pd
from scripts.research.analysis.exit_shadow_fixed_entry import (
    PairedLatency,
    _menu_pairs,
    _monthly_cohort_summary,
    _trade_metrics,
    paired_bootstrap,
)

from market_data.loading.ticks import TickBook


def test_paired_latency_reuses_first_historical_draw_then_stays_keyed() -> None:
    ema = PairedLatency("e1:p1", 12)
    structural = PairedLatency("e1:p1", 12)

    assert ema.integers(0, 30) == 12
    assert structural.integers(0, 30) == 12
    assert ema.integers(0, 30) == structural.integers(0, 30)
    assert ema.integers(0, 30) == structural.integers(0, 30)
    assert ema.integers(0, 30) != PairedLatency("e2:p1", 12).integers(0, 30)


def test_menu_parser_preserves_reference_and_price_order() -> None:
    assert _menu_pairs("[['asia_high', 101.25], ['week_high', 103.5]]") == (
        ("asia_high", 101.25),
        ("week_high", 103.5),
    )


def test_paired_bootstrap_is_repeatable() -> None:
    values = np.asarray([-1.0, 0.0, 2.0, 3.0])
    first = paired_bootstrap(values, resamples=500, seed=20261024)
    second = paired_bootstrap(values, resamples=500, seed=20261024)

    assert first == second
    assert first[0] <= float(values.mean()) <= first[1]


def test_monthly_report_separates_full_cohort_from_matched_pair() -> None:
    paired = pd.DataFrame(
        [
            {
                "decision_time": "2025-03-01T00:00:00Z",
                "structural_status": "eligible",
                "ema_historical_net_pnl": 10.0,
                "ema_realized_r": 1.0,
                "structural_historical_net_pnl": 12.0,
                "delta_r_historical_net": 0.2,
            },
            {
                "decision_time": "2025-03-02T00:00:00Z",
                "structural_status": "eligible",
                "ema_historical_net_pnl": -5.0,
                "ema_realized_r": -0.5,
                "structural_historical_net_pnl": -8.0,
                "delta_r_historical_net": -0.3,
            },
            {
                "decision_time": "2025-03-03T00:00:00Z",
                "structural_status": "ineligible",
                "ema_historical_net_pnl": -4.0,
                "ema_realized_r": -0.4,
                "structural_historical_net_pnl": np.nan,
                "delta_r_historical_net": np.nan,
            },
        ]
    )

    monthly = _monthly_cohort_summary(paired)[0]

    assert monthly["frozen_entries"] == 3
    assert monthly["ema_all_net_pnl"] == 1.0
    assert monthly["ema_wins"] == 1
    assert monthly["ema_losses"] == 2
    assert monthly["ema_breakeven"] == 0
    assert np.isclose(monthly["ema_win_rate"], 1.0 / 3.0)
    assert np.isclose(monthly["ema_mean_r"], 0.1 / 3.0)
    assert monthly["paired_entries"] == 2
    assert monthly["ema_paired_net_pnl"] == 5.0
    assert monthly["structural_paired_net_pnl"] == 4.0
    assert np.isclose(monthly["mean_delta_r"], -0.05)


def test_trade_metrics_use_exit_specific_bid_ask_excursions() -> None:
    entry = pd.Timestamp("2025-01-01T00:00:00Z")
    exit_time = pd.Timestamp("2025-01-01T00:00:02Z")
    book = SimpleNamespace(
        _ts=np.asarray([entry.value, entry.value + 1_000_000_000, exit_time.value]),
        _bid=np.asarray([99.0, 96.0, 104.0]),
        _ask=np.asarray([101.0, 98.0, 106.0]),
    )
    tick_book = cast(TickBook, book)
    row = pd.Series(
        {
            "actual_tick_time": entry,
            "direction": 1,
            "lots": 2.0,
            "modeled_stop_risk_usd": 20.0,
            "price": 101.0,
        }
    )
    replay = {
        "fills": [
            {
                "actual_tick_time": exit_time,
                "fill_time": exit_time,
                "time": exit_time,
                "price": 104.0,
                "net_pnl": 6.0,
                "size": 2.0,
                "position_complete": True,
                "reason": "structure_sl",
            }
        ]
    }

    result = _trade_metrics(row, replay, tick_book, contract_size=1.0, extra_slippage_points=5.0)

    assert result["complete"]
    assert result["mae_price"] == 5.0
    assert result["mfe_price"] == 3.0
    assert result["mae_usd"] == 10.0
    assert result["mfe_usd"] == 6.0
    assert result["holding_seconds"] == 2.0
    assert result["tick_count"] == 3
    assert result["historical_net_pnl"] == 6.0
    assert result["stress_net_pnl"] == -14.0
