"""Matched baseline entry points reject invalid selections before rollout work."""

from __future__ import annotations

import random
from collections.abc import Mapping
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import build_trade_setup_action_schema
from evaluation.rollout import matched_setup_baselines
from evaluation.rollout.matched_setup_baselines import (
    ExistingPolicyArm,
    RuleSetupBaselineArm,
)


def _inputs() -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    cfg: dict[str, object] = {"env": {"strategy_actions": True, "trade_setup_actions": True}}
    index = pd.DatetimeIndex([], tz="UTC")
    return cfg, pd.DataFrame(index=index), pd.DataFrame(index=index)


def _evaluate(
    cfg: Mapping[str, object],
    bars: pd.DataFrame,
    features: pd.DataFrame,
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    options: dict[str, Any] = {
        "execution_seed": 3,
        "random_policy_seed": 7,
        "period_role": "synthetic",
        "bootstrap_samples": 2,
    }
    options.update(kwargs)
    return matched_setup_baselines.evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        **options,
    )


@pytest.mark.parametrize(
    ("baseline_names", "message"),
    [
        (["unknown"], "unknown baseline_names"),
        (["always_no_trade", "always_no_trade"], "must not contain duplicates"),
        ([], "must select at least one policy"),
    ],
)
def test_baseline_selection_contract_fails_before_environment_creation(
    baseline_names: list[str], message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, bars, features = _inputs()
    monkeypatch.setattr(
        matched_setup_baselines,
        "cost_model",
        lambda _cfg: SimpleNamespace(slippage_points=0.0),
    )
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("invalid baseline selection must fail before rollout"),
    )

    with pytest.raises(ValueError, match=message):
        _evaluate(cfg, bars, features, baseline_names=baseline_names)


def test_existing_policy_arm_requires_checkpoint_provenance_before_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg, bars, features = _inputs()
    monkeypatch.setattr(
        matched_setup_baselines,
        "cost_model",
        lambda _cfg: SimpleNamespace(slippage_points=0.0),
    )
    model = SimpleNamespace(predict=lambda *_args, **_kwargs: None)
    arm = ExistingPolicyArm(model=model, metadata={})

    with pytest.raises(ValueError, match="metadata is missing 'policy_id'"):
        _evaluate(cfg, bars, features, additional_policies={"candidate_policy": arm})


@pytest.mark.parametrize(
    "missing_key",
    [
        "policy_id",
        "checkpoint_sha256",
        "checkpoint_source_key",
        "training_seed",
        "training_total_steps",
        "policy_action_mode",
        "action_schema",
    ],
)
def test_existing_policy_metadata_requires_every_checkpoint_contract_field(
    missing_key: str,
) -> None:
    metadata = {
        "policy_id": "candidate",
        "checkpoint_sha256": "a" * 64,
        "checkpoint_source_key": "checkpoint.zip",
        "training_seed": 7,
        "training_total_steps": 100,
        "policy_action_mode": "deterministic",
        "action_schema": {"schema": "trade_setup_action_v1"},
    }
    del metadata[missing_key]
    arm = ExistingPolicyArm(
        model=SimpleNamespace(predict=lambda *_args, **_kwargs: None),
        metadata=metadata,
    )

    with pytest.raises(ValueError, match=f"metadata is missing '{missing_key}'"):
        matched_setup_baselines._validate_existing_policy("candidate", arm)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"bootstrap_samples": 0}, "bootstrap_samples must be a positive integer"),
        ({"bootstrap_samples": True}, "bootstrap_samples must be a positive integer"),
        ({"bootstrap_level": 1.0}, "bootstrap_level must be finite and between 0 and 1"),
        ({"bootstrap_seed": -1}, "bootstrap_seed must be a non-negative integer"),
        ({"execution_seed": True}, "execution_seed must be a non-negative integer"),
        ({"random_policy_seed": -1}, "random_policy_seed must be a non-negative integer"),
        ({"period_role": "development"}, "requires an explicit absolute_risk_budget_usd"),
        ({"period_role": "oos"}, "period_role must be development"),
        ({"absolute_risk_budget_usd": float("nan")}, "must be finite and positive"),
        ({"absolute_risk_budget_usd": "not-a-number"}, "must be finite and positive"),
        ({"absolute_risk_budget_usd": True}, "must be finite and positive"),
        (
            {"absolute_risk_budget_usd": 100.0, "normalized_risk": 1.1},
            "normalized_risk must be finite and in \\[0, 1\\]",
        ),
        (
            {"absolute_risk_budget_usd": 100.0, "tick_fill_slippage_points": -1.0},
            "tick_fill_slippage_points must be finite and non-negative",
        ),
        (
            {"absolute_risk_budget_usd": 100.0, "tick_fill_slippage_points": "bad"},
            "tick_fill_slippage_points must be finite and non-negative",
        ),
    ],
)
def test_matched_baseline_protocol_rejects_invalid_inputs_before_rollout(
    kwargs: dict[str, Any], message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, bars, features = _inputs()
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("invalid protocol input must fail before rollout"),
    )

    with pytest.raises(ValueError, match=message):
        _evaluate(cfg, bars, features, **kwargs)


