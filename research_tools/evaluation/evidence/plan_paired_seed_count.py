#!/usr/bin/env python3
"""Plan a fixed paired-seed count from a declared effect and paired SD."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "paired_seed_count_plan.v1"


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the continued fraction used by the regularized beta function."""
    max_iterations = 300
    epsilon = 3e-14
    floor = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < floor:
        d = floor
    d = 1.0 / d
    result = d
    for iteration in range(1, max_iterations + 1):
        even = 2 * iteration
        coefficient = iteration * (b - iteration) * x / ((qam + even) * (a + even))
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / ((a + even) * (qap + even))
        d = 1.0 + coefficient * d
        if abs(d) < floor:
            d = floor
        c = 1.0 + coefficient / c
        if abs(c) < floor:
            c = floor
        d = 1.0 / d
        multiplier = d * c
        result *= multiplier
        if abs(multiplier - 1.0) < epsilon:
            return result
    raise ArithmeticError("regularized beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    """Evaluate the regularized incomplete beta function for positive shapes."""
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValueError("regularized beta inputs are outside their domains")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    log_front += a * math.log(x) + b * math.log1p(-x)
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    """Evaluate the central Student-t CDF using the regularized beta function."""
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    if value == 0.0:
        return 0.5
    beta_x = degrees_of_freedom / (degrees_of_freedom + value * value)
    tail = 0.5 * _regularized_beta(beta_x, degrees_of_freedom / 2.0, 0.5)
    return tail if value < 0.0 else 1.0 - tail


def _student_t_upper_critical(alpha: float, degrees_of_freedom: int) -> float:
    """Find the one-sided central-t critical value by bounded bisection."""
    lower = 0.0
    upper = 1.0
    while _student_t_cdf(upper, degrees_of_freedom) < 1.0 - alpha:
        upper *= 2.0
    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        if _student_t_cdf(midpoint, degrees_of_freedom) < 1.0 - alpha:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _noncentral_t_power(*, standardized_effect: float, pairs: int, alpha: float) -> float:
    """Integrate the noncentral-t rejection probability over its chi-square scale."""
    degrees_of_freedom = pairs - 1
    critical_value = _student_t_upper_critical(alpha, degrees_of_freedom)
    noncentrality = standardized_effect * math.sqrt(pairs)
    shape = degrees_of_freedom / 2.0
    log_normalizer = shape * math.log(2.0) + math.lgamma(shape)
    upper = degrees_of_freedom + 14.0 * math.sqrt(2.0 * degrees_of_freedom) + 50.0
    intervals = 4096
    step = upper / intervals
    weighted_sum = 0.0
    for index in range(intervals + 1):
        chi_square = index * step
        if chi_square == 0.0:
            density = 0.0
        else:
            log_density = (shape - 1.0) * math.log(chi_square)
            log_density -= chi_square / 2.0 + log_normalizer
            density = math.exp(log_density)
        normal_tail = 0.5 * math.erfc(
            (critical_value * math.sqrt(chi_square / degrees_of_freedom) - noncentrality)
            / math.sqrt(2.0)
        )
        coefficient = 1.0 if index in {0, intervals} else (4.0 if index % 2 else 2.0)
        weighted_sum += coefficient * density * normal_tail
    power = weighted_sum * step / 3.0
    return min(1.0, max(0.0, power))


def plan_paired_seed_count(
    *,
    minimum_effect: float,
    paired_standard_deviation: float,
    minimum_effect_source: str,
    paired_standard_deviation_source: str,
    target_power: float = 0.8,
    alpha: float = 0.05,
    minimum_pairs: int = 6,
    maximum_pairs: int = 1000,
) -> dict[str, Any]:
    """Find the smallest fixed pair count meeting approximate one-sided power.

    The calculation integrates the paired noncentral-t rejection probability
    with Simpson's rule. It plans a fixed count only; confirmatory inference
    remains the preregistered paired sign-flip test and paired-seed bootstrap.
    """
    values = {
        "minimum_effect": minimum_effect,
        "paired_standard_deviation": paired_standard_deviation,
        "target_power": target_power,
        "alpha": alpha,
    }
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values.values()
    ):
        raise ValueError("power inputs must be finite")
    if minimum_effect <= 0.0:
        raise ValueError("minimum_effect must be positive")
    if not isinstance(minimum_effect_source, str) or not isinstance(
        paired_standard_deviation_source, str
    ):
        raise ValueError("input provenance references must be non-empty strings")
    provenance = {
        "minimum_effect": minimum_effect_source.strip(),
        "paired_standard_deviation": paired_standard_deviation_source.strip(),
    }
    if not all(provenance.values()):
        raise ValueError("input provenance references must be non-empty")
    if paired_standard_deviation < 0.0:
        raise ValueError("paired_standard_deviation cannot be negative")
    if not 0.0 < alpha < 0.5:
        raise ValueError("alpha must be between 0 and 0.5")
    if not alpha < target_power < 1.0:
        raise ValueError("target_power must be greater than alpha and below one")
    if isinstance(minimum_pairs, bool) or not isinstance(minimum_pairs, int) or minimum_pairs < 6:
        raise ValueError("minimum_pairs must be an integer of at least six")
    if (
        isinstance(maximum_pairs, bool)
        or not isinstance(maximum_pairs, int)
        or maximum_pairs < minimum_pairs
    ):
        raise ValueError("maximum_pairs must be an integer at least minimum_pairs")

    selected_pairs: int
    selected_power: float
    if paired_standard_deviation == 0.0:
        selected_pairs = minimum_pairs
        selected_power = 1.0
    else:
        standardized_effect = minimum_effect / paired_standard_deviation
        selected_pairs = minimum_pairs
        selected_power = _noncentral_t_power(
            standardized_effect=standardized_effect,
            pairs=selected_pairs,
            alpha=alpha,
        )
        while selected_power < target_power and selected_pairs < maximum_pairs:
            selected_pairs += 1
            selected_power = _noncentral_t_power(
                standardized_effect=standardized_effect,
                pairs=selected_pairs,
                alpha=alpha,
            )
        if selected_power < target_power:
            raise ValueError(
                f"target power was not reached by maximum_pairs={maximum_pairs}; "
                "increase the bound or revise the declared design inputs"
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "planned",
        "method": "one-sided paired noncentral-t power approximation",
        "assumption": "paired differences are approximately normally distributed",
        "inputs": {
            "minimum_effect": float(minimum_effect),
            "paired_standard_deviation": float(paired_standard_deviation),
            "target_power": float(target_power),
            "alpha": float(alpha),
            "minimum_pairs": minimum_pairs,
            "maximum_pairs": maximum_pairs,
        },
        "input_provenance": provenance,
        "planned_pair_count": selected_pairs,
        "estimated_power_at_planned_count": float(selected_power),
        "confirmatory_test": "one-sided paired sign-flip test",
        "confirmatory_interval": "paired-seed bootstrap percentile 95% interval",
        "campaign_authorized": False,
        "limitations": [
            "The noncentral-t calculation uses numerical Simpson integration and does not replace exact power for the discrete sign-flip statistic.",
            "Provenance references are caller-supplied and are not independently verified by this planner.",
            "The fixed count must be frozen before confirmatory outcomes are inspected.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-effect", type=float, required=True)
    parser.add_argument("--paired-standard-deviation", type=float, required=True)
    parser.add_argument("--minimum-effect-source", required=True)
    parser.add_argument("--paired-standard-deviation-source", required=True)
    parser.add_argument("--target-power", type=float, default=0.8)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--minimum-pairs", type=int, default=6)
    parser.add_argument("--maximum-pairs", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = plan_paired_seed_count(
        minimum_effect=args.minimum_effect,
        paired_standard_deviation=args.paired_standard_deviation,
        minimum_effect_source=args.minimum_effect_source,
        paired_standard_deviation_source=args.paired_standard_deviation_source,
        target_power=args.target_power,
        alpha=args.alpha,
        minimum_pairs=args.minimum_pairs,
        maximum_pairs=args.maximum_pairs,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
