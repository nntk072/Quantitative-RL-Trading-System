from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from scripts.research.analysis.evidence.analyze_paired_seed_results import (
    analyze_paired_seed_metrics,
)

from evaluation.metrics.matched_comparison import MATCH_FIELDS


def _payload() -> dict[str, Any]:
    pairs = []
    for seed, delta in zip((11, 12, 13, 14, 15), (1.0, 2.0, 3.0, 4.0, 5.0), strict=True):
        common = {
            "dataset_sha256": "a" * 64,
            "split_id": "train-v1",
            "features_sha256": "b" * 64,
            "reward_sha256": "c" * 64,
            "costs_sha256": "d" * 64,
            "execution_sha256": "e" * 64,
            "timesteps": 20_000_000,
            "seed": seed,
            "initial_capital": 100_000.0,
            "model_settings_sha256": "f" * 64,
            "environment_sha256": "1" * 64,
            "evaluation_start": "2024-01-01T00:00:00Z",
            "evaluation_end": "2025-01-01T00:00:00Z",
        }
        treatment_provenance = {**common, "features_sha256": "2" * 64}
        arms = {}
        for name, provenance, return_pct in (
            ("control", common, 0.5),
            ("treatment", treatment_provenance, 0.5 + delta),
        ):
            run_id = f"{name}-seed{seed}"
            arms[name] = {
                "run_id": run_id,
                "status": "succeeded",
                "evidence_role": "matched_exploratory",
                "provenance": {**provenance, "run_id": run_id},
                "metrics": {"net_return_pct": return_pct, "trade_count": 40 + seed},
            }
        pairs.append({"seed": seed, **arms})
    return {
        "schema": "aalto.paired_seed_metrics.v1",
        "comparison_id": "rq1-control-v-treatment",
        "evidence_role": "matched_exploratory",
        "intervention_field": "features_sha256",
        "metrics": ["net_return_pct", "trade_count"],
        "expected_seeds": [11, 12, 13, 14, 15],
        "pairs": pairs,
    }


def _primary_selection_payload() -> dict[str, Any]:
    payload = _payload()
    payload["schema"] = "aalto.paired_seed_metrics.v2"
    payload["metrics"] = ["net_return_initial_equity_pct"]
    payload["intervention_field"] = "policy_sha256"
    payload["evidence_role"] = "matched_exploratory"
    payload["evaluation_exposure"] = "development"
    payload["expected_seeds"] = [11, 12, 13, 14, 15, 16]
    for pair in payload["pairs"]:
        pair["treatment"]["provenance"]["features_sha256"] = pair["control"]["provenance"][
            "features_sha256"
        ]
    pairs = payload["pairs"]
    assert isinstance(pairs, list)
    sixth = deepcopy(pairs[-1])
    sixth["seed"] = 16
    for arm_name in ("control", "treatment"):
        arm = sixth[arm_name]
        arm["run_id"] = arm["run_id"].replace("seed15", "seed16")
        arm["provenance"]["run_id"] = arm["run_id"]
        arm["provenance"]["seed"] = 16
    pairs.append(sixth)

    for index, pair in enumerate(pairs):
        seed = pair["seed"]
        pair["control"]["provenance"]["policy_sha256"] = "1" * 64
        pair["treatment"]["provenance"]["policy_sha256"] = "2" * 64
        for arm_name in ("control", "treatment"):
            arm = pair[arm_name]
            if arm_name == "control":
                arm["policy_id"] = "always_no_trade_v1"
                net_return = 0.0
            else:
                arm["policy_id"] = "candidate_policy_v1"
                net_return = float(index + 1)
            arm["evaluation_complete"] = True
            arm["hard_risk_gate_passed"] = True
            arm["initial_operating_equity"] = 100_000.0
            arm["ending_retained_equity"] = 100_000.0 * (1.0 + net_return / 100.0)
            arm["cumulative_payouts"] = 0.0
            arm["trade_count"] = 0 if arm_name == "control" else index + 1
            arm["metrics"] = {"net_return_initial_equity_pct": net_return}
            arm["provenance"]["seed"] = seed
    payload["primary_selection"] = {
        "contrast": "treatment_vs_always_no_trade",
        "metric": "net_return_initial_equity_pct",
        "alternative": "greater",
        "control_policy_id": "always_no_trade_v1",
    }
    return payload


