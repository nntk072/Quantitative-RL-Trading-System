"""Prospective primary comparison between the qualified policy and no-trade control."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from artifacts.identity import file_sha256
from evaluation.metrics.matched_comparison import MATCH_FIELDS
from experiments.research.statistics import analyze_paired_seeds

EXPECTED_SEEDS = (42, 43, 44, 45, 46, 47)


def _finite(value: Any, label: str) -> float:
    """Return a finite numeric value or fail closed.

    Args:
        value: Value to validate or transform.
        label: Field label used in validation errors.

    Returns:
        Result produced by _finite.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _arm(value: Any, *, seed: int, control: bool) -> dict[str, Any]:
    """Validate and normalize one matched-comparison arm.

    Args:
        value: Value to validate or transform.
        seed: Random seed used for deterministic sampling.
        control: Control values paired by independent seed.

    Returns:
        Result produced by _arm.
    """
    if not isinstance(value, dict):
        raise ValueError("pair arm must be an object")
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("pair arm requires provenance")
    missing = [field for field in MATCH_FIELDS if field not in provenance]
    if missing:
        raise ValueError(f"pair arm missing provenance fields: {missing}")
    if provenance.get("seed") != seed:
        raise ValueError("pair arm provenance seed mismatch")
    policy_sha = provenance.get("policy_sha256")
    if not isinstance(policy_sha, str) or len(policy_sha) != 64:
        raise ValueError("pair arm requires policy_sha256")
    if (
        value.get("evaluation_complete") is not True
        or value.get("hard_risk_gate_passed") is not True
    ):
        raise ValueError("primary comparison requires complete hard-risk-safe paths")
    initial = _finite(value.get("initial_operating_equity"), "initial_operating_equity")
    retained = _finite(value.get("ending_retained_equity"), "ending_retained_equity")
    payouts = _finite(value.get("cumulative_payouts"), "cumulative_payouts")
    trades = value.get("trade_count")
    if isinstance(trades, bool) or not isinstance(trades, int) or trades < 0:
        raise ValueError("trade_count must be a nonnegative integer")
    if control:
        if value.get("policy_id") != "always_no_trade_v1":
            raise ValueError("primary control must be always_no_trade_v1")
        if (
            trades != 0
            or payouts != 0.0
            or not math.isclose(retained, initial, rel_tol=1e-12, abs_tol=1e-9)
        ):
            raise ValueError("no-trade control must retain capital with zero trades/payouts")
    declared = _finite(
        value.get("net_return_initial_equity_pct"),
        "net_return_initial_equity_pct",
    )
    reconciled = 100.0 * (retained + payouts - initial) / initial
    if not math.isclose(declared, reconciled, rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("declared net return does not reconcile")
    sources = value.get("source_artifacts")
    if not isinstance(sources, list) or not sources:
        raise ValueError("pair arm requires source artifacts")
    verified: list[dict[str, str]] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("source artifact row must be an object")
        path = Path(str(source.get("path", ""))).expanduser().resolve()
        digest = source.get("sha256")
        if not path.is_file() or digest != file_sha256(path):
            raise ValueError(f"source artifact identity mismatch: {path}")
        verified.append({"path": str(path), "sha256": str(digest)})
    return {
        **value,
        "provenance": dict(provenance),
        "source_artifacts": verified,
        "net_return_initial_equity_pct": declared,
    }


def build_primary_payload(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact six paired development paths and matched provenance.

    Args:
        spec: Source specification to validate.

    Returns:
        Result produced by build_primary_payload.
    """
    if spec.get("schema_version") != 1:
        raise ValueError("unsupported primary-pair source schema")
    if spec.get("evaluation_exposure") != "development":
        raise ValueError("primary selection must use development exposure")
    if tuple(spec.get("expected_seeds", ())) != EXPECTED_SEEDS:
        raise ValueError(f"expected_seeds must be exactly {list(EXPECTED_SEEDS)}")
    pairs = spec.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != len(EXPECTED_SEEDS):
        raise ValueError("primary comparison requires exactly six pairs")
    by_seed: dict[int, dict[str, Any]] = {}
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("pair must be an object")
        seed = pair.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed in by_seed:
            raise ValueError("pair seeds must be unique integers")
        by_seed[seed] = pair
    if tuple(sorted(by_seed)) != EXPECTED_SEEDS:
        raise ValueError("pair seeds differ from the prospective seed set")
    built: list[dict[str, Any]] = []
    for seed in EXPECTED_SEEDS:
        control = _arm(by_seed[seed].get("control"), seed=seed, control=True)
        treatment = _arm(by_seed[seed].get("treatment"), seed=seed, control=False)
        for field in MATCH_FIELDS:
            if control["provenance"][field] != treatment["provenance"][field]:
                raise ValueError(f"seed {seed} unmatched provenance: {field}")
        if control["provenance"]["policy_sha256"] == treatment["provenance"]["policy_sha256"]:
            raise ValueError(f"seed {seed} policy intervention does not differ")
        built.append({"seed": seed, "control": control, "treatment": treatment})
    return {
        "schema_version": 1,
        "comparison_id": str(spec.get("comparison_id", "qualified_policy_vs_always_no_trade")),
        "evaluation_exposure": "development",
        "metric": "net_return_initial_equity_pct",
        "alternative": "greater",
        "expected_seeds": list(EXPECTED_SEEDS),
        "pairs": built,
    }


def analyze_primary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the registered exact sign-flip and paired-seed bootstrap.

    Args:
        payload: Normalized comparison payload.

    Returns:
        Result produced by analyze_primary_payload.
    """
    pairs = payload.get("pairs")
    if payload.get("schema_version") != 1 or not isinstance(pairs, list):
        raise ValueError("invalid primary comparison payload")
    treatment = [
        _finite(pair["treatment"]["net_return_initial_equity_pct"], "treatment return")
        for pair in pairs
    ]
    control = [
        _finite(pair["control"]["net_return_initial_equity_pct"], "control return")
        for pair in pairs
    ]
    statistics = analyze_paired_seeds(treatment, control)
    all_safe = all(
        pair["treatment"]["hard_risk_gate_passed"] is True
        and pair["control"]["hard_risk_gate_passed"] is True
        for pair in pairs
    )
    positive = all_safe and statistics.positive
    return {
        "schema_version": 1,
        "status": "positive" if positive else "negative_or_inconclusive",
        "pair_count": statistics.pair_count,
        "mean_difference_pct": statistics.mean_difference,
        "exact_sign_flip_p_value": statistics.sign_flip_p_value,
        "paired_bootstrap_95pct": [statistics.bootstrap_lower, statistics.bootstrap_upper],
        "all_paths_hard_risk_safe": all_safe,
        "positive_primary_result": positive,
    }


__all__ = ["EXPECTED_SEEDS", "analyze_primary_payload", "build_primary_payload"]
