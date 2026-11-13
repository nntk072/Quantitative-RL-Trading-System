"""Paired-seed statistics for research experiments."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PairedStatistics:
    """Prospectively registered paired-seed inference result."""

    mean_difference: float
    sign_flip_p_value: float
    bootstrap_lower: float
    bootstrap_upper: float
    pair_count: int

    @property
    def positive(self) -> bool:
        """Return whether all registered superiority criteria are satisfied.

        Returns:
            Result produced by positive.
        """
        return (
            self.mean_difference > 0.0
            and self.sign_flip_p_value < 0.05
            and self.bootstrap_lower > 0.0
        )


def paired_differences(treatment: Iterable[float], control: Iterable[float]) -> NDArray[np.float64]:
    """Return finite treatment-minus-control differences with equal cardinality.

    Args:
        treatment: Treatment values paired by independent seed.
        control: Control values paired by independent seed.

    Returns:
        Result produced by paired_differences.
    """
    treatment_values = np.asarray(tuple(treatment), dtype=np.float64)
    control_values = np.asarray(tuple(control), dtype=np.float64)
    if treatment_values.shape != control_values.shape or treatment_values.ndim != 1:
        raise ValueError("paired samples must be one-dimensional and equally sized")
    if treatment_values.size < 1 or not np.isfinite(treatment_values).all():
        raise ValueError("treatment sample must contain finite values")
    if not np.isfinite(control_values).all():
        raise ValueError("control sample must contain finite values")
    return treatment_values - control_values


def exact_sign_flip_greater(differences: NDArray[np.float64], *, max_pairs: int = 15) -> float:
    """Return the exact one-sided paired sign-flip p-value.

    Args:
        differences: Paired treatment-minus-control differences.
        max_pairs: Largest pair count allowed for exact enumeration.

    Returns:
        Result produced by exact_sign_flip_greater.
    """
    if differences.ndim != 1 or differences.size < 1:
        raise ValueError("sign-flip differences must be a non-empty vector")
    if differences.size > max_pairs:
        raise ValueError("exact sign-flip pair count exceeds the registered limit")
    observed = float(np.mean(differences))
    if observed <= 0.0:
        return 1.0
    exceed = 0
    total = 0
    values = tuple(float(value) for value in differences)
    for signs in product((-1.0, 1.0), repeat=len(values)):
        statistic = float(np.mean(np.multiply(values, signs)))
        total += 1
        if statistic >= observed - 1e-15:
            exceed += 1
    return exceed / total


def paired_bootstrap_interval(
    differences: NDArray[np.float64],
    *,
    samples: int = 10_000,
    seed: int = 42,
) -> tuple[float, float]:
    """Return the registered percentile interval for the paired-seed mean.

    Args:
        differences: Paired treatment-minus-control differences.
        samples: Number of bootstrap resamples.
        seed: Random seed used for deterministic sampling.

    Returns:
        Result produced by paired_bootstrap_interval.
    """
    if differences.ndim != 1 or differences.size < 1:
        raise ValueError("bootstrap differences must be a non-empty vector")
    if samples < 1:
        raise ValueError("bootstrap sample count must be positive")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, differences.size, size=(samples, differences.size))
    means = np.mean(differences[indices], axis=1)
    lower, upper = np.quantile(means, (0.025, 0.975))
    return float(lower), float(upper)


def analyze_paired_seeds(
    treatment: Iterable[float],
    control: Iterable[float],
    *,
    bootstrap_samples: int = 10_000,
    rng_seed: int = 42,
) -> PairedStatistics:
    """Compute the registered paired statistics for up to fifteen seeds.

    Args:
        treatment: Treatment values paired by independent seed.
        control: Control values paired by independent seed.
        bootstrap_samples: Number of paired bootstrap resamples.
        rng_seed: Random seed used by the statistical procedure.

    Returns:
        Result produced by analyze_paired_seeds.
    """
    differences = paired_differences(treatment, control)
    p_value = exact_sign_flip_greater(differences)
    lower, upper = paired_bootstrap_interval(
        differences,
        samples=bootstrap_samples,
        seed=rng_seed,
    )
    return PairedStatistics(
        mean_difference=float(np.mean(differences)),
        sign_flip_p_value=p_value,
        bootstrap_lower=lower,
        bootstrap_upper=upper,
        pair_count=int(differences.size),
    )


__all__ = [
    "PairedStatistics",
    "analyze_paired_seeds",
    "exact_sign_flip_greater",
    "paired_bootstrap_interval",
    "paired_differences",
]