def test_paired_seed_analysis_keeps_pairs_and_is_reproducible() -> None:
    payload = _payload()
    first = analyze_paired_seed_metrics(payload, rng_seed=9, bootstrap_draws=500)
    second = analyze_paired_seed_metrics(payload, rng_seed=9, bootstrap_draws=500)

    assert first["schema"] == "aalto.paired_seed_statistics.v1"
    assert first["n_pairs"] == 5
    assert first["metrics"] == second["metrics"]
    assert len(first["pair_lineage"]) == 5
    metrics = first["metrics"]
    assert isinstance(metrics, dict)
    result = metrics["net_return_pct"]
    assert result["mean_treatment_minus_control"] == 3.0
    assert result["sign_flip_p_value"] == 0.0625
    assert result["sign_flip_method"] == "exact two-sided paired sign-flip"
    assert [row["seed"] for row in result["seed_level_values"]] == [11, 12, 13, 14, 15]
    assert result["paired_student_t_degrees_freedom"] == 4
    assert result["paired_student_t_ci_95pct"] == pytest.approx([1.0367568, 4.9632432])
    assert result["paired_seed_bootstrap_ci_95pct"][0] <= 3.0
    assert result["paired_seed_bootstrap_ci_95pct"][1] >= 3.0


def test_paired_seed_analysis_accepts_costs_as_the_declared_intervention() -> None:
    payload = _payload()
    payload["intervention_field"] = "costs_sha256"
    for pair in payload["pairs"]:
        shared_features = pair["control"]["provenance"]["features_sha256"]
        pair["treatment"]["provenance"]["features_sha256"] = shared_features
        pair["treatment"]["provenance"]["costs_sha256"] = "e" * 64

    result = analyze_paired_seed_metrics(payload, rng_seed=9, bootstrap_draws=500)
    assert result["n_pairs"] == 5
    assert result["intervention_field"] == "costs_sha256"


def test_paired_seed_analysis_rejects_mismatched_match_fields() -> None:
    payload = _payload()
    pairs = payload["pairs"]
    assert isinstance(pairs, list)
    pairs[0]["treatment"]["provenance"]["dataset_sha256"] = "9" * 64

    with pytest.raises(ValueError, match="mismatched provenance: dataset_sha256"):
        analyze_paired_seed_metrics(payload)


def test_paired_seed_analysis_rejects_uncompleted_or_selection_runs() -> None:
    for field, value in (("status", "interrupted"), ("evidence_role", "selection")):
        payload = deepcopy(_payload())
        payload["pairs"][0]["control"][field] = value
        with pytest.raises(ValueError):
            analyze_paired_seed_metrics(payload)


def test_paired_seed_analysis_requires_five_pairs_and_full_identity() -> None:
    payload = _payload()
    payload["pairs"] = payload["pairs"][:4]
    with pytest.raises(ValueError, match="at least 5"):
        analyze_paired_seed_metrics(payload)

    payload = _payload()
    del payload["pairs"][0]["control"]["provenance"][MATCH_FIELDS[0]]
    with pytest.raises(ValueError, match="missing match provenance"):
        analyze_paired_seed_metrics(payload)


def test_paired_seed_analysis_requires_the_declared_seed_ids() -> None:
    payload = _payload()
    payload["expected_seeds"] = [101, 102, 103, 104, 105]
    with pytest.raises(ValueError, match="do not match expected_seeds"):
        analyze_paired_seed_metrics(payload)


def test_exposed_report_only_results_cannot_be_confirmatory() -> None:
    payload = _payload()
    payload["evaluation_exposure"] = "exposed_report_only"
    payload["evidence_role"] = "matched_confirmation"
    for pair in payload["pairs"]:
        pair["control"]["evidence_role"] = "matched_confirmation"
        pair["treatment"]["evidence_role"] = "matched_confirmation"
    with pytest.raises(ValueError, match="cannot be confirmatory"):
        analyze_paired_seed_metrics(payload)

    payload["evidence_role"] = "matched_exploratory"
    for pair in payload["pairs"]:
        pair["control"]["evidence_role"] = "matched_exploratory"
        pair["treatment"]["evidence_role"] = "matched_exploratory"
    result = analyze_paired_seed_metrics(payload, bootstrap_draws=100)
    assert result["evidence_role"] == "matched_exploratory"
    assert result["evaluation_exposure"] == "exposed_report_only"


