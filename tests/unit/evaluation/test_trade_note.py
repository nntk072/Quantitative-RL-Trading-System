"""Plain-language trade note shared by the PNG and HTML order charts."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from evaluation.reporting.trade_note import (
    build_trade_note,
    build_trade_plot_note,
    entry_reason,
    pretty_ref,
)
from trading.orders import source_timeframe

_OPEN_EMA = {
    "time": "2025-10-27 17:44:00+03:00",
    "sl_price": 25683.39,
    "tp_price": None,
    "sl_ref": "M5_last_swing_low",
    "tp_ref": "ema_21",
    "exit_mode": "ema_21",
    "level_type": "asian_low",
    "manipulation": "done",
    "strategy": "po3_ifvg",
    "sl_menu": [
        ["M5_last_swing_low", 25683.39],
        ["H1_last_swing_low", 25718.90],
        ["london_low", 25700.00],
    ],
    "tp_menu": [],
}
_CLOSE = {"time": "2025-10-27 17:48:00+03:00", "reason": "normal"}


def _note(open_row: dict[str, object], **over: object) -> list[str]:
    kwargs: dict[str, object] = {
        "entry_price": 25744.25,
        "exit_price": 25729.85,
        "direction": 1,
        "pnl": -21.53,
        "pnl_calc": -21.53,
        "duration_mins": 4,
        "duration_secs": 0,
        "lots": 1.49,
        "close_reason_detail": "normal",
    }
    kwargs.update(over)
    return build_trade_note(open_row, _CLOSE, **kwargs)  # type: ignore[arg-type]


def test_pretty_ref_maps_names_to_plain_language() -> None:
    assert pretty_ref("M5_last_swing_low") == "swing low (M5)"
    assert pretty_ref("H1_last_swing_high") == "swing high (H1)"
    assert pretty_ref("ema_21") == "EMA-21 exit"
    assert pretty_ref("asian_low") == "Asia session low"
    assert pretty_ref("dev_0") == "swing low (0x range projection)"
    assert pretty_ref("H1_fvg_bull_high") == "Fair Value Gap (bullish) (H1)"
    assert pretty_ref("M30_fvg_bear_low") == "Fair Value Gap (bearish) (M30)"
    assert pretty_ref("M15_ifvg_bear_high") == "Inverse Fair Value Gap (bearish) (M15)"
    assert pretty_ref("asian_low|H1_last_swing_low") == ("Asia session low + swing low (H1)")


def test_pretty_ref_is_safe_on_empty_and_nan() -> None:
    assert pretty_ref("") == ""
    assert pretty_ref(None) == ""
    assert pretty_ref(float("nan")) == ""
    assert pretty_ref(math.nan) == ""


def test_reference_timeframes_cover_all_configured_candle_frames() -> None:
    assert source_timeframe("M30_fvg_bull_high") == "M30"
    assert source_timeframe("D1_last_swing_low") == "D1"
    assert source_timeframe("london_low") == ""
    assert source_timeframe("") == ""


def test_entry_reason_names_the_level_and_manipulation_state() -> None:
    text = entry_reason(_OPEN_EMA)
    assert text.startswith("Entry:")
    assert "swept Asia session low" in text
    assert 'manipulation "done"' in text


def test_entry_reason_mentions_distribution_phase() -> None:
    text = entry_reason({**_OPEN_EMA, "distribution_phase": 1.0})
    assert "PO3 distribution active" in text


def test_entry_reason_lists_overlapping_ideas_and_timeframes() -> None:
    text = entry_reason(
        {
            **_OPEN_EMA,
            "entry_ideas": ["order_block", "standard_deviation", "fvg_retest"],
            "entry_idea_timeframes": {
                "order_block": ["M5", "H1"],
                "standard_deviation": ["M15"],
                "fvg_retest": ["M3"],
            },
            "entry_idea_gap_reactions": {"FVG": ["M3"], "IFVG": ["H1"]},
        }
    )
    assert "Order Block reaction (M5, H1)" in text
    assert "Fib-like swing retracement (0.5-0.786) (M15)" in text
    assert "FVG reaction (M3)" in text
    assert "IFVG reaction (H1)" in text
    assert "3 entry ideas overlap" in text


def test_entry_reason_lists_only_linked_fvg_zone_values() -> None:
    text = entry_reason(
        {
            **_OPEN_EMA,
            "entry_ideas": ["po3"],
            "entry_idea_timeframes": {"po3": ["M5"]},
            "entry_idea_zones": [
                {
                    "idea": "po3",
                    "family": "ifvg",
                    "timeframe": "M5",
                    "side": "bull",
                    "low": 100.0,
                    "high": 101.5,
                }
            ],
        }
    )
    assert "PO3 setup (M5)" in text
    assert "FVG → IFVG bull (M5) 100.00-101.50" in text


def test_entry_reason_distinguishes_inactive_from_unrecorded_ideas() -> None:
    assert "No named setup signal was active at this entry" in entry_reason(
        {**_OPEN_EMA, "entry_ideas": [], "entry_idea_timeframes": {}}
    )
    unrecorded = {**_OPEN_EMA, "level_type": None}
    assert "strategy offered this side" in entry_reason(unrecorded)


def test_entry_reason_degrades_when_columns_are_empty() -> None:
    text = entry_reason({})
    assert text == "Entry: strategy offered this side (no swept level)"
    assert entry_reason({"manipulation": ""}).strip() != ""


def test_note_has_direction_open_close_pnl_and_volume() -> None:
    lines = _note(_OPEN_EMA)
    joined = "\n".join(lines)
    assert "ENTRY: Long" in joined
    assert "17:44" in joined and "17:48" in joined
    assert "RESULT: Net realized PnL $-21.53" in joined
    assert "Volume 1.49 lots" in joined
    assert "Fill-price calc $-21.53" in joined
    assert sum(line.startswith("ENTRY:") for line in lines) == 1
    assert sum(line.startswith("STOP LOSS (SL):") for line in lines) == 1
    assert sum(line.startswith("TAKE PROFIT (TP):") for line in lines) == 1
    assert "ENTRY: Long" in joined and "RESULT: Net realized PnL" in joined


def test_ema_note_says_no_fixed_target() -> None:
    joined = "\n".join(_note(_OPEN_EMA))
    assert "No fixed TP; EMA-21 closed the full position" in joined
    assert "EMA-21 closed the full position" in joined


def test_note_names_the_initial_stop() -> None:
    joined = "\n".join(_note(_OPEN_EMA))
    assert "STOP LOSS (SL)" in joined
    assert "SL 1 initial 25683.39" in joined


def test_structural_note_shows_numbered_targets_with_source_and_size() -> None:
    row = {
        **_OPEN_EMA,
        "tp_price": 25876.83,
        "tp_ref": "H1_last_swing_low",
        "exit_mode": "structural",
        "tp_legs": str(
            [
                {
                    "leg": 1,
                    "executed_price": 25876.83,
                    "reference": "H1_last_swing_low",
                    "lot_fraction": 0.6,
                },
                {
                    "leg": 2,
                    "executed_price": 25840.10,
                    "reference": "asian_low",
                    "lot_fraction": 0.4,
                },
            ]
        ),
    }
    joined = "\n".join(_note(row))
    assert "TP 1 25876.83 (swing low (H1)) (60.0% of entry size)" in joined
    assert "TP 2 25840.10 (Asia session low) (40.0% of entry size)" in joined


def test_note_reports_stop_target_changes_and_actual_exit_fills() -> None:
    events = pd.DataFrame(
        [
            {
                "type": "tp_update",
                "tp_slot": 1,
                "effective_time": "2025-10-27 17:45:00+03:00",
                "price": 25740.0,
                "reason": "swing_target_updated",
            },
            {
                "type": "tp_partial_close",
                "tp_slot": 1,
                "time": "2025-10-27 17:46:01.123+03:00",
                "actual_tick_time": "2025-10-27 17:46:01.123+03:00",
                "price": 25740.0,
                "size": 0.5,
                "pnl": 12.34,
                "fill_quote_source": "tick",
                "reason": "structure_tp1",
            },
            {
                "type": "sl_update",
                "effective_time": "2025-10-27 17:46:01.123+03:00",
                "price": 25746.25,
                "reason": "post_partial_breakeven",
            },
            {
                "type": "stop_close",
                "time": "2025-10-27 17:47:02.500+03:00",
                "actual_tick_time": "2025-10-27 17:47:02.500+03:00",
                "price": 25746.25,
                "size": 0.5,
                "pnl": -3.21,
                "fill_quote_source": "tick",
                "reason": "structure_sl",
            },
        ]
    )
    joined = "\n".join(_note(_OPEN_EMA, position_events=events))

    assert "TP 1 updated 17:45:00 to 25740.00" in joined
    assert "TP 1 partial fill 17:46:01.123 @ 25740.00 (tick fill)" in joined
    assert "realized $+12.34" in joined
    assert "STOP LOSS (SL): SL 1 initial" in joined
    assert "SL 2 moved 17:46:01.123 to 25746.25" in joined
    assert "SL fill 17:47:02.500 @ 25746.25 (tick fill)" in joined
    assert "realized $-3.21" in joined
    assert "{" not in joined and "}" not in joined


def test_short_direction_is_labelled() -> None:
    joined = "\n".join(_note(_OPEN_EMA, direction=-1))
    assert "Short" in joined


def test_thesis_report_separates_primary_idea_from_supporting_context() -> None:
    row = {
        **_OPEN_EMA,
        "primary_idea": "fvg_retest",
        "primary_setup_timeframe": "M5",
        "primary_direction": 1,
        "supporting_idea_timeframes": ["po3@H1:long", "ifvg_retest@M3:long"],
        "entry_ideas": ["po3", "fvg_retest", "ifvg_retest"],
        "entry_idea_timeframes": {"po3": ["H1"], "fvg_retest": ["M5"]},
    }
    reason = entry_reason(row)
    assert "Primary thesis: FVG retest (M5, long)" in reason
    assert "Supporting context: po3@H1:long; ifvg_retest@M3:long" in reason
    assert "3 entry ideas overlap" not in reason

    note = build_trade_plot_note(
        row,
        _CLOSE,
        entry_price=100.0,
        exit_price=99.0,
        direction=1,
        pnl=-1.0,
        lots=1.0,
        close_reason_detail="stop_close",
    )
    assert note[1] == "REASON FVG retest M5 long; context: po3@H1:long, ifvg_retest@M3:long"


@pytest.mark.parametrize("bad", [None, "", "not-a-menu", 3, float("nan")])
def test_menu_parsing_tolerates_junk(bad: object) -> None:
    joined = "\n".join(_note({**_OPEN_EMA, "sl_menu": bad}))
    assert joined  # never raises, still produces the note
