#!/usr/bin/env python3
"""Summarize provenance-matched seed pairs without treating bars as seeds.

The percentile interval resamples paired seeds. It is separate from the
moving-block within-path interval in ``evaluation.metrics.bootstrap``.
The exact sign-flip test tests a zero-centered paired mean under sign symmetry;
it is not a substitute for validity, selection, or holdout gates.

The v1 schema remains available for historical/descriptive analysis with its
five-pair floor. The v2 primary-selection schema requires an always-no-trade
control, at least six prospectively fixed pairs, complete risk-passing paths,
and a net-return metric reconciled to ending equity plus cumulative payouts.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from evaluation.metrics.matched_comparison import INTERVENTION_FIELDS, MATCH_FIELDS

BOOTSTRAP_DRAWS = 10_000
EXACT_SIGN_FLIP_MAX_PAIRS = 15
MONTE_CARLO_SIGN_FLIP_DRAWS = 100_000
MIN_PAIRED_SEEDS = 5
MIN_PRIMARY_SELECTION_SEEDS = 6
EVIDENCE_ROLES = frozenset({"matched_confirmation", "matched_exploratory", "robustness"})


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the incomplete-beta continued fraction (Numerical Recipes form)."""
    max_iterations = 200
    epsilon = 3.0e-14
    minimum = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < minimum:
        d = minimum
    d = 1.0 / d
    result = d
    for iteration in range(1, max_iterations + 1):
        m2 = 2 * iteration
        aa = iteration * (b - iteration) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + aa / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        result *= d * c
        aa = -(a + iteration) * (qab + iteration) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + aa / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) <= epsilon:
            return result
    raise ArithmeticError("incomplete-beta continued fraction did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _beta_continued_fraction(a, b, x) / a
    return 1.0 - factor * _beta_continued_fraction(b, a, 1.0 - x) / b


def _student_t_cdf(value: float, degrees_freedom: int) -> float:
    if degrees_freedom <= 0:
        raise ValueError("Student-t degrees of freedom must be positive")
    if value == 0.0:
        return 0.5
    x = degrees_freedom / (degrees_freedom + value * value)
    tail = 0.5 * _regularized_incomplete_beta(x, degrees_freedom / 2.0, 0.5)
    return 1.0 - tail if value > 0.0 else tail


def _student_t_critical_value(probability: float, degrees_freedom: int) -> float:
    """Invert the Student-t CDF without an undeclared SciPy dependency."""
    if not 0.5 < probability < 1.0:
        raise ValueError("Student-t quantile probability must be between 0.5 and 1")
    low = 0.0
    high = 1.0
    while _student_t_cdf(high, degrees_freedom) < probability:
        high *= 2.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        if _student_t_cdf(midpoint, degrees_freedom) < probability:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2.0


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def _validate_pair_input(
    payload: Any,
) -> tuple[
    str,
    str,
    list[int],
    dict[str, NDArray[np.float64]],
    dict[str, NDArray[np.float64]],
]:
    if not isinstance(payload, dict):
        raise ValueError("input must be an object")
    schema = payload.get("schema")
    if schema not in {"aalto.paired_seed_metrics.v1", "aalto.paired_seed_metrics.v2"}:
        raise ValueError("input schema must be aalto.paired_seed_metrics.v1 or v2")
    is_primary_schema = schema == "aalto.paired_seed_metrics.v2"
    comparison_id = payload.get("comparison_id")
    if not isinstance(comparison_id, str) or not comparison_id.strip():
        raise ValueError("comparison_id must be a non-empty string")
    intervention = payload.get("intervention_field")
    if intervention not in INTERVENTION_FIELDS:
        raise ValueError(f"unsupported intervention_field: {intervention!r}")
    evidence_role = payload.get("evidence_role")
    if evidence_role is not None and evidence_role not in EVIDENCE_ROLES:
        raise ValueError(f"unsupported evidence_role: {evidence_role!r}")
    if (
        payload.get("evaluation_exposure") == "exposed_report_only"
        and evidence_role != "matched_exploratory"
    ):
        raise ValueError("exposed report-only results cannot be confirmatory evidence")
    expected_seeds = payload.get("expected_seeds")
    if expected_seeds is not None and (
        not isinstance(expected_seeds, list)
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in expected_seeds)
        or len(expected_seeds) != len(set(expected_seeds))
    ):
        raise ValueError("expected_seeds must be a list of unique integer seed IDs")
    metrics = payload.get("metrics")
    if (
        not isinstance(metrics, list)
        or not metrics
        or any(not isinstance(name, str) or not name.strip() for name in metrics)
        or len(set(metrics)) != len(metrics)
    ):
        raise ValueError("metrics must be a non-empty list of unique names")
    pairs = payload.get("pairs")
    minimum_pairs = MIN_PRIMARY_SELECTION_SEEDS if is_primary_schema else MIN_PAIRED_SEEDS
    if not isinstance(pairs, list) or len(pairs) < minimum_pairs:
        raise ValueError(f"at least {minimum_pairs} completed matched seed pairs are required")
    if evidence_role == "matched_confirmation" and not is_primary_schema:
        raise ValueError("matched confirmation requires aalto.paired_seed_metrics.v2")
    primary_selection = payload.get("primary_selection")
    if not is_primary_schema and primary_selection is not None:
        raise ValueError("primary_selection requires aalto.paired_seed_metrics.v2")
    if is_primary_schema and primary_selection is None:
        raise ValueError("aalto.paired_seed_metrics.v2 requires primary_selection")
    if is_primary_schema:
        if expected_seeds is None:
            raise ValueError("primary selection requires the prospectively fixed expected_seeds")
        if not isinstance(primary_selection, dict):
            raise ValueError("primary_selection must be an object")
        if primary_selection.get("contrast") != "treatment_vs_always_no_trade":
            raise ValueError("primary selection contrast must be treatment_vs_always_no_trade")
        if primary_selection.get("metric") != "net_return_initial_equity_pct":
            raise ValueError("primary selection metric must be net_return_initial_equity_pct")
        if primary_selection.get("alternative") != "greater":
            raise ValueError("primary selection alternative must be greater")
        if primary_selection.get("control_policy_id") != "always_no_trade_v1":
            raise ValueError("primary selection control must be always_no_trade_v1")
        if intervention != "policy_sha256":
            raise ValueError("primary selection must declare policy_sha256 as its intervention")
        if metrics != ["net_return_initial_equity_pct"]:
            raise ValueError(
                "primary selection payload must contain only the "
                "net_return_initial_equity_pct metric"
            )
        exposure = payload.get("evaluation_exposure")
        if exposure != "development":
            raise ValueError("primary selection requires development-only evaluation exposure")
        if evidence_role != "matched_exploratory":
            raise ValueError("primary selection results must remain matched_exploratory")
        initial_equities: set[float] = set()
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                raise ValueError(f"pairs[{index}] must be an object")
            control = pair.get("control")
            treatment = pair.get("treatment")
            if not isinstance(control, dict) or not isinstance(treatment, dict):
                raise ValueError(f"pairs[{index}] is missing a control or treatment arm")
            if control.get("policy_id") != "always_no_trade_v1":
                raise ValueError(f"pairs[{index}] control is not always_no_trade_v1")
            for arm_name, arm in (("control", control), ("treatment", treatment)):
                if arm.get("evaluation_complete") is not True:
                    raise ValueError(f"pairs[{index}] {arm_name} path is incomplete")
                if arm.get("hard_risk_gate_passed") is not True:
                    raise ValueError(f"pairs[{index}] {arm_name} path failed the hard-risk gate")
                provenance = arm.get("provenance")
                if not isinstance(provenance, dict):
                    raise ValueError(f"pairs[{index}] {arm_name} is missing provenance")
                initial = _finite_number(
                    arm.get("initial_operating_equity"),
                    field=f"pairs[{index}].{arm_name}.initial_operating_equity",
                )
                provenance_initial = _finite_number(
                    provenance.get("initial_capital"),
                    field=f"pairs[{index}].{arm_name}.provenance.initial_capital",
                )
                if not math.isclose(initial, provenance_initial, rel_tol=1e-12, abs_tol=1e-9):
                    raise ValueError(
                        f"pairs[{index}] {arm_name} starting equity does not match provenance"
                    )
                initial_equities.add(initial)
                retained = _finite_number(
                    arm.get("ending_retained_equity"),
                    field=f"pairs[{index}].{arm_name}.ending_retained_equity",
                )
                payouts = _finite_number(
                    arm.get("cumulative_payouts"),
                    field=f"pairs[{index}].{arm_name}.cumulative_payouts",
                )
                if initial <= 0.0 or payouts < 0.0:
                    raise ValueError(f"pairs[{index}] {arm_name} account summary is invalid")
                if arm_name == "control":
                    trade_count = arm.get("trade_count")
                    if isinstance(trade_count, bool) or trade_count != 0:
                        raise ValueError(f"pairs[{index}] no-trade control has trades")
                    if not math.isclose(retained, initial, rel_tol=1e-12, abs_tol=1e-9):
                        raise ValueError(
                            f"pairs[{index}] no-trade control did not retain initial equity"
                        )
                    if payouts != 0.0:
                        raise ValueError(f"pairs[{index}] no-trade control recorded a payout")
                expected_return = 100.0 * (retained + payouts - initial) / initial
                arm_metrics = arm.get("metrics")
                if not isinstance(arm_metrics, dict):
                    raise ValueError(f"pairs[{index}] {arm_name} metrics must be an object")
                recorded_return = _finite_number(
                    arm_metrics.get("net_return_initial_equity_pct"),
                    field=f"pairs[{index}].{arm_name}.net_return_initial_equity_pct",
                )
                if not math.isclose(expected_return, recorded_return, rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError(
                        f"pairs[{index}] {arm_name} full-path net return does not reconcile"
                    )
        if len(initial_equities) != 1:
            raise ValueError("primary selection paths must share one initial operating equity")

    seen_seeds: set[int] = set()
    seen_run_ids: set[str] = set()
    seen_roles: set[str] = set()
    treatment_values: dict[str, list[float]] = {name: [] for name in metrics}
    control_values: dict[str, list[float]] = {name: [] for name in metrics}
    seeds: list[int] = []
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            raise ValueError(f"pairs[{index}] must be an object")
        seed = pair.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed in seen_seeds:
            raise ValueError(f"pairs[{index}].seed must be a unique integer")
        seen_seeds.add(seed)
        seeds.append(seed)
        arms: dict[str, dict[str, Any]] = {}
        for arm_name in ("control", "treatment"):
            arm_record = pair.get(arm_name)
            if not isinstance(arm_record, dict):
                raise ValueError(f"pairs[{index}].{arm_name} must be an object")
            run_id = arm_record.get("run_id")
            if not isinstance(run_id, str) or not run_id.strip() or run_id in seen_run_ids:
                raise ValueError(f"pairs[{index}].{arm_name}.run_id must be unique and non-empty")
            seen_run_ids.add(run_id)
            if arm_record.get("status") != "succeeded":
                raise ValueError(f"run {run_id} is not succeeded")
            arm_role = arm_record.get("evidence_role")
            if arm_role not in EVIDENCE_ROLES:
                raise ValueError(f"run {run_id} has an unsupported evidence role")
            seen_roles.add(arm_role)
            if evidence_role is not None and arm_role != evidence_role:
                raise ValueError(f"run {run_id} evidence role does not match the comparison")
            provenance = arm_record.get("provenance")
            if not isinstance(provenance, dict):
                raise ValueError(f"run {run_id} is missing provenance")
            missing = [field for field in MATCH_FIELDS if field not in provenance]
            if intervention not in MATCH_FIELDS and intervention not in provenance:
                missing.append(intervention)
            if missing:
                raise ValueError(f"run {run_id} is missing match provenance: {missing}")
            if provenance["seed"] != seed:
                raise ValueError(f"run {run_id} seed does not match pair seed")
            if "run_id" in provenance and provenance["run_id"] != run_id:
                raise ValueError(f"run {run_id} provenance identity mismatch")
            if (
                "evidence_role" in provenance
                and provenance["evidence_role"] != arm_record["evidence_role"]
            ):
                raise ValueError(f"run {run_id} evidence role mismatch")
            arms[arm_name] = {
                "run_id": run_id,
                "provenance": provenance,
                "metrics": arm_record.get("metrics"),
            }

        left = arms["control"]["provenance"]
        right = arms["treatment"]["provenance"]
        for field in MATCH_FIELDS:
            left_value, right_value = left[field], right[field]
            if field == intervention:
                if (
                    left_value == right_value
                    or left_value in (None, "")
                    or right_value in (None, "")
                ):
                    raise ValueError(f"declared intervention must differ: {field}")
            elif left_value != right_value or left_value in (None, ""):
                raise ValueError(f"paired runs have missing or mismatched provenance: {field}")
        if intervention not in MATCH_FIELDS:
            left_value = left.get(intervention)
            right_value = right.get(intervention)
            if left_value in (None, "") or right_value in (None, "") or left_value == right_value:
                raise ValueError(f"declared intervention must differ: {intervention}")

        for arm_name, destination in (("control", control_values), ("treatment", treatment_values)):
            arm_metrics = arms[arm_name]["metrics"]
            if not isinstance(arm_metrics, dict):
                raise ValueError(f"run {arms[arm_name]['run_id']} is missing metrics")
            if set(arm_metrics) != set(metrics):
                raise ValueError(f"run {arms[arm_name]['run_id']} metric names do not match input")
            for metric in metrics:
                destination[metric].append(
                    _finite_number(
                        arm_metrics[metric], field=f"{arms[arm_name]['run_id']}.{metric}"
                    )
                )

    controls = {metric: np.asarray(control_values[metric], dtype=np.float64) for metric in metrics}
    treatments = {
        metric: np.asarray(treatment_values[metric], dtype=np.float64) for metric in metrics
    }
    if expected_seeds is not None and seeds != expected_seeds:
        raise ValueError(f"completed seed IDs do not match expected_seeds: {seeds}")
    if len(seen_roles) != 1:
        raise ValueError("all paired runs must use the same evidence role")
    return comparison_id, intervention, seeds, controls, treatments


def _sign_flip_p_value(
    differences: NDArray[np.float64], *, rng_seed: int, alternative: str = "two-sided"
) -> tuple[float, str]:
    if alternative not in {"two-sided", "greater", "less"}:
        raise ValueError("alternative must be two-sided, greater, or less")
    observed_mean = float(differences.mean())
    observed = abs(observed_mean) if alternative == "two-sided" else observed_mean
    n = len(differences)
    if alternative == "greater" and observed_mean <= 0.0:
        return 1.0, "one-sided paired sign-flip (greater)"
    if alternative == "less" and observed_mean >= 0.0:
        return 1.0, "one-sided paired sign-flip (less)"

    def is_extreme(mean: float) -> bool:
        if alternative == "greater":
            return mean >= observed - 1e-12
        if alternative == "less":
            return mean <= observed + 1e-12
        return abs(mean) >= observed - 1e-12

    if n <= EXACT_SIGN_FLIP_MAX_PAIRS:
        extreme = sum(
            is_extreme(float(np.mean(differences * signs)))
            for signs in itertools.product((-1.0, 1.0), repeat=n)
        )
        label = (
            "exact two-sided paired sign-flip"
            if alternative == "two-sided"
            else f"exact one-sided paired sign-flip ({alternative})"
        )
        return extreme / (2**n), label
    rng = np.random.default_rng(rng_seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(MONTE_CARLO_SIGN_FLIP_DRAWS, n))
    means = (signs * differences).mean(axis=1)
    if alternative == "greater":
        extreme = int(np.count_nonzero(means >= observed - 1e-12))
    elif alternative == "less":
        extreme = int(np.count_nonzero(means <= observed + 1e-12))
    else:
        extreme = int(np.count_nonzero(np.abs(means) >= observed - 1e-12))
    label = (
        "Monte Carlo two-sided paired sign-flip"
        if alternative == "two-sided"
        else f"Monte Carlo one-sided paired sign-flip ({alternative})"
    )
    return (extreme + 1) / (MONTE_CARLO_SIGN_FLIP_DRAWS + 1), label


def _holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * value))
        adjusted[name] = running
    return adjusted