def test_matched_baseline_requires_setup_actions_before_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, bars, features = _inputs()
    cfg = {"env": {"strategy_actions": True, "trade_setup_actions": False}}
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("missing setup-action config must fail before rollout"),
    )

    with pytest.raises(ValueError, match="require env.strategy_actions=true"):
        _evaluate(cfg, bars, features)


def test_matched_baseline_rejects_unaligned_bar_feature_rows_before_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg, bars, features = _inputs()
    bars = pd.DataFrame(index=pd.DatetimeIndex(["2025-01-01"], tz="UTC"))
    features = pd.DataFrame(index=pd.DatetimeIndex(["2025-01-02"], tz="UTC"))
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("unaligned inputs must fail before rollout"),
    )

    with pytest.raises(ValueError, match="identical rows and ordered timestamps"):
        _evaluate(cfg, bars, features)


def test_risk_sizing_provenance_reports_fixed_budget_and_tightest_static_cap() -> None:
    metadata = matched_setup_baselines._risk_sizing_metadata(
        {
            "env": {"risk_mode": "fixed", "fixed_risk_usd": 250.0},
            "ftmo": {"risk_per_trade_limit": 500.0, "risk_sizing_limit_usd": 300.0},
            "strategy": {"risk": {"risk_frac_range": [0.1, 0.5]}},
            "account": {"contract_size": 20.0},
        }
    )

    assert metadata["risk_mode"] == "fixed"
    assert "total stop-risk" in metadata["risk_budget_semantics"]
    assert metadata["fixed_risk_usd"] == 250.0
    assert metadata["configured_static_trade_risk_cap_usd"] == 300.0
    assert metadata["strategy_risk_frac_range"] == [0.1, 0.5]
    assert metadata["contract_size"] == 20.0


def test_absolute_risk_budget_uses_an_independent_canonical_config() -> None:
    source = {"env": {"risk_mode": "dynamic", "risk_band_max_usd": 500.0}}

    effective = matched_setup_baselines._with_absolute_risk_budget(source, risk_band_max_usd=250.0)

    assert source == {"env": {"risk_mode": "dynamic", "risk_band_max_usd": 500.0}}
    assert effective.env.risk_mode == "dollar_band"
    assert effective.env.risk_band_max_usd == 250.0
    assert matched_setup_baselines._resolved_config_sha256({"b": 2, "a": 1}) == (
        matched_setup_baselines._resolved_config_sha256({"a": 1, "b": 2})
    )


def test_seeded_stochastic_arm_repeats_actions_and_restores_global_rngs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_torch(_name: str) -> Any:
        raise ImportError("exercise the supported no-Torch path")

    monkeypatch.setattr(matched_setup_baselines, "import_module", no_torch)
    random.seed(81)
    np.random.seed(81)
    expected_python = random.random()
    expected_numpy = np.random.random()
    random.seed(81)
    np.random.seed(81)

    with matched_setup_baselines._seeded_action_rng(7):
        first = (random.random(), np.random.random())
    after_first = (random.random(), np.random.random())
    with matched_setup_baselines._seeded_action_rng(7):
        second = (random.random(), np.random.random())

    assert first == second
    assert after_first == (expected_python, expected_numpy)


