"""Bootstrap confidence intervals for performance metrics (Chain D).

Resamples bar-level returns (stationary bootstrap preserves mild
autocorrelation) and trade PnLs to produce percentile confidence
intervals for Sharpe, Sortino, max drawdown and win rate. Multiple
seeds per variant are the primary uncertainty reduction; these CIs
quantify within-run sampling error on top of that.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .performance import (
    DEFAULT_PERIODS_PER_YEAR,
    _sharpe,
    _sortino,
    _trade_stats,
    max_drawdown,
)


def _validate_bootstrap_parameters(n_boot: int, level: float, block_len: int) -> None:
    """Reject invalid interval settings before handling empty or short samples."""
    if isinstance(n_boot, bool) or not isinstance(n_boot, (int, np.integer)) or n_boot < 0:
        raise ValueError("n_boot must be a nonnegative integer")
    if not np.isfinite(level) or not 0.0 < level < 1.0:
        raise ValueError("level must be finite and between 0 and 1")
    if isinstance(block_len, bool) or not isinstance(block_len, (int, np.integer)) or block_len < 1:
        raise ValueError("block_len must be a positive integer")


def _finite_vector(values: NDArray[np.float64], name: str) -> NDArray[np.float64]:
    """Return a finite one-dimensional float vector or raise a clear error."""
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


@dataclass(frozen=True)
class CI:
    """A percentile confidence interval."""

    estimate: float
    lower: float
    upper: float
    level: float

    def as_tuple(self) -> tuple[float, float, float]:
        """Return the lower and upper confidence limits as a pair.

        Returns:
            Values returned by ``as_tuple``, in the declared order.
        """
        return (self.lower, self.estimate, self.upper)


def bootstrap_ci(
    values: NDArray[np.float64],
    stat_fn: Callable[[NDArray[np.float64]], float],
    n_boot: int = 2000,
    level: float = 0.95,
    rng_seed: int = 42,
    block_len: int = 8,
) -> CI:
    """Percentile bootstrap CI for ``stat_fn(values)``.

    Uses a moving-block bootstrap (blocks of ``block_len``) so mild
    autocorrelation in bar returns is preserved rather than destroyed
    by an i.i.d. resample.

    Args:
        values: Values to process, in input order.
        stat_fn: Stat fn used by the operation described above.
        n_boot: Numeric value used for the n boot.
        level: Numeric value used for the level.
        rng_seed: Numeric value used for the rng seed.
        block_len: Numeric value used for the block len.

    Returns:
        Result of percentile bootstrap CI for ``stat_fn(values)``.
    """
    _validate_bootstrap_parameters(n_boot, level, block_len)
    arr = _finite_vector(values, "values")
    n = arr.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(arr))
    if n == 1 or n_boot == 0:
        return CI(estimate, estimate, estimate, level)

    # Moving-block starts require ``n - block_len + 1 > 0``; shrink the block
    # when the sample is shorter than the requested block.
    block_len = min(int(block_len), n)
    rng = np.random.default_rng(rng_seed)
    n_blocks = int(np.ceil(n / block_len))
    starts = rng.integers(0, n - block_len + 1, size=(n_boot, n_blocks))
    stats = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        pieces = [arr[s : s + block_len] for s in starts[b]]
        sample = np.concatenate(pieces)[:n]
        stats[b] = stat_fn(sample)
    stats = stats[np.isfinite(stats)]
    if stats.size == 0:
        return CI(estimate, float("nan"), float("nan"), level)

    alpha = (1.0 - level) / 2.0
    lo, hi = np.percentile(stats, [100 * alpha, 100 * (1 - alpha)])
    return CI(estimate, float(lo), float(hi), level)


def paired_metric_difference_ci(
    treatment_returns: NDArray[np.float64],
    control_returns: NDArray[np.float64],
    stat_fn: Callable[[NDArray[np.float64]], float],
    n_boot: int = 2000,
    level: float = 0.95,
    rng_seed: int = 42,
    block_len: int = 8,
) -> CI:
    """Moving-block CI for treatment minus control on aligned returns.

    Each bootstrap draw selects the *same* contiguous time blocks for both
    series.  The caller must supply matching periods from matched systems;
    this is within-path uncertainty, separate from paired-seed uncertainty.

    Args:
        treatment_returns: Treatment returns used by the operation described above.
        control_returns: Control returns used by the operation described above.
        stat_fn: Stat fn used by the operation described above.
        n_boot: Numeric value used for the n boot.
        level: Numeric value used for the level.
        rng_seed: Numeric value used for the rng seed.
        block_len: Numeric value used for the block len.

    Returns:
        Result of moving-block CI for treatment minus control on aligned returns.
    """
    _validate_bootstrap_parameters(n_boot, level, block_len)
    treatment = _finite_vector(treatment_returns, "treatment_returns")
    control = _finite_vector(control_returns, "control_returns")
    if treatment.ndim != 1 or control.ndim != 1 or treatment.size != control.size:
        raise ValueError("Paired return series must be one-dimensional and have the same length")
    n = treatment.size
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), level)
    estimate = float(stat_fn(treatment) - stat_fn(control))
    if n == 1 or n_boot == 0:
        return CI(estimate, estimate, estimate, level)

    block_len = min(int(block_len), n)
    rng = np.random.default_rng(rng_seed)
    n_blocks = int(np.ceil(n / block_len))
    starts = rng.integers(0, n - block_len + 1, size=(n_boot, n_blocks))
    stats = np.empty(n_boot, dtype=np.float64)
    for i, row in enumerate(starts):
        indices = np.concatenate([np.arange(s, s + block_len) for s in row])[:n]
        stats[i] = stat_fn(treatment[indices]) - stat_fn(control[indices])
    finite = stats[np.isfinite(stats)]
    if finite.size == 0:
        return CI(estimate, float("nan"), float("nan"), level)
    alpha = (1.0 - level) / 2.0
    lo, hi = np.percentile(finite, [100.0 * alpha, 100.0 * (1.0 - alpha)])
    return CI(estimate, float(lo), float(hi), level)


def sharpe_stat(
    returns: NDArray[np.float64], periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Sharpe of bar returns (annualisation matching evaluation/metrics).

    Args:
        returns: Returns used by the operation described above.
        periods_per_year: Numeric value used for the periods per year.

    Returns:
        Numeric result returned by ``sharpe_stat``.
    """
    r = _finite_vector(returns, "returns")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return _sharpe(r, periods_per_year)


