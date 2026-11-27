"""Trade note reporting contracts for multi-target EMA runner records."""

from __future__ import annotations

from evaluation.reporting.trade_note import build_trade_note


def test_trade_note_describes_ema_runner_after_recorded_partial_targets() -> None:
    open_row = {
        "time": "2025-03-03T15:00:00Z",
        "sl_price": 98.0,
        "sl_ref": "M5_last_swing_low",
        "tp_price": None,
        "tp_ref": "ema_21",
        "exit_mode": "ema_21",
        "ema_runner_fraction": 0.25,
        "tp_legs": [
            {
                "leg": 1,
                "executed_price": 101.0,
                "lot_fraction": 0.5,
                "reference": "M5_fvg_bull_high",
            },
            {
                "leg": 2,
                "executed_price": 102.0,
                "lot_fraction": 0.25,
                "reference": "H1_last_swing_high",
            },
        ],
    }
    close_row = {"time": "2025-03-03T15:05:00Z"}

    lines = build_trade_note(
        open_row,
        close_row,
        entry_price=100.0,
        exit_price=101.5,
        direction=1,
        pnl=1.5,
        pnl_calc=1.5,
        duration_mins=5,
        duration_secs=0,
        lots=1.0,
        close_reason_detail="ema_exit",
    )

    target_line = next(line for line in lines if line.startswith("TAKE PROFIT (TP):"))
    assert "TP 1 101.00" in target_line
    assert "TP 2 102.00" in target_line
    assert (
        "TP 3 EMA-21 runner exit after TP 2 partial target(s) "
        "(25.0% of entry size; target legs close 75.0%)"
    ) in target_line