def test_primary_selection_requires_six_seed_paths_and_reconciled_no_trade_control() -> None:
    payload = _primary_selection_payload()
    result = analyze_paired_seed_metrics(payload)

    assert result["schema"] == "aalto.paired_seed_statistics.v2"
    assert result["n_pairs"] == 6
    assert result["multiple_testing"] == {
        "method": "none_single_primary_contrast",
        "metric_count": 1,
    }
    primary = result["metrics"]["net_return_initial_equity_pct"]
    assert primary["sign_flip_p_value"] == pytest.approx(1 / 64)
    assert primary["sign_flip_method"] == "exact one-sided paired sign-flip (greater)"
    assert primary["holm_adjusted_p_value"] is None
    assert primary["paired_seed_bootstrap_ci_95pct"][0] > 0.0


def test_primary_selection_rejects_fewer_than_six_pairs_or_risk_breach() -> None:
    payload = _primary_selection_payload()
    payload["pairs"] = payload["pairs"][:5]
    payload["expected_seeds"] = [11, 12, 13, 14, 15]
    with pytest.raises(ValueError, match="at least 6 completed matched seed pairs"):
        analyze_paired_seed_metrics(payload)

    payload = _primary_selection_payload()
    payload["pairs"][2]["treatment"]["hard_risk_gate_passed"] = False
    with pytest.raises(ValueError, match="failed the hard-risk gate"):
        analyze_paired_seed_metrics(payload)


def test_primary_selection_rejects_wrong_control_and_unreconciled_return() -> None:
    payload = _primary_selection_payload()
    payload["pairs"][0]["control"]["policy_id"] = "random_eligible_setup_v1"
    with pytest.raises(ValueError, match="control is not always_no_trade_v1"):
        analyze_paired_seed_metrics(payload)

    payload = _primary_selection_payload()
    payload["pairs"][0]["treatment"]["cumulative_payouts"] = 500.0
    with pytest.raises(ValueError, match="full-path net return does not reconcile"):
        analyze_paired_seed_metrics(payload)


def test_primary_selection_reconciles_profit_withdrawal_without_losing_return() -> None:
    payload = _primary_selection_payload()
    treatment = payload["pairs"][0]["treatment"]
    treatment["ending_retained_equity"] = 100_000.0
    treatment["cumulative_payouts"] = 1_000.0
    treatment["metrics"]["net_return_initial_equity_pct"] = 1.0

    result = analyze_paired_seed_metrics(payload)

    assert result["metrics"]["net_return_initial_equity_pct"]["paired_seed_count"] == 6


def test_primary_selection_schema_requires_the_contract() -> None:
    payload = _primary_selection_payload()
    del payload["primary_selection"]
    with pytest.raises(ValueError, match="requires primary_selection"):
        analyze_paired_seed_metrics(payload)

    payload = _primary_selection_payload()
    payload["pairs"][0] = None
    with pytest.raises(ValueError, match=r"pairs\[0\] must be an object"):
        analyze_paired_seed_metrics(payload)

    payload = _primary_selection_payload()
    payload["evaluation_exposure"] = "untouched_holdout"
    payload["evidence_role"] = "matched_confirmation"
    for pair in payload["pairs"]:
        pair["control"]["evidence_role"] = "matched_confirmation"
        pair["treatment"]["evidence_role"] = "matched_confirmation"
    with pytest.raises(ValueError, match="development-only evaluation exposure"):
        analyze_paired_seed_metrics(payload)

    payload["evaluation_exposure"] = "development"
    with pytest.raises(ValueError, match="must remain matched_exploratory"):
        analyze_paired_seed_metrics(payload)


def test_matched_confirmation_cannot_use_the_historical_v1_schema() -> None:
    payload = _payload()
    payload["evidence_role"] = "matched_confirmation"
    for pair in payload["pairs"]:
        pair["control"]["evidence_role"] = "matched_confirmation"
        pair["treatment"]["evidence_role"] = "matched_confirmation"
    with pytest.raises(
        ValueError, match="matched confirmation requires aalto.paired_seed_metrics.v2"
    ):
        analyze_paired_seed_metrics(payload)