def sortino_stat(
    returns: NDArray[np.float64], periods_per_year: int = DEFAULT_PERIODS_PER_YEAR
) -> float:
    """Sortino of bar returns (downside deviation vs. zero).

    Args:
        returns: Returns used by the operation described above.
        periods_per_year: Numeric value used for the periods per year.

    Returns:
        Numeric result returned by ``sortino_stat``.
    """
    r = _finite_vector(returns, "returns")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    return _sortino(r, periods_per_year)


def max_drawdown_stat(equity: NDArray[np.float64]) -> float:
    """Peak-to-trough equity decline as a positive fraction.

    Args:
        equity: Current account equity in account currency.

    Returns:
        Numeric result returned by ``max_drawdown_stat``.
    """
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size == 0:
        return float("nan")
    return max_drawdown(eq)


def win_rate_stat(trade_pnls: NDArray[np.float64]) -> float:
    """Fraction of winning trades.

    Args:
        trade_pnls: Trade pnls used by the operation described above.

    Returns:
        Numeric result returned by ``win_rate_stat``.
    """
    pnls = np.asarray(trade_pnls, dtype=np.float64)
    if pnls.size == 0:
        return float("nan")
    return _trade_stats(pnls)["win_rate"]


def metrics_with_ci(
    equity_curve: NDArray[np.float64],
    trade_pnls: NDArray[np.float64],
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
    n_boot: int = 2000,
    level: float = 0.95,
    rng_seed: int = 42,
    initial_balance: float | None = None,
) -> dict[str, CI]:
    """Bootstrap CIs for Sharpe/Sortino (bar returns) and MDD/win-rate.

    Max drawdown resamples contiguous blocks of returns, then reconstructs
    each equity path from the original initial equity. Resampling equity
    *levels* would create impossible crashes in monotonic runs.

    Args:
        equity_curve: Equity curve used by the operation described above.
        trade_pnls: Trade pnls used by the operation described above.
        periods_per_year: Numeric value used for the periods per year.
        n_boot: Numeric value used for the n boot.
        level: Numeric value used for the level.
        rng_seed: Numeric value used for the rng seed.
        initial_balance: Initial balance used by the operation described above.

    Returns:
        Mapping from ``str`` keys to ``CI`` values.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    _validate_bootstrap_parameters(n_boot, level, 1)
    eq = _finite_vector(equity_curve, "equity_curve")
    pnls = _finite_vector(trade_pnls, "trade_pnls")
    if np.any(eq <= 0.0):
        raise ValueError("equity_curve values must be positive")
    if initial_balance is not None:
        if not np.isfinite(initial_balance) or initial_balance <= 0:
            raise ValueError("initial_balance must be finite and positive")
        if eq.size and eq[0] != initial_balance:
            eq = np.concatenate(([float(initial_balance)], eq))
    rets = np.diff(eq) / eq[:-1] if eq.size > 1 else np.array([])

    def reconstructed_drawdown(sample: NDArray[np.float64]) -> float:
        """Rebuild an equity path from sampled returns and measure drawdown.

        Args:
            sample: Sample used by the operation described above.

        Returns:
            Numeric result returned by ``reconstructed_drawdown``.
        """
        if eq.size == 0:
            return float("nan")
        path = np.empty(sample.size + 1, dtype=np.float64)
        path[0] = eq[0]
        path[1:] = eq[0] * np.cumprod(1.0 + sample)
        return max_drawdown_stat(path)

    mdd_ci = bootstrap_ci(rets, reconstructed_drawdown, n_boot, level, rng_seed)
    # Bootstrap estimate should describe the observed path, including the
    # initial-capital observation and its first loss.
    mdd_ci = CI(max_drawdown_stat(eq), mdd_ci.lower, mdd_ci.upper, mdd_ci.level)
    return {
        "sharpe": bootstrap_ci(
            rets, lambda r: sharpe_stat(r, periods_per_year), n_boot, level, rng_seed
        ),
        "sortino": bootstrap_ci(
            rets, lambda r: sortino_stat(r, periods_per_year), n_boot, level, rng_seed
        ),
        "max_drawdown": mdd_ci,
        "win_rate": bootstrap_ci(pnls, win_rate_stat, n_boot, level, rng_seed),
    }
