from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypedDict, cast

import numpy as np
import pandas as pd
import pytest
from scripts.research.analysis.evidence.verify_result_manifest import validate_result_manifest

from configuration.configuration_loader import load_config
from decisioning.trade_setup import build_trade_setup_action_schema, trade_setup_candidate_id
from evaluation.reporting.matched_setup_baseline_bundle import (
    write_matched_setup_baseline_bundle,
)
from evaluation.rollout.matched_setup_baselines import (
    ExistingPolicyArm,
    RuleSetupBaselineArm,
    evaluate_tier0_setup_baselines,
)
from evaluation.rollout.random_eligible_setup import (
    AlwaysNoTradePolicy,
    AlwaysNoTradeRolloutModel,
    RandomEligibleSetupPolicy,
    RandomEligibleSetupRolloutModel,
)
from evaluation.rollout.structure_priority_setup import (
    StructurePrioritySetupPolicy,
    StructurePrioritySetupRolloutModel,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns

ROOT = Path(__file__).resolve().parents[3]


class _BootstrapOverrides(TypedDict, total=False):
    bootstrap_samples: int
    bootstrap_level: float
    bootstrap_seed: int


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2025-01-06 16:30", periods=24, freq="1min", tz="Etc/GMT-3")
    close = np.full(len(index), 20_000.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 2.0,
            "low": close - 2.0,
            "close": close,
            "spread": 0.6,
            "session_id": 0,
        },
        index=index,
    )
    features = pd.DataFrame(
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["entry_idea_fvg_retest_M5_long"] = 1.0
    features["M5_fvg_bull_retest_confirmed_at_time_ns"] = float(index[0].value)
    features["M5_fvg_bull_retest_origin_time_ns"] = float(index[0].value - 300_000_000_000)
    features["last_swing_low"] = close - 20.0
    features["last_swing_high"] = close + 40.0
    for name in (
        "asian_high",
        "asian_low",
        "sweep_high",
        "sweep_low",
        "po3_manipulation_low",
        "po3_manipulation_high",
        "po3_manipulation_end",
        "po3_distribution",
        "ifvg_bull_low",
        "ifvg_bull_high",
        "ifvg_bear_low",
        "ifvg_bear_high",
    ):
        features[name] = 0.0
    return bars, features


def test_tier0_baselines_share_resolved_inputs_but_separate_seeds() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
            "evaluation.periods_per_year=100",
        ]
    )
    bars, features = _synthetic_inputs()

    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
    )

    assert set(outputs) == {"always_no_trade", "random_eligible_setup"}
    flat, random = outputs.values()
    assert flat["trade_fill_event_ledger"].empty
    assert flat["decisions"]["trade_setup_candidate_id"].eq(0).all()
    assert flat["policy_metadata"]["execution_seed"] == 41
    assert flat["policy_metadata"]["risk_sizing"]["risk_mode"] == "dynamic"
    assert (
        "current equity multiplied"
        in flat["policy_metadata"]["risk_sizing"]["risk_budget_semantics"]
    )
    assert flat["policy_metadata"]["random_policy_seed"] is None
    assert random["policy_metadata"]["execution_seed"] == 41
    assert random["policy_metadata"]["random_policy_seed"] == 7
    assert flat["policy_metadata"]["action_schema"] == random["policy_metadata"]["action_schema"]
    assert (
        flat["policy_metadata"]["resolved_config_sha256"]
        == random["policy_metadata"]["resolved_config_sha256"]
    )
    assert flat["policy_metadata"]["bars_rows"] == len(bars)
    assert random["policy_metadata"]["features_rows"] == len(features)
    assert random["decisions"]["decision_id"].notna().all()
    assert (
        random["policy_metadata"]["matched_input_bundle"]
        == flat["policy_metadata"]["matched_input_bundle"]
    )
    assert "sharpe" in random["metrics"].__dataclass_fields__
    assert len(flat["equity"]) == len(random["equity"])
    for output in (flat, random):
        uncertainty = output["confidence_intervals"]
        assert uncertainty["schema"] == "within_trajectory_bootstrap_ci_v1"
        assert uncertainty["n_boot"] == 2000
        assert uncertainty["scope"].startswith("within-trajectory sampling")
        assert set(uncertainty["metrics"]) == {"sharpe", "sortino", "max_drawdown", "win_rate"}
    assert np.isnan(random["confidence_intervals"]["metrics"]["win_rate"]["estimate"])
    assert random["confidence_intervals"]["metrics"]["max_drawdown"]["estimate"] == pytest.approx(
        random["metrics"].max_drawdown
    )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("bootstrap_samples", 0, "positive integer"),
        ("bootstrap_level", 1.0, "between 0 and 1"),
        ("bootstrap_seed", -1, "non-negative integer"),
    ],
)
def test_tier0_bootstrap_parameters_are_validated(name: str, value: object, message: str) -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()
    options: _BootstrapOverrides = {"bootstrap_samples": 10}
    if name == "bootstrap_samples":
        options["bootstrap_samples"] = cast(int, value)
    elif name == "bootstrap_level":
        options["bootstrap_level"] = cast(float, value)
    else:
        options["bootstrap_seed"] = cast(int, value)
    with pytest.raises(ValueError, match=message):
        evaluate_tier0_setup_baselines(
            cfg,
            bars,
            features,
            None,
            execution_seed=41,
            random_policy_seed=7,
            period_role="synthetic",
            **options,
        )


