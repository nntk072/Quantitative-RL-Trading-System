from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from evaluation.metrics.trade_excursions import trade_excursion_bounds


def test_long_excursion_has_equal_bounds_without_endpoint_ties() -> None:
    result = trade_excursion_bounds(
        np.asarray([10, 20, 30], dtype=np.int64),
        np.asarray([99.0, 103.0, 98.0]),
        entry_time_ns=10,
        exit_time_ns=30,
        direction=1,
        entry_price=100.0,
        entry_liquidation_price=99.5,
        exit_liquidation_price=98.0,
    )

    assert result.mfe_price_lower == result.mfe_price_upper == 3.0
    assert result.mae_price_lower == result.mae_price_upper == 2.0
    assert result.inclusive_tick_rows == 3
    assert result.strict_interior_tick_rows == 1
    assert result.entry_timestamp_tie_rows == result.exit_timestamp_tie_rows == 1


def test_short_excursion_bounds_include_unordered_endpoint_tie_rows() -> None:
    result = trade_excursion_bounds(
        np.asarray([10, 10, 20, 30, 30], dtype=np.int64),
        np.asarray([101.0, 97.0, 103.0, 99.0, 105.0]),
        entry_time_ns=10,
        exit_time_ns=30,
        direction=-1,
        entry_price=100.0,
        entry_liquidation_price=101.0,
        exit_liquidation_price=99.0,
    )

    assert result.mfe_price_lower == 1.0
    assert result.mfe_price_upper == 3.0
    assert result.mae_price_lower == 3.0
    assert result.mae_price_upper == 5.0
    assert result.entry_timestamp_tie_rows == result.exit_timestamp_tie_rows == 2


@pytest.mark.parametrize(
    ("timestamps", "prices", "kwargs", "message"),
    [
        (
            np.asarray([20, 10], dtype=np.int64),
            np.asarray([100.0, 101.0]),
            {},
            "sorted",
        ),
        (
            np.asarray([10, 20], dtype=np.int64),
            np.asarray([100.0, 101.0]),
            {"direction": 0},
            "direction",
        ),
    ],
)
def test_trade_excursion_rejects_invalid_inputs(
    timestamps: NDArray[np.int64],
    prices: NDArray[np.float64],
    kwargs: dict[str, int],
    message: str,
) -> None:
    parameters = {
        "entry_time_ns": 10,
        "exit_time_ns": 20,
        "direction": 1,
        "entry_price": 100.0,
        "entry_liquidation_price": 99.0,
        "exit_liquidation_price": 99.0,
        **kwargs,
    }
    with pytest.raises(ValueError, match=message):
        trade_excursion_bounds(timestamps, prices, **parameters)  # type: ignore[arg-type]
