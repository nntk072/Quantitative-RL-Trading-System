from __future__ import annotations

import pandas as pd
import pytest

from trading.orders.stops import stop_menu


class _Candidates:
    manipulation_filter = "against"

    def __init__(self, values: list[tuple[str, float]]) -> None:
        self.values = values

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        del direction, row
        return list(self.values)


def test_stop_menu_rejects_invalid_direction_grid_and_timeframes() -> None:
    strategy = _Candidates([])
    with pytest.raises(ValueError, match="direction must be"):
        stop_menu(
            strategy,
            direction=0,
            entry_price=100.0,
            row=pd.Series(dtype=float),
            min_dist=1.0,
            buffer=0.0,
            manipulation="none",
        )
    with pytest.raises(ValueError, match="price_increment"):
        stop_menu(
            strategy,
            direction=1,
            entry_price=100.0,
            row=pd.Series(dtype=float),
            min_dist=1.0,
            buffer=0.0,
            manipulation="none",
            price_increment=0.0,
        )
    with pytest.raises(ValueError):
        stop_menu(
            strategy,
            direction=1,
            entry_price=100.0,
            row=pd.Series(dtype=float),
            min_dist=1.0,
            buffer=0.0,
            manipulation="none",
            htf=("bad-timeframe",),
        )


def test_stop_menu_keeps_live_sweep_wick_as_anchor_and_reports_rejected_levels() -> None:
    row = pd.Series(
        {
            "sweep_low": 1.0,
            "sweep_low_wick": 94.0,
            "last_swing_low": 90.0,
        }
    )

    menu, audit = stop_menu(
        _Candidates([("last_swing_low", 90.0)]),
        direction=1,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.5,
        manipulation="none",
        htf=(),
    )

    assert menu == [("sweep_low_wick", 93.5, 6.5)]
    assert any(item["reason"] == "active_sweep_wick_is_stop_anchor" for item in audit)


def test_stop_menu_audits_candidate_swing_without_causal_provenance() -> None:
    row = pd.Series({"M5_swing_low_candidate_1": 95.0})

    menu, audit = stop_menu(
        _Candidates([]),
        direction=1,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.0,
        manipulation="none",
        htf=("M5",),
    )

    assert menu == []
    assert audit[0]["name"] == "M5_swing_low_candidate_1"
    assert audit[0]["reason"] == "missing_decision_time"


def test_stop_menu_requires_the_active_standard_deviation_timeframe_and_level_one() -> None:
    row = pd.Series(
        {
            "last_swing_low": 90.0,
            "M15_standard_deviation_level_1_price": 97.0,
            "H1_standard_deviation_level_1_price": 96.0,
            "standard_deviation_level_2_price": 95.0,
        }
    )
    strategy = _Candidates(
        [
            ("last_swing_low", 90.0),
            ("M15_standard_deviation_level_1_price", 97.0),
            ("H1_standard_deviation_level_1_price", 96.0),
            ("standard_deviation_level_2_price", 95.0),
        ]
    )

    menu, audit = stop_menu(
        strategy,
        direction=1,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.0,
        manipulation="none",
        htf=(),
        standard_deviation_timeframes=("M15",),
    )

    assert menu == [("M15_standard_deviation_level_1_price", 97.0, 3.0)]
    assert {item["name"] for item in audit if item["status"] == "rejected"} == {
        "H1_standard_deviation_level_1_price",
        "last_swing_low",
        "standard_deviation_level_2_price",
    }


def test_stop_menu_records_valid_candidate_provenance_and_smt_swing_name() -> None:
    decision = pd.Timestamp("2025-01-06 16:30", tz="UTC")
    decision_ms = decision.value // 1_000_000
    row = pd.Series(
        {
            "M5_swing_low_candidate_1": 95.0,
            "M5_swing_low_candidate_1_pivot_time_ms": decision_ms - 120_000,
            "M5_swing_low_candidate_1_confirmed_at_ms": decision_ms - 60_000,
            "M5_swing_low_candidate_1_age_bars": 2.0,
            "decision_at_ms": decision_ms,
            "smt_bullish": 1.0,
        },
        name=decision,
    )

    menu, audit = stop_menu(
        _Candidates([("last_swing_low", 90.0)]),
        direction=1,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.0,
        manipulation="none",
        htf=("M5",),
    )

    assert menu[0][0] == "M5_swing_low_candidate_1"
    assert ("smt_swing", 90.0, 10.0) in menu
    candidate = next(item for item in audit if item["name"] == "M5_swing_low_candidate_1")
    assert candidate["status"] == "eligible"
    assert candidate["provenance"] == [
        {
            "timeframe": "M5",
            "pivot_time_ms": decision_ms - 120_000,
            "confirmed_at_ms": decision_ms - 60_000,
            "age_bars": 2.0,
        }
    ]


@pytest.mark.parametrize(
    ("manipulation_filter", "expected_name", "rejected_name"),
    [
        ("against", "M5_swing_low", "M5_ifvg_bull_low"),
        ("follow", "M5_ifvg_bull_low", "M5_swing_low"),
    ],
)
def test_stop_menu_applies_directional_manipulation_filter(
    manipulation_filter: str, expected_name: str, rejected_name: str
) -> None:
    strategy = _Candidates([("M5_swing_low", 90.0), ("M5_ifvg_bull_low", 95.0)])
    strategy.manipulation_filter = manipulation_filter

    menu, audit = stop_menu(
        strategy,
        direction=1,
        entry_price=100.0,
        row=pd.Series(dtype=float),
        min_dist=1.0,
        buffer=0.0,
        manipulation="against",
        htf=(),
    )

    assert [candidate[0] for candidate in menu] == [expected_name]
    assert any(
        item["name"] == rejected_name and item["reason"] == "manipulation_filter" for item in audit
    )