def _valid_existing_policy_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "policy_id": "candidate_ppo",
        "checkpoint_sha256": "a" * 64,
        "checkpoint_source_key": "checkpoints/best.zip",
        "training_seed": 7,
        "training_total_steps": 100_000,
        "policy_action_mode": "deterministic",
        "action_schema": {"schema": "trade_setup_action_v1"},
    }
    metadata.update(overrides)
    return metadata


@pytest.mark.parametrize(
    ("name", "metadata", "error", "message"),
    [
        ("bad-name", {}, ValueError, "unique lowercase identifiers"),
        ("always_no_trade", {}, ValueError, "unique lowercase identifiers"),
        (
            "candidate",
            _valid_existing_policy_metadata(policy_id=" "),
            ValueError,
            "policy_id must be a non-empty string",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(checkpoint_sha256="A" * 64),
            ValueError,
            "checkpoint_sha256 must be a lowercase SHA-256",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(checkpoint_source_key=""),
            ValueError,
            "checkpoint_source_key must be a non-empty string",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(training_seed=True),
            ValueError,
            "training_seed must be a non-negative integer",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(training_seed=1.5),
            ValueError,
            "training_seed must be a non-negative integer",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(training_total_steps=-1),
            ValueError,
            "training_total_steps must be a non-negative integer",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(training_total_steps=False),
            ValueError,
            "training_total_steps must be a non-negative integer",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(policy_action_mode="unknown"),
            ValueError,
            "policy_action_mode must be deterministic or stochastic",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(policy_action_mode="stochastic"),
            ValueError,
            "stochastic policies require policy_action_seed",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(
                policy_action_mode="stochastic", policy_action_seed=True
            ),
            ValueError,
            "stochastic policies require policy_action_seed",
        ),
        (
            "candidate",
            _valid_existing_policy_metadata(
                policy_action_mode="stochastic", policy_action_seed=2**32
            ),
            ValueError,
            "stochastic policies require policy_action_seed",
        ),
    ],
)
def test_existing_policy_metadata_rejects_invalid_identity_and_action_contracts(
    name: str, metadata: dict[str, Any], error: type[Exception], message: str
) -> None:
    arm = ExistingPolicyArm(
        model=SimpleNamespace(predict=lambda *_args, **_kwargs: None), metadata=metadata
    )

    with pytest.raises(error, match=message):
        matched_setup_baselines._validate_existing_policy(name, arm)


def test_existing_policy_metadata_accepts_valid_stochastic_seed_and_marks_source() -> None:
    arm = ExistingPolicyArm(
        model=SimpleNamespace(predict=lambda *_args, **_kwargs: None),
        metadata=_valid_existing_policy_metadata(
            policy_action_mode="stochastic", policy_action_seed=2**32 - 1
        ),
    )

    result = matched_setup_baselines._validate_additional_policy("candidate", arm)

    assert result["policy_action_seed"] == 2**32 - 1
    assert result["policy_source"] == "trained_checkpoint"


def test_existing_policy_metadata_requires_a_predict_method() -> None:
    arm = ExistingPolicyArm(
        model=object(),
        metadata=_valid_existing_policy_metadata(),
    )

    with pytest.raises(TypeError, match="must expose predict"):
        matched_setup_baselines._validate_existing_policy("candidate", arm)


def _valid_rule_metadata(**overrides: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "policy_id": "structure_priority_v1",
        "baseline_tier": "tier_1_rule",
        "policy_action_mode": "deterministic",
        "action_schema": {"schema": "trade_setup_action_v1"},
        "permitted_information": ["completed bars"],
        "training_performed": False,
        "selection_or_tuning_performed": False,
    }
    metadata.update(overrides)
    return metadata