def test_matched_runner_accepts_deterministic_structure_rule_without_checkpoint(
    tmp_path: Path,
) -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "env.obs_window=1",
            "env.risk_mode=dollar_band",
            "env.risk_band_max_usd=500",
            "costs.use_tick_execution=false",
            "evaluation.periods_per_year=100",
        ]
    )
    bars, features = _synthetic_inputs()
    schema = build_trade_setup_action_schema(
        has_sl_mode=bool(cfg.env.allow_agent_sl_mode),
        has_tp_mode=bool(cfg.env.allow_agent_tp_mode),
        has_multi_tp=bool(cfg.env.allow_multi_tp),
        has_simplex=bool(cfg.env.allow_multi_tp and cfg.env.allow_simplex),
    )
    rule_model = StructurePrioritySetupRolloutModel(
        StructurePrioritySetupPolicy(
            schema,
            idea_priority=("fvg_retest",),
            timeframe_priority=("M5",),
            normalized_risk=0.5,
        )
    )
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={"priority_fvg": RuleSetupBaselineArm(rule_model)},
    )

    result = outputs["priority_fvg"]
    expected_candidate = trade_setup_candidate_id("fvg_retest", "M5", 1)

    assert result["policy_metadata"]["policy_source"] == "deterministic_rule"
    assert result["policy_metadata"]["policy_id"] == "structure_priority_setup_v1"
    assert result["policy_metadata"]["action_schema"] == schema.to_dict()
    assert result["policy_metadata"]["risk_sizing"]["policy_risk_coordinate_is_constant"] is True
    assert set(result["decisions"]["trade_setup_candidate_id"]) == {expected_candidate}

    bundle_path = write_matched_setup_baseline_bundle(
        outputs,
        cfg,
        bars,
        features,
        None,
        output_root=tmp_path / "evidence/research/structure_priority_baseline",
        artifact_root=tmp_path,
        source_repository=ROOT,
        config_path=ROOT / "config/base/default.yaml",
        protocol_path="docs/research/setup_conditioned_reasoning_benchmark_protocol.md",
        regeneration_command=(
            "pytest tests/integration/evaluation/test_matched_setup_baselines.py"
        ),
        symbols=("SYNTHETIC",),
        timeframes=("M1", "M5"),
    )
    manifest = json.loads((bundle_path / "result_manifest.json").read_text(encoding="utf-8"))
    schema_document = json.loads(
        (ROOT / "schemas/research_result_manifest_v2.schema.json").read_text(encoding="utf-8")
    )

    assert validate_result_manifest(manifest, schema_document, repo_root=tmp_path) == []
    rule_run = next(
        run for run in manifest["runs"] if run["variant_id"] == "structure_priority_setup_v1"
    )
    assert rule_run["role"] == "deterministic_rule"
    assert rule_run["identity"]["checkpoint_hash"]["status"] == "unknown"


