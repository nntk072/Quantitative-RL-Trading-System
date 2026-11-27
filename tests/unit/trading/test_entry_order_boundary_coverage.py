"""Structural order geometry contracts used by strategy-based entries."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.orders.entries import OrderGeometry, dynamic_tp, place_strategy_order
from trading.orders.targets import collapse_levels, target_menu


class _StructuralStrategy:
    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
        del row
        return [("last_swing_low", 95.0)] if direction == 1 else [("last_swing_high", 105.0)]

    def sl_reference(self, *, direction: int, row: pd.Series) -> None:
        del direction, row


def _place(row: pd.Series, *, runner_fraction: float) -> OrderGeometry:
    return place_strategy_order(
        _StructuralStrategy(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
        min_dist=1.0,
        sl_fraction=0.0,
        tp_fraction=0.5,
        exit_mode="ema_21",
        buffer_pts=0.0,
        max_tp_distance=30.0,
        htf=(),
        tp_selections=(0, 1, 2),
        tp_z=(0.5, -0.25),
        allow_multi_tp=True,
        allow_simplex=True,
        price_increment=0.01,
        ema_runner_fraction=runner_fraction,
    )


def test_ema_runner_keeps_ordered_targets_and_reserves_the_runner_fraction() -> None:
    geometry = _place(
        pd.Series(
            {
                "last_swing_high": 110.0,
                "asian_high": 115.0,
                "london_high": 120.0,
                "ema_21": 101.0,
            }
        ),
        runner_fraction=0.25,
    )

    assert geometry.rejected is False
    assert geometry.exit_mode == "ema_21"
    assert geometry.sl_price == pytest.approx(95.0)
    targets = (geometry.tp1_price, geometry.tp2_price, geometry.tp3_price)
    assert targets == pytest.approx((110.0, 115.0, 120.0))
    assert geometry.tp_indices == (0, 1, 2)
    assert sum(geometry.tp_lot_fractions) == pytest.approx(0.75)
    assert all(fraction > 0.0 for fraction in geometry.tp_lot_fractions)
    assert geometry.ema_runner_fraction == pytest.approx(0.25)


def test_ema_runner_rejects_when_structural_targets_are_unavailable() -> None:
    geometry = _place(pd.Series({"last_swing_low": 95.0, "ema_21": 101.0}), runner_fraction=0.25)

    assert geometry.rejected is True
    assert geometry.reject_kind == "tp"
    assert geometry.sl_price == pytest.approx(95.0)
    assert geometry.tp_price is None
    assert geometry.n_tp == 0


def test_structural_entry_selects_the_ranked_target_and_records_its_reference() -> None:
    geometry = place_strategy_order(
        _StructuralStrategy(),
        direction=1,
        entry_price=100.0,
        feat_row=pd.Series(
            {
                "last_swing_low": 95.0,
                "last_swing_high": 110.0,
                "asian_high": 120.0,
                "london_high": 130.0,
            }
        ),
        min_dist=1.0,
        sl_fraction=0.0,
        tp_fraction=0.5,
        exit_mode="structural",
        buffer_pts=0.0,
        max_tp_distance=30.0,
        htf=(),
        price_increment=0.01,
    )

    assert geometry.rejected is False
    assert geometry.sl_ref == "last_swing_low"
    assert geometry.tp_ref == "asian_high"
    assert geometry.tp_price == pytest.approx(120.0)
    assert geometry.tp_index == 1
    assert geometry.tp_references[1].reason == "selected"
    assert geometry.tp_references[1].original_price == pytest.approx(120.0)
    assert geometry.tp_references[0].reason == "eligible"


def test_entry_rejects_invalid_runner_fraction_and_missing_stop_candidates() -> None:
    with pytest.raises(ValueError, match="ema_runner_fraction must be in \\[0, 1\\)"):
        place_strategy_order(
            _StructuralStrategy(),
            direction=1,
            entry_price=100.0,
            feat_row=pd.Series({"ema_21": 101.0}),
            min_dist=1.0,
            sl_fraction=0.0,
            tp_fraction=0.5,
            exit_mode="ema_21",
            buffer_pts=0.0,
            max_tp_distance=30.0,
            htf=(),
            ema_runner_fraction=1.0,
        )

    class _NoStopStrategy:
        def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:
            del direction, row
            return []

        def sl_reference(self, *, direction: int, row: pd.Series) -> None:
            del direction, row
            return None

    rejected = place_strategy_order(
        _NoStopStrategy(),
        direction=1,
        entry_price=100.0,
        feat_row=pd.Series(dtype=float),
        min_dist=1.0,
        sl_fraction=0.0,
        tp_fraction=0.5,
        exit_mode="structural",
        buffer_pts=0.0,
        max_tp_distance=30.0,
        htf=(),
    )
    assert rejected.rejected is True
    assert rejected.reject_kind == "sl"
    assert rejected.sl_price is None and rejected.tp_price is None


def test_dynamic_target_obeys_the_reachable_risk_distance_boundary() -> None:
    at_cap, rejected = dynamic_tp(
        direction=1,
        entry_price=100.0,
        sl_price=95.0,
        reward_fraction=1.0,
        max_tp_distance=5.0,
    )
    assert rejected is False
    assert at_cap == pytest.approx(105.0)

    below_cap, rejected = dynamic_tp(
        direction=1,
        entry_price=100.0,
        sl_price=95.0,
        reward_fraction=1.0,
        max_tp_distance=5.0 - 2e-9,
    )
    assert below_cap is None
    assert rejected is True


def test_target_menu_admits_only_active_order_block_targets() -> None:
    row = pd.Series(
        {
            "last_swing_high": float("nan"),
            "ob_bear_high": 115.0,
            "ob_bear_active": 1.0,
        }
    )
    inactive_row = pd.Series(
        {
            "last_swing_high": float("nan"),
            "ob_bear_high": 115.0,
            "ob_bear_active": 0.0,
        }
    )

    active = target_menu(
        direction=1,
        entry_price=100.0,
        row=row,
        stop_dist=5.0,
        max_tp_distance=20.0,
        htf=(),
    )
    inactive = target_menu(
        direction=1,
        entry_price=100.0,
        row=inactive_row,
        stop_dist=5.0,
        max_tp_distance=20.0,
        htf=(),
    )

    assert active == [("ob_bear_high", 115.0, 15.0)]
    assert inactive == []


def test_target_menu_rejects_a_reference_confirmed_after_the_decision_bar() -> None:
    decision_time = pd.Timestamp("2026-01-12T12:00:00Z")
    row = pd.Series(
        {
            "last_swing_high": 110.0,
            "last_swing_high_confirmed_at": decision_time + pd.Timedelta(minutes=1),
        },
        name=decision_time,
    )

    assert (
        target_menu(
            direction=1,
            entry_price=100.0,
            row=row,
            stop_dist=5.0,
            max_tp_distance=20.0,
            htf=(),
        )
        == []
    )


def test_price_grid_collapses_equivalent_levels_and_skips_non_finite_prices() -> None:
    assert collapse_levels(
        [("first", 100.01), ("same_tick", 100.04), ("invalid", float("nan"))],
        price_increment=0.1,
    ) == [("first|same_tick", 100.01)]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"direction": 0}, "direction must be -1 or 1"),
        ({"front_run_pts": -0.1}, "front_run_pts must be finite and nonnegative"),
        ({"price_increment": 0.0}, "price_increment must be finite and positive"),
    ],
)
def test_target_menu_rejects_invalid_execution_geometry(
    options: dict[str, float],
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "direction": 1,
        "entry_price": 100.0,
        "row": pd.Series({"last_swing_high": 110.0}),
        "stop_dist": 5.0,
        "max_tp_distance": 20.0,
        "htf": (),
    }
    kwargs.update(options)

    with pytest.raises(ValueError, match=message):
        target_menu(**kwargs)  # type: ignore[arg-type]