@pytest.mark.parametrize(
    ("name", "metadata", "message"),
    [
        ("bad-name", {}, "unique lowercase identifiers"),
        ("random_eligible_setup", {}, "unique lowercase identifiers"),
        ("candidate", {"policy_id": "rule"}, "missing 'baseline_tier'"),
        ("candidate", _valid_rule_metadata(policy_id=""), "policy_id must be a non-empty string"),
        ("candidate", _valid_rule_metadata(baseline_tier="tier_0_random"), "Tier 1"),
        (
            "candidate",
            _valid_rule_metadata(policy_action_mode="stochastic"),
            "deterministic action mode",
        ),
        ("candidate", _valid_rule_metadata(training_performed=True), "training_performed=false"),
        (
            "candidate",
            _valid_rule_metadata(selection_or_tuning_performed=True),
            "selection_or_tuning_performed=false",
        ),
        ("candidate", _valid_rule_metadata(permitted_information={"bars": True}), "must be a list"),
    ],
)
def test_rule_baseline_metadata_rejects_invalid_tier_or_provenance(
    name: str, metadata: dict[str, Any], message: str
) -> None:
    arm = RuleSetupBaselineArm(
        model=SimpleNamespace(
            predict=lambda *_args, **_kwargs: None,
            policy_metadata=metadata,
        )
    )

    with pytest.raises(ValueError, match=message):
        matched_setup_baselines._validate_rule_setup_baseline(name, arm)


def test_rule_baseline_metadata_marks_valid_policy_as_deterministic_rule() -> None:
    arm = RuleSetupBaselineArm(
        model=SimpleNamespace(
            predict=lambda *_args, **_kwargs: None,
            policy_metadata=_valid_rule_metadata(),
        )
    )

    result = matched_setup_baselines._validate_additional_policy("candidate", arm)

    assert result["policy_source"] == "deterministic_rule"


@pytest.mark.parametrize(
    "missing_key",
    [
        "policy_id",
        "baseline_tier",
        "policy_action_mode",
        "action_schema",
        "permitted_information",
        "training_performed",
        "selection_or_tuning_performed",
    ],
)
def test_rule_baseline_requires_complete_policy_emitted_provenance(missing_key: str) -> None:
    metadata = _valid_rule_metadata()
    del metadata[missing_key]
    arm = RuleSetupBaselineArm(
        model=SimpleNamespace(
            predict=lambda *_args, **_kwargs: None,
            policy_metadata=metadata,
        )
    )

    with pytest.raises(ValueError, match=f"metadata is missing '{missing_key}'"):
        matched_setup_baselines._validate_rule_setup_baseline("candidate", arm)


def test_rule_baseline_requires_predict_and_policy_emitted_metadata() -> None:
    with pytest.raises(TypeError, match="must expose predict"):
        matched_setup_baselines._validate_rule_setup_baseline(
            "candidate",
            RuleSetupBaselineArm(model=object()),
        )
    with pytest.raises(ValueError, match="must expose policy_metadata"):
        matched_setup_baselines._validate_rule_setup_baseline(
            "candidate",
            RuleSetupBaselineArm(model=SimpleNamespace(predict=lambda *_args, **_kwargs: None)),
        )


def test_additional_policy_requires_supported_arm_type() -> None:
    with pytest.raises(TypeError, match="ExistingPolicyArm or RuleSetupBaselineArm"):
        matched_setup_baselines._validate_additional_policy("candidate", object())  # type: ignore[arg-type]


def test_policy_hash_requires_lowercase_hex_digest() -> None:
    assert matched_setup_baselines._valid_sha256("a" * 64)
    assert not matched_setup_baselines._valid_sha256("A" * 64)
    assert not matched_setup_baselines._valid_sha256("g" * 64)
    assert not matched_setup_baselines._valid_sha256(7)


def test_seeded_action_rng_seeds_and_restores_the_torch_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import nullcontext

    calls: dict[str, Any] = {}
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False, device_count=lambda: 0),
        random=SimpleNamespace(
            fork_rng=lambda *, devices: calls.update(devices=devices) or nullcontext()
        ),
        manual_seed=lambda seed: calls.update(seed=seed),
    )
    monkeypatch.setattr(matched_setup_baselines, "import_module", lambda _name: fake_torch)
    random.seed(17)
    expected_next_random = random.random()
    random.seed(17)

    with matched_setup_baselines._seeded_action_rng(19):
        assert calls == {"devices": [], "seed": 19}

    assert random.random() == expected_next_random