def test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "env.obs_window=1",
            "env.risk_mode=dollar_band",
            "env.risk_band_max_usd=500",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
        normalized_risk=1.0,
        absolute_risk_budget_usd=250.0,
    )
    for name, result in outputs.items():
        sizing = result["policy_metadata"]["risk_sizing"]
        assert sizing["risk_mode"] == "dollar_band"
        assert sizing["risk_band_max_usd"] == 250.0
        assert sizing["policy_normalized_risk"] == (1.0 if name == "random_eligible_setup" else 0.0)
        assert sizing["policy_risk_coordinate_is_constant"] is True
        assert sizing["absolute_risk_budget_usd"] == 250.0
        assert "reserves modeled execution costs" in sizing["risk_budget_semantics"]
        assert sizing["configured_static_trade_risk_cap_usd"] == 900.0

    random_ledger = outputs["random_eligible_setup"]["trade_fill_event_ledger"]
    random_opens = random_ledger.loc[random_ledger["type"].eq("open")]
    assert not random_opens.empty
    assert random_opens["approved_risk_usd"].le(250.0).all()
    reserved_stop_risk = (
        random_opens["modeled_stop_risk_usd"] + random_opens["execution_reserve_usd"]
    )
    assert reserved_stop_risk.le(random_opens["approved_risk_usd"] + 1e-6).all()

    schema_record = outputs["always_no_trade"]["policy_metadata"]["action_schema"]
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=bool(schema_record["has_sl_mode"]),
        has_tp_mode=bool(schema_record["has_tp_mode"]),
        has_multi_tp=bool(schema_record["has_multi_tp"]),
        has_simplex=bool(schema_record["has_simplex"]),
    )
    existing = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        normalized_risk=1.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=RandomEligibleSetupRolloutModel(
                    RandomEligibleSetupPolicy(
                        action_schema,
                        seed=9,
                        normalized_risk=1.0,
                    )
                ),
                metadata={
                    "policy_id": "synthetic_policy",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "checkpoint_source_key": "checkpoint",
                    "training_seed": 3,
                    "training_total_steps": 10,
                    "policy_action_mode": "stochastic",
                    "policy_action_seed": 9,
                    "action_schema": action_schema.to_dict(),
                },
            )
        },
    )
    assert (
        existing["existing_policy"]["policy_metadata"]["risk_sizing"]["risk_band_max_usd"] == 250.0
    )
    existing_ledger = existing["existing_policy"]["trade_fill_event_ledger"]
    existing_opens = existing_ledger.loc[existing_ledger["type"].eq("open")]
    assert not existing_opens.empty
    assert existing_opens["approved_risk_usd"].le(250.0).all()


def test_existing_policy_rejects_action_schema_mismatch() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()
    actual_schema = build_trade_setup_action_schema(
        has_sl_mode=False,
        has_tp_mode=False,
        has_multi_tp=False,
        has_simplex=False,
    ).to_dict()
    incompatible_schema = {**actual_schema, "version": "incompatible-schema"}
    arm = ExistingPolicyArm(
        model=AlwaysNoTradeRolloutModel(
            AlwaysNoTradePolicy(
                build_trade_setup_action_schema(
                    has_sl_mode=False,
                    has_tp_mode=False,
                    has_multi_tp=False,
                    has_simplex=False,
                )
            )
        ),
        metadata={
            "policy_id": "synthetic_policy",
            "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "checkpoint_source_key": "checkpoint",
            "training_seed": 3,
            "training_total_steps": 10,
            "policy_action_mode": "deterministic",
            "action_schema": incompatible_schema,
        },
    )
    with pytest.raises(ValueError, match="action_schema does not match"):
        evaluate_tier0_setup_baselines(
            cfg,
            bars,
            features,
            None,
            execution_seed=41,
            random_policy_seed=7,
            period_role="synthetic",
            absolute_risk_budget_usd=250.0,
            additional_policies={"existing_policy": arm},
        )


def test_tier0_non_synthetic_evaluation_requires_absolute_risk_budget() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()

    with pytest.raises(ValueError, match="requires an explicit absolute_risk_budget_usd"):
        evaluate_tier0_setup_baselines(
            cfg,
            bars,
            features,
            None,
            execution_seed=41,
            random_policy_seed=7,
            period_role="development",
        )


