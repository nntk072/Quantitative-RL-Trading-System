"""Paired evaluation with explicit, matching research-run provenance."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from .bootstrap import (
    CI,
    max_drawdown_stat,
    paired_metric_difference_ci,
    sharpe_stat,
    sortino_stat,
)

MATCH_FIELDS = (
    "dataset_sha256",
    "split_id",
    "features_sha256",
    "reward_sha256",
    "costs_sha256",
    "execution_sha256",
    "timesteps",
    "seed",
    "initial_capital",
    "model_settings_sha256",
    "environment_sha256",
    "evaluation_start",
    "evaluation_end",
)

# A matched intervention may change exactly one declared design dimension.
# Dataset, split, reward, execution, budget, seed, capital, model settings and
# evaluation window remain identical for a cost sensitivity comparison.
INTERVENTION_FIELDS = frozenset(
    {"features_sha256", "reward_sha256", "environment_sha256", "costs_sha256"}
)


def compare_matched_returns(
    treatment: pd.Series,
    control: pd.Series,
    treatment_provenance: Mapping[str, Any],
    control_provenance: Mapping[str, Any],
    *,
    intervention_field: str | None = None,
    n_boot: int = 2000,
    level: float = 0.95,
    rng_seed: int = 42,
) -> CI:
    """Paired mean return difference only when the declared conditions match.

    Requires genuinely timestamp-aligned returns and independently recorded
    provenance. A comparison of a previously inspected holdout is not evidence
    of a new untouched OOS evaluation. When an intervention is declared, its
    provenance field must be one of the supported design dimensions and must
    differ between arms; every other required field still has to match.

    Args:
        treatment: Tabular data used for the treatment.
        control: Tabular data used for the control.
        treatment_provenance: Key-value data used for the treatment provenance.
        control_provenance: Key-value data used for the control provenance.
        intervention_field: Intervention field used by the operation described above.
        n_boot: Numeric value used for the n boot.
        level: Numeric value used for the level.
        rng_seed: Numeric value used for the rng seed.

    Returns:
        Result of paired mean return difference only when the declared conditions match.
    """
    if intervention_field is not None and intervention_field not in INTERVENTION_FIELDS:
        raise ValueError(f"Unsupported comparison intervention field: {intervention_field}")
    for field in MATCH_FIELDS:
        left = treatment_provenance.get(field)
        right = control_provenance.get(field)
        if field == intervention_field:
            if (
                left is None
                or right is None
                or left == right
                or (isinstance(left, str) and not left.strip())
                or (isinstance(right, str) and not right.strip())
            ):
                raise ValueError(
                    f"Declared intervention must have distinct, non-empty provenance: {field}"
                )
            continue
        if (
            left is None
            or right is None
            or left != right
            or (isinstance(left, str) and not left.strip())
            or (isinstance(right, str) and not right.strip())
        ):
            raise ValueError(f"Missing or mismatched comparison provenance: {field}")
    if not isinstance(treatment.index, pd.DatetimeIndex) or not isinstance(
        control.index, pd.DatetimeIndex
    ):
        raise ValueError("Paired series require timestamp indexes")  # noqa: TRY004 - existing API contract
    if treatment.index.hasnans or control.index.hasnans:
        raise ValueError("Paired timestamps must not be missing")
    if not treatment.index.is_monotonic_increasing or not control.index.is_monotonic_increasing:
        raise ValueError("Paired timestamps must be chronologically ordered")
    if not treatment.index.is_unique or not control.index.is_unique:
        raise ValueError("Paired series index must have unique timestamps")
    if not treatment.index.equals(control.index):
        raise ValueError("Paired series index must match exactly")
    if len(treatment) == 0:
        raise ValueError("Paired comparison requires at least one return observation")
    try:
        declared_start = pd.Timestamp(treatment_provenance["evaluation_start"])
        declared_end = pd.Timestamp(treatment_provenance["evaluation_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid declared evaluation period") from exc
    if declared_start != treatment.index[0] or declared_end != treatment.index[-1]:
        raise ValueError("Declared evaluation period must match the return index endpoints")
    if len(treatment) == 1:
        raise ValueError("Paired bootstrap comparison requires at least two return observations")
    if n_boot <= 0:
        raise ValueError("n_boot must be positive for a confidence interval")
    if not np.isfinite(level) or not 0.0 < level < 1.0:
        raise ValueError("Confidence level must be finite and strictly between zero and one")
    return paired_metric_difference_ci(
        np.asarray(treatment, dtype=np.float64),
        np.asarray(control, dtype=np.float64),
        np.mean,
        n_boot=n_boot,
        level=level,
        rng_seed=rng_seed,
    )


def paired_equity_metric_differences(
    treatment: pd.Series,
    control: pd.Series,
    *,
    initial_balance: float,
    periods_per_year: int,
    n_boot: int = 2000,
    level: float = 0.95,
    rng_seed: int = 42,
    block_len: int = 8,
) -> dict[str, CI]:
    """Estimate paired time-series metric differences for timestamp-matched equity.

    The same moving-block indices are applied to both arms. Results describe
    within-path uncertainty conditional on this evaluation and the supplied
    policy action seeds; they do not estimate between-seed variation.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    left_path, right_path = _paired_equity_paths(treatment, control, initial_balance)
    if left_path.size < 3:
        raise ValueError("Paired bootstrap requires at least two aligned bar returns")
    left_returns = np.diff(left_path) / left_path[:-1]
    right_returns = np.diff(right_path) / right_path[:-1]

    def drawdown_from_returns(returns: NDArray[np.float64]) -> float:
        path = np.concatenate(([initial_balance], initial_balance * np.cumprod(1.0 + returns)))
        return max_drawdown_stat(path)

    metrics: dict[str, Callable[[NDArray[np.float64]], float]] = {
        "mean_bar_return": lambda returns: float(np.mean(returns)),
        "sharpe": lambda returns: sharpe_stat(returns, periods_per_year),
        "sortino": lambda returns: sortino_stat(returns, periods_per_year),
        "max_drawdown": drawdown_from_returns,
    }
    return {
        name: paired_metric_difference_ci(
            left_returns,
            right_returns,
            statistic,
            n_boot=n_boot,
            level=level,
            rng_seed=rng_seed,
            block_len=block_len,
        )
        for name, statistic in metrics.items()
    }