@pytest.mark.parametrize(
    ("bars", "period_role", "message"),
    [
        (pd.DataFrame(index=pd.Index([0])), "synthetic", "require a DatetimeIndex"),
        (
            pd.DataFrame(index=pd.DatetimeIndex(["2025-01-01"], tz="UTC")),
            "exposed_report_only",
            "requires overlap",
        ),
        (
            pd.DataFrame(index=pd.DatetimeIndex(["2026-02-01"], tz="UTC")),
            "development",
            "must be labeled exposed_report_only",
        ),
    ],
)
def test_baseline_input_roles_reject_invalid_index_or_exposed_interval(
    bars: pd.DataFrame, period_role: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, _, _ = _inputs()
    features = pd.DataFrame(index=bars.index)
    monkeypatch.setattr(
        matched_setup_baselines,
        "cost_model",
        lambda _cfg: SimpleNamespace(slippage_points=0.0),
    )
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("invalid date contract must fail before rollout"),
    )

    with pytest.raises((TypeError, ValueError), match=message):
        _evaluate(
            cfg,
            bars,
            features,
            period_role=period_role,
            absolute_risk_budget_usd=10.0,
            tick_fill_slippage_points=0.0,
        )


def test_additional_policy_needs_a_shared_absolute_risk_budget_before_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg, bars, features = _inputs()
    arm = RuleSetupBaselineArm(
        model=SimpleNamespace(
            predict=lambda *_args, **_kwargs: None,
            policy_metadata=_valid_rule_metadata(),
        )
    )
    monkeypatch.setattr(
        matched_setup_baselines,
        "cost_model",
        lambda _cfg: SimpleNamespace(slippage_points=0.0),
    )
    monkeypatch.setattr(
        matched_setup_baselines,
        "TradingEnv",
        lambda **_kwargs: pytest.fail("missing shared risk budget must fail before rollout"),
    )

    with pytest.raises(ValueError, match="additional policies require an explicit"):
        _evaluate(cfg, bars, features, additional_policies={"candidate": arm})


def test_absolute_risk_budget_cannot_exceed_static_trade_risk_limit() -> None:
    cfg, bars, features = _inputs()
    cfg["ftmo"] = {"risk_per_trade_limit": 100.0}

    with pytest.raises(ValueError, match="exceeds the configured static"):
        _evaluate(cfg, bars, features, absolute_risk_budget_usd=101.0)


@pytest.mark.parametrize(
    "invalid_config",
    [None, [], 1],
)
def test_risk_provenance_rejects_non_mapping_config(invalid_config: Any) -> None:
    with pytest.raises(TypeError, match="mapping or an OmegaConf config"):
        matched_setup_baselines._risk_sizing_metadata(invalid_config)


def test_annualization_uses_configured_periods_and_legacy_fallback() -> None:
    assert matched_setup_baselines._periods_per_year({"evaluation": {"periods_per_year": 12}}) == 12
    assert matched_setup_baselines._periods_per_year(object()) == 252 * 390