@pytest.mark.parametrize(
    ("strategy_actions", "trade_setup_actions"),
    [(False, True), (True, False)],
)
def test_tier0_setup_baselines_fail_closed_without_required_action_mode(
    strategy_actions: bool,
    trade_setup_actions: bool,
) -> None:
    cfg = load_config(
        [
            f"env.strategy_actions={str(strategy_actions).lower()}",
            f"env.trade_setup_actions={str(trade_setup_actions).lower()}",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()

    with pytest.raises(ValueError, match="strategy_actions=true.*trade_setup_actions=true"):
        evaluate_tier0_setup_baselines(
            cfg,
            bars,
            features,
            None,
            execution_seed=41,
            random_policy_seed=7,
            period_role="synthetic",
        )


def test_tier0_baselines_reject_exposed_report_data_labeled_development() -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "costs.use_tick_execution=false",
        ]
    )
    bars, features = _synthetic_inputs()
    exposed_index = pd.DatetimeIndex(
        [timestamp + pd.Timedelta(days=365) for timestamp in bars.index]
    )
    bars.index = exposed_index
    features.index = exposed_index

    with pytest.raises(ValueError, match="must be labeled exposed_report_only"):
        evaluate_tier0_setup_baselines(
            cfg,
            bars,
            features,
            None,
            execution_seed=41,
            random_policy_seed=7,
            period_role="development",
            absolute_risk_budget_usd=250.0,
        )


