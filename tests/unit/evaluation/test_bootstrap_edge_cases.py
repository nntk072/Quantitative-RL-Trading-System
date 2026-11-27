"""Bootstrap inputs fail clearly and preserve short-sample contracts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from evaluation.metrics.bootstrap import (
    bootstrap_ci,
    metrics_with_ci,
    paired_metric_difference_ci,
    sharpe_stat,
    sortino_stat,
)


@pytest.mark.parametrize(
    ("n_boot", "level", "block_len", "message"),
    [
        (True, 0.95, 1, "n_boot"),
        (-1, 0.95, 1, "n_boot"),
        (2, 0.0, 1, "level"),
        (2, float("nan"), 1, "level"),
        (2, 0.95, 0, "block_len"),
    ],
)
def test_bootstrap_rejects_invalid_resampling_parameters(
    n_boot: int, level: float, block_len: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        bootstrap_ci(np.asarray([1.0, 2.0]), np.mean, n_boot, level, block_len=block_len)


def test_bootstrap_short_empty_and_nonfinite_statistic_paths() -> None:
    empty = bootstrap_ci(np.asarray([]), np.mean, n_boot=4)
    assert math.isnan(empty.estimate) and math.isnan(empty.lower) and math.isnan(empty.upper)

    one = bootstrap_ci(np.asarray([3.0]), np.mean, n_boot=4)
    assert one.as_tuple() == (3.0, 3.0, 3.0)
    no_resamples = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=0)
    assert no_resamples.as_tuple() == (2.0, 2.0, 2.0)

    short_blocks = bootstrap_ci(np.asarray([1.0, 3.0]), np.mean, n_boot=5, block_len=8)
    assert short_blocks.estimate == pytest.approx(2.0)
    all_nan = bootstrap_ci(np.asarray([1.0, 2.0]), lambda _values: float("nan"), n_boot=3)
    assert math.isnan(all_nan.lower) and math.isnan(all_nan.upper)


def test_paired_bootstrap_uses_aligned_series_and_short_sample_conventions() -> None:
    def stat(values: np.ndarray[Any, Any]) -> float:
        return float(np.mean(values))

    empty = paired_metric_difference_ci(np.asarray([]), np.asarray([]), stat)
    assert math.isnan(empty.estimate)
    exact = paired_metric_difference_ci(np.asarray([3.0]), np.asarray([1.0]), stat, n_boot=4)
    assert exact.as_tuple() == (2.0, 2.0, 2.0)
    no_resamples = paired_metric_difference_ci(
        np.asarray([2.0, 4.0]), np.asarray([1.0, 1.0]), stat, n_boot=0
    )
    assert no_resamples.as_tuple() == (2.0, 2.0, 2.0)
    sampled = paired_metric_difference_ci(
        np.asarray([2.0, 4.0]), np.asarray([1.0, 1.0]), stat, n_boot=8, block_len=8
    )
    assert sampled.lower == pytest.approx(sampled.upper)

    with pytest.raises(ValueError, match="same length"):
        paired_metric_difference_ci(np.asarray([1.0]), np.asarray([1.0, 2.0]), stat)


def test_bootstrap_metric_wrappers_validate_inputs_and_initial_balance() -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        sharpe_stat(np.asarray([1.0]), periods_per_year=0)
    with pytest.raises(ValueError, match="periods_per_year"):
        sortino_stat(np.asarray([1.0]), periods_per_year=0)
    with pytest.raises(ValueError, match="one-dimensional"):
        sharpe_stat(np.asarray([[1.0, 2.0]]))
    with pytest.raises(ValueError, match="finite"):
        sortino_stat(np.asarray([float("nan")]))

    with pytest.raises(ValueError, match="must be positive"):
        metrics_with_ci(np.asarray([0.0, 1.0]), np.asarray([]))
    with pytest.raises(ValueError, match="initial_balance"):
        metrics_with_ci(np.asarray([100.0, 101.0]), np.asarray([]), initial_balance=0.0)
    with pytest.raises(ValueError, match="periods_per_year"):
        metrics_with_ci(np.asarray([100.0]), np.asarray([]), periods_per_year=0)
    with pytest.raises(ValueError, match="equity_curve.*finite"):
        metrics_with_ci(np.asarray([100.0, float("nan")]), np.asarray([]))
    with pytest.raises(ValueError, match="trade_pnls.*finite"):
        metrics_with_ci(np.asarray([100.0, 101.0]), np.asarray([float("inf")]))

    result = metrics_with_ci(
        np.asarray([98.0, 101.0, 100.0]),
        np.asarray([1.0, -1.0]),
        periods_per_year=12,
        n_boot=8,
        initial_balance=100.0,
    )
    assert set(result) == {"sharpe", "sortino", "max_drawdown", "win_rate"}
    assert result["max_drawdown"].estimate == pytest.approx(0.02)