def test_stochastic_additional_policy_rollout_uses_matching_schema_and_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg, _, _ = _inputs()
    index = pd.DatetimeIndex(["2025-01-02 15:00"], tz="UTC")
    bars = pd.DataFrame({"close": [100.0]}, index=index)
    features = pd.DataFrame({"signal": [0.25]}, index=index)
    schema = build_trade_setup_action_schema()
    raw_equity = pd.Series([100.0], index=index)
    raw_trades = pd.DataFrame(columns=["type"])
    rollout_calls: list[dict[str, Any]] = []
    seed_calls: list[int] = []
    environment_calls: list[dict[str, Any]] = []

    class SyntheticEnvironment:
        def __init__(
            self,
            bars: pd.DataFrame,
            features: pd.DataFrame,
            *,
            episodic: bool,
            tickbook: Any,
        ) -> None:
            self.action_schema = schema
            environment_calls.append(
                {
                    "bars": bars,
                    "features": features,
                    "episodic": episodic,
                    "tickbook": tickbook,
                }
            )

    def evaluate_model(
        model: Any,
        received_bars: pd.DataFrame,
        received_features: pd.DataFrame,
        *,
        env: Any,
        tickbook: Any,
        execution_seed: int,
        strategy_actions: bool,
        trade_setup_actions: bool,
        deterministic: bool,
    ) -> dict[str, Any]:
        rollout_calls.append(
            {
                "model": model,
                "bars": received_bars,
                "features": received_features,
                "env": env,
                "tickbook": tickbook,
                "execution_seed": execution_seed,
                "strategy_actions": strategy_actions,
                "trade_setup_actions": trade_setup_actions,
                "deterministic": deterministic,
            }
        )
        return {
            "equity": raw_equity,
            "trades": raw_trades,
            "n_sessions": 1,
            "n_breach_sessions": 0,
            "n_steps": 1,
            "exposure_bars": 0,
            "exposure_fraction": 0.0,
            "breach_events": [],
            "completed_data_split": True,
            "episode_end_reason": "data_end",
        }

    @contextmanager
    def seeded_actions(seed: int) -> Any:
        seed_calls.append(seed)
        yield

    model = SimpleNamespace(predict=lambda *_args, **_kwargs: None)
    arm = ExistingPolicyArm(
        model=model,
        metadata=_valid_existing_policy_metadata(
            action_schema=schema.to_dict(),
            policy_action_mode="stochastic",
            policy_action_seed=31,
        ),
    )
    monkeypatch.setattr(matched_setup_baselines, "cost_model", lambda _cfg: None)
    monkeypatch.setattr(
        matched_setup_baselines,
        "build_eval_common",
        lambda *_args, **_kwargs: ({"initial_balance": 100.0}, None, None, None, None),
    )
    monkeypatch.setattr(matched_setup_baselines, "TradingEnv", SyntheticEnvironment)
    monkeypatch.setattr(matched_setup_baselines, "evaluate_model", evaluate_model)
    monkeypatch.setattr(matched_setup_baselines, "_seeded_action_rng", seeded_actions)
    monkeypatch.setattr(
        matched_setup_baselines,
        "calculate_metrics",
        lambda *_args, **_kwargs: SimpleNamespace(total_return_pct=0.0),
    )
    monkeypatch.setattr(matched_setup_baselines, "account_path_metric_inputs", lambda _raw: {})
    monkeypatch.setattr(matched_setup_baselines, "_periods_per_year", lambda _cfg: 252)
    monkeypatch.setattr(matched_setup_baselines, "pair_trades", lambda _trades: [])
    monkeypatch.setattr(matched_setup_baselines, "metrics_with_ci", lambda *_args, **_kwargs: {})

    result = matched_setup_baselines.evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
        execution_seed=13,
        random_policy_seed=17,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        tick_fill_slippage_points=0.0,
        bootstrap_samples=2,
        baseline_names=("candidate",),
        additional_policies={"candidate": arm},
    )["candidate"]

    assert seed_calls == [31]
    assert len(environment_calls) == 1
    assert environment_calls[0]["bars"] is bars
    assert environment_calls[0]["features"] is features
    assert environment_calls[0]["episodic"] is False
    assert environment_calls[0]["tickbook"] is None
    assert len(rollout_calls) == 1
    assert rollout_calls[0]["model"] is model
    assert rollout_calls[0]["bars"] is bars
    assert rollout_calls[0]["features"] is features
    assert rollout_calls[0]["tickbook"] is None
    assert rollout_calls[0]["execution_seed"] == 13
    assert rollout_calls[0]["strategy_actions"] is True
    assert rollout_calls[0]["trade_setup_actions"] is True
    assert rollout_calls[0]["deterministic"] is False
    assert result["policy_metadata"]["evaluation_action_mode"] == "stochastic"
    assert result["policy_metadata"]["policy_source"] == "trained_checkpoint"
    assert result["policy_metadata"]["risk_sizing"]["absolute_risk_budget_usd"] == 250.0
    assert result["equity"] is raw_equity
    assert result["trade_fill_event_ledger"] is raw_trades