def test_tier0_baseline_bundle_has_valid_manifest_and_hashed_artifacts(tmp_path: Path) -> None:
    cfg = load_config(
        [
            "env.strategy_actions=true",
            "env.trade_setup_actions=true",
            "env.obs_window=1",
            "costs.use_tick_execution=false",
            "evaluation.periods_per_year=100",
        ]
    )
    bars, features = _synthetic_inputs()
    tier0_outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
    )
    schema_record = tier0_outputs["always_no_trade"]["policy_metadata"]["action_schema"]
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=bool(schema_record["has_sl_mode"]),
        has_tp_mode=bool(schema_record["has_tp_mode"]),
        has_multi_tp=bool(schema_record["has_multi_tp"]),
        has_simplex=bool(schema_record["has_simplex"]),
    )
    checkpoint_digest = hashlib.sha256(b"synthetic existing policy checkpoint").hexdigest()
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=41,
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(action_schema)),
                metadata={
                    "policy_id": "synthetic_existing_policy_seed_12",
                    "checkpoint_sha256": checkpoint_digest,
                    "checkpoint_source_key": "existing_policy_checkpoint",
                    "training_seed": 12,
                    "training_total_steps": 100_000,
                    "training_effective_steps": 99_840,
                    "policy_action_mode": "deterministic",
                    "action_schema": action_schema.to_dict(),
                },
            )
        },
    )

    source_repository = tmp_path / "source"
    config_path = source_repository / "config.yaml"
    metric_path = source_repository / "evaluation/metrics/performance.py"
    protocol_path = source_repository / "docs/operations/research_execution_plan.md"
    config_path.parent.mkdir(parents=True)
    metric_path.parent.mkdir(parents=True)
    protocol_path.parent.mkdir(parents=True)
    config_path.write_text("synthetic: true\n", encoding="utf-8")
    metric_path.write_text("synthetic metric source identity\n", encoding="utf-8")
    protocol_path.write_text("synthetic protocol\n", encoding="utf-8")
    checkpoint_path = source_repository / "checkpoints/existing-policy.zip"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_bytes(b"synthetic existing policy checkpoint")

    mismatched_outputs = {name: dict(result) for name, result in outputs.items()}
    random_result = dict(mismatched_outputs["random_eligible_setup"])
    random_metadata = dict(random_result["policy_metadata"])
    random_metadata["input_hashes"] = {"bars": "wrong"}
    random_result["policy_metadata"] = random_metadata
    mismatched_outputs["random_eligible_setup"] = random_result
    with pytest.raises(ValueError, match="input hashes do not match"):
        write_matched_setup_baseline_bundle(
            mismatched_outputs,
            cfg,
            bars,
            features,
            None,
            output_root=tmp_path / "evidence/research/mismatched",
            artifact_root=tmp_path,
            source_repository=source_repository,
            config_path=config_path,
            protocol_path="docs/operations/research_execution_plan.md",
            regeneration_command="pytest tests/integration/evaluation/test_matched_setup_baselines.py",
            source_files={"existing_policy_checkpoint": checkpoint_path},
        )

    bundle_path = write_matched_setup_baseline_bundle(
        outputs,
        cfg,
        bars,
        features,
        None,
        output_root=tmp_path / "evidence/research/matched_setup_baselines",
        artifact_root=tmp_path,
        source_repository=source_repository,
        config_path=config_path,
        protocol_path="docs/operations/research_execution_plan.md",
        regeneration_command="pytest tests/integration/evaluation/test_matched_setup_baselines.py",
        symbols=("SYNTHETIC",),
        timeframes=("M1",),
        source_files={"existing_policy_checkpoint": checkpoint_path},
    )

    manifest_path = bundle_path / "result_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas/research_result_manifest_v2.schema.json").read_text(encoding="utf-8")
    )
    assert manifest["manifest_status"] == "draft"
    assert manifest["finding_status"] == "draft_synthetic_contract_validation"
    assert validate_result_manifest(manifest, schema, repo_root=tmp_path) == []
    assert {run["role"] for run in manifest["runs"]} == {
        "control",
        "randomized_control",
        "trained_policy",
    }
    trained_run = next(run for run in manifest["runs"] if run["role"] == "trained_policy")
    assert trained_run["identity"]["checkpoint_hash"] == checkpoint_digest
    assert trained_run["identity"]["training_seed"] == 12
    assert any(artifact["role"] == "confidence_intervals" for artifact in trained_run["artifacts"])
    interval_path = bundle_path / "existing_policy" / "confidence_intervals.json"
    interval_payload = json.loads(interval_path.read_text(encoding="utf-8"))
    assert interval_payload["schema"] == "within_trajectory_bootstrap_ci_v1"
    assert interval_payload["scope"].startswith("within-trajectory sampling")
    policy_comparison = next(
        item
        for item in manifest["comparisons"]
        if item["comparison_id"] == "existing_policy_vs_random_eligible_setup"
    )
    paired_intervals = policy_comparison["paired_time_series_intervals"]
    assert paired_intervals["schema"] == "paired_matched_bar_metric_ci_v2"
    assert paired_intervals["difference_direction"] == "treatment_minus_control"
    assert paired_intervals["scope"].startswith("paired within-trajectory uncertainty")
    assert paired_intervals["status"] == "estimated"
    assert paired_intervals["paired_return_observations"] >= 2
    assert set(paired_intervals["metrics"]) == {
        "mean_bar_return",
        "sharpe",
        "sortino",
        "max_drawdown",
    }
    assert (bundle_path / "input_identity.json").is_file()
    assert all(
        artifact["path"].startswith(bundle_path.relative_to(tmp_path).as_posix())
        for run in manifest["runs"]
        for artifact in run["artifacts"]
    )
    input_identity = json.loads((bundle_path / "input_identity.json").read_text(encoding="utf-8"))
    assert input_identity["protocol_file"]["path"] == "docs/operations/research_execution_plan.md"
    assert (
        input_identity["protocol_file"]["sha256"]
        == hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    )

    incorrect_checkpoint = source_repository / "checkpoints/incorrect-policy.zip"
    incorrect_checkpoint.write_bytes(b"different checkpoint contents")
    with pytest.raises(ValueError, match="checkpoint hash must match"):
        write_matched_setup_baseline_bundle(
            outputs,
            cfg,
            bars,
            features,
            None,
            output_root=tmp_path / "evidence/research/checkpoint_hash_mismatch",
            artifact_root=tmp_path,
            source_repository=source_repository,
            config_path=config_path,
            protocol_path="docs/operations/research_execution_plan.md",
            regeneration_command="pytest tests/integration/evaluation/test_matched_setup_baselines.py",
            source_files={"existing_policy_checkpoint": incorrect_checkpoint},
        )

    with pytest.raises(FileExistsError, match="refusing to overwrite immutable"):
        write_matched_setup_baseline_bundle(
            outputs,
            cfg,
            bars,
            features,
            None,
            output_root=tmp_path / "evidence/research/matched_setup_baselines",
            artifact_root=tmp_path,
            source_repository=source_repository,
            config_path=config_path,
            protocol_path="docs/operations/research_execution_plan.md",
            regeneration_command="pytest tests/integration/evaluation/test_matched_setup_baselines.py",
            symbols=("SYNTHETIC",),
            timeframes=("M1",),
            source_files={"existing_policy_checkpoint": checkpoint_path},
        )