def analyze_paired_seed_metrics(
    payload: Any, *, rng_seed: int = 42, bootstrap_draws: int = BOOTSTRAP_DRAWS
) -> dict[str, Any]:
    if bootstrap_draws <= 0:
        raise ValueError("bootstrap_draws must be positive")
    comparison_id, intervention, seeds, controls, treatments = _validate_pair_input(payload)
    primary_selection = payload.get("primary_selection")
    if primary_selection is not None and (rng_seed != 42 or bootstrap_draws != BOOTSTRAP_DRAWS):
        raise ValueError("primary selection requires 10,000 bootstrap draws with RNG seed 42")
    rng = np.random.default_rng(rng_seed)
    raw_p: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for metric, treatment in treatments.items():
        control = controls[metric]
        values = treatment - control
        degrees_freedom = len(values) - 1
        sample_sd = float(values.std(ddof=1))
        standard_error = sample_sd / float(np.sqrt(len(values)))
        critical_value = _student_t_critical_value(0.975, degrees_freedom)
        mean_difference = float(values.mean())
        sample_indices = rng.integers(0, len(values), size=(bootstrap_draws, len(values)))
        bootstrap_means = values[sample_indices].mean(axis=1)
        alternative = (
            str(primary_selection["alternative"]) if primary_selection is not None else "two-sided"
        )
        p_value, p_method = _sign_flip_p_value(values, rng_seed=rng_seed, alternative=alternative)
        raw_p[metric] = p_value
        rows[metric] = {
            "paired_seed_count": len(values),
            "seeds": seeds,
            "seed_level_values": [
                {
                    "seed": seed,
                    "control": float(control_value),
                    "treatment": float(treatment_value),
                    "difference": float(difference),
                }
                for seed, control_value, treatment_value, difference in zip(
                    seeds, control, treatment, values, strict=True
                )
            ],
            "mean_treatment_minus_control": mean_difference,
            "median_treatment_minus_control": float(np.median(values)),
            "sd_of_paired_differences": sample_sd,
            "paired_student_t_degrees_freedom": degrees_freedom,
            "paired_student_t_critical_value_95pct": critical_value,
            "paired_student_t_standard_error": standard_error,
            "paired_student_t_ci_95pct": [
                mean_difference - critical_value * standard_error,
                mean_difference + critical_value * standard_error,
            ],
            "min_paired_difference": float(values.min()),
            "max_paired_difference": float(values.max()),
            "paired_seed_bootstrap_ci_95pct": [
                float(x) for x in np.quantile(bootstrap_means, [0.025, 0.975])
            ],
            "sign_flip_p_value": p_value,
            "sign_flip_method": p_method,
        }
    if primary_selection is None:
        adjusted_p = _holm_adjust(raw_p)
        for metric, row in rows.items():
            row["holm_adjusted_p_value"] = adjusted_p[metric]
        multiple_testing = {"method": "Holm", "metric_count": len(rows)}
    else:
        for row in rows.values():
            row["holm_adjusted_p_value"] = None
        multiple_testing = {"method": "none_single_primary_contrast", "metric_count": 1}
    pair_lineage = [
        {
            "seed": pair["seed"],
            **{
                arm_name: {
                    "run_id": pair[arm_name]["run_id"],
                    "status": pair[arm_name]["status"],
                    "evidence_role": pair[arm_name]["evidence_role"],
                    "provenance": pair[arm_name]["provenance"],
                }
                for arm_name in ("control", "treatment")
            },
        }
        for pair in payload["pairs"]
    ]
    report = {
        "schema": (
            "aalto.paired_seed_statistics.v2"
            if primary_selection is not None
            else "aalto.paired_seed_statistics.v1"
        ),
        "comparison_id": comparison_id,
        "intervention_field": intervention,
        "evidence_role": payload.get("evidence_role")
        or payload["pairs"][0]["control"]["evidence_role"],
        "evaluation_exposure": payload.get("evaluation_exposure"),
        "expected_seeds": payload.get("expected_seeds"),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "n_pairs": len(seeds),
        "pair_lineage": pair_lineage,
        "bootstrap": {"unit": "paired_seed", "draws": bootstrap_draws, "rng_seed": rng_seed},
        "multiple_testing": multiple_testing,
        "metrics": rows,
        "interpretation_limits": [
            "The interval resamples paired seeds; it does not represent within-path temporal uncertainty.",
            "Use the moving-block paired-return analysis separately for temporal-path uncertainty.",
            "This tool does not verify holdout freshness, selection discipline, full-split exposure, or raw metric reconstruction.",
            "A small number of seeds yields coarse intervals and discrete exact-test p-values; report the seed-level differences.",
            "A sign-flip test assumes symmetry of paired differences under its null and does not establish causality by itself.",
        ],
    }
    if primary_selection is not None:
        report["primary_selection"] = primary_selection
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Matched seed-pair JSON")
    parser.add_argument("--output", required=True, type=Path, help="New statistics JSON path")
    parser.add_argument("--seed", type=int, default=42, help="Bootstrap/sign-flip RNG seed")
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace statistics output: {args.output}")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = analyze_paired_seed_metrics(
        payload, rng_seed=args.seed, bootstrap_draws=args.bootstrap_draws
    )
    report["input_path"] = str(args.input.resolve())
    report["input_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "n_pairs": report["n_pairs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