def _paired_equity_return_observation_count(
    treatment: pd.Series,
    control: pd.Series,
    *,
    initial_balance: float,
) -> int:
    """Validate matched equity paths and count their aligned bar returns."""
    left_path, _ = _paired_equity_paths(treatment, control, initial_balance)
    return left_path.size - 1


def _paired_equity_paths(
    treatment: pd.Series,
    control: pd.Series,
    initial_balance: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Validate timestamp-matched equity and prepend common starting capital."""
    for name, series in (("treatment", treatment), ("control", control)):
        if not isinstance(series, pd.Series):
            raise TypeError(f"{name} equity must be a pandas Series")
        if not isinstance(series.index, pd.DatetimeIndex):
            raise ValueError("Paired equity requires timestamp indexes")
        if series.index.hasnans or not series.index.is_monotonic_increasing:
            raise ValueError("Paired equity timestamps must be present and chronological")
        if not series.index.is_unique:
            raise ValueError("Paired equity timestamps must be unique")
    if not treatment.index.equals(control.index):
        raise ValueError("Paired equity indexes must match exactly")
    if not np.isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("initial_balance must be finite and positive")
    if treatment.empty:
        raise ValueError("Paired equity requires at least one observation")
    left = treatment.to_numpy(dtype=np.float64)
    right = control.to_numpy(dtype=np.float64)
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Paired equity values must be finite")
    if np.any(left <= 0) or np.any(right <= 0):
        raise ValueError("Paired equity values must be positive")
    if (left[0] == initial_balance) != (right[0] == initial_balance):
        raise ValueError("Paired equity paths must use the same initial-capital convention")

    left_path = left if left[0] == initial_balance else np.concatenate(([initial_balance], left))
    right_path = (
        right if right[0] == initial_balance else np.concatenate(([initial_balance], right))
    )
    return left_path, right_path
