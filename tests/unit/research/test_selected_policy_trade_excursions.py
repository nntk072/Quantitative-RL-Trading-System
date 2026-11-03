from __future__ import annotations

import numpy as np
import pandas as pd
from scripts.research.analysis.evaluation.summarize_selected_policy_trade_excursions import (
    summarize_arm,
)


def test_summarize_arm_reconciles_fills_and_bounds_entry_timestamp_tie(tmp_path) -> None:
    entry = pd.Timestamp("2025-01-02T10:00:00.100Z")
    middle = pd.Timestamp("2025-01-02T10:00:00.200Z")
    exit_time = pd.Timestamp("2025-01-02T10:00:00.300Z")
    positions_path = tmp_path / "positions.csv"
    fills_path = tmp_path / "fills.csv"
    pd.DataFrame(
        [
            {
                "position_id": "p1",
                "direction": 1,
                "entry_time": entry.isoformat(),
                "exit_time": exit_time.isoformat(),
                "entry_price": 100.5,
                "exit_price": 104.0,
                "completed": True,
                "holding_seconds": 0.2,
                "exit_reason": "target",
                "position_net_pnl": 35.0,
            }
        ]
    ).to_csv(positions_path, index=False)
    pd.DataFrame(
        [
            {
                "type": "open",
                "position_id": "p1",
                "direction": 1,
                "price": 100.5,
                "actual_tick_time": entry.isoformat(),
                "position_complete": False,
                "fill_id": "f1",
                "modeled_stop_risk_usd": 100.0,
                "sl_price": 90.5,
                "lots": 10.0,
            },
            {
                "type": "tp_close",
                "position_id": "p1",
                "direction": 1,
                "price": 104.0,
                "actual_tick_time": exit_time.isoformat(),
                "position_complete": True,
                "fill_id": "f2",
                "modeled_stop_risk_usd": 100.0,
                "sl_price": 90.5,
                "lots": 10.0,
            },
        ]
    ).to_csv(fills_path, index=False)

    entry_ns, middle_ns, exit_ns = entry.value, middle.value, exit_time.value

    class TickBookFixture:
        _ts = np.asarray([entry_ns, entry_ns, middle_ns, exit_ns], dtype=np.int64)
        _bid = np.asarray([100.0, 98.0, 103.0, 104.0], dtype=np.float64)
        _ask = np.asarray([100.5, 98.5, 103.5, 104.5], dtype=np.float64)

    result = summarize_arm("a4a", positions_path, fills_path, TickBookFixture())  # type: ignore[arg-type]

    assert len(result) == 1
    row = result.iloc[0]
    assert row["mfe_points_lower"] == row["mfe_points_upper"] == 3.5
    assert row["mae_points_lower"] == 0.5
    assert row["mae_points_upper"] == 2.5
    assert row["entry_timestamp_tie_rows"] == 2
    assert row["initial_stop_distance_points"] == 10.0
    assert row["realized_r"] == 0.35
