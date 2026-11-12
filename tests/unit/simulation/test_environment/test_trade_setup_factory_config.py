from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from configuration.configuration_loader import load_config
from decisioning.trade_setup import (
    TRADE_SETUP_CATEGORY_COUNT,
    TradeSetupActionSchema,
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
    trade_setup_id_from_box,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from learning.rl.agent import build_agent
from learning.rl.hybrid import (
    HybridClampedStdMultiInputPolicy,
    TradeSetupConditionedClampedStdMultiInputPolicy,
)
from market_data.loading.ticks import TickBook
from models.encoders import MTFReasoningEncoder
from simulation.environment import build_eval_common, make_env, mtf_settings
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)
from trading.strategies import PO3IFVGStrategy


def test_trade_setup_observation_mode_flows_into_train_and_eval_env_kwargs() -> None:
    config = OmegaConf.load("config/base/default.yaml")
    config.env.strategy_actions = True
    config.env.trade_setup_actions = True
    config.env.trade_setup_candidate_timeframes = ["M1", "M5"]

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["strategy_actions"] is True
    assert eval_common["trade_setup_actions"] is True
    assert eval_common["trade_setup_candidate_timeframes"] == ("M1", "M5")


def test_trade_setup_observation_mode_defaults_off() -> None:
    config = OmegaConf.load("config/base/default.yaml")

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["trade_setup_actions"] is False


def test_gate_ii_overlays_isolate_opportunities_from_completed_history() -> None:
    from learning.rl.agent import _ppo_policy_and_ent_coef
    from simulation.environment.trading_environment_factory import mtf_settings

    a = load_config(config_path="config/research/m1_opportunity_reference.yaml")
    b = load_config(config_path="config/research/mtf_shared_opportunities_m1_history.yaml")
    c = load_config(config_path="config/research/mtf_shared_opportunities_with_history.yaml")

    assert list(a.env.trade_setup_candidate_timeframes) == ["M1"]
    assert list(a.features.entry_ideas.timeframes) == ["M1"]
    assert list(b.env.trade_setup_candidate_timeframes) == list(
        c.env.trade_setup_candidate_timeframes
    )
    assert b.agent.arch == c.agent.arch == "mtf_reasoning"
    assert b.env.completed_htf_history_enabled is False
    assert c.env.completed_htf_history_enabled is True
    assert b.ppo.policy_distribution == c.ppo.policy_distribution == "trade_setup_hybrid_v1"
    assert mtf_settings(b, None)[0] is True
    assert mtf_settings(c, None)[0] is True
    b_env_kwargs, *_ = build_eval_common(b, arch=b.agent.arch)
    c_env_kwargs, *_ = build_eval_common(c, arch=c.agent.arch)
    assert b_env_kwargs["completed_htf_history_enabled"] is False
    assert c_env_kwargs["completed_htf_history_enabled"] is True
    b_values = cast(dict[str, Any], OmegaConf.to_container(b, resolve=True))
    c_values = cast(dict[str, Any], OmegaConf.to_container(c, resolve=True))
    b_values["env"]["completed_htf_history_enabled"] = c_values["env"][
        "completed_htf_history_enabled"
    ]
    assert b_values == c_values
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=bool(b.env.allow_agent_sl_mode),
        has_tp_mode=bool(b.env.allow_agent_tp_mode),
        has_multi_tp=bool(b.env.allow_multi_tp),
        has_simplex=bool(b.env.allow_multi_tp and b.env.allow_simplex),
    )
    c_action_schema = build_trade_setup_action_schema(
        has_sl_mode=bool(c.env.allow_agent_sl_mode),
        has_tp_mode=bool(c.env.allow_agent_tp_mode),
        has_multi_tp=bool(c.env.allow_multi_tp),
        has_simplex=bool(c.env.allow_multi_tp and c.env.allow_simplex),
    )
    assert action_schema == c_action_schema
    observation_space = spaces.Dict(
        {"trade_setup_mask": spaces.Box(0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32)}
    )
    action_space = spaces.Box(-1.0, 1.0, (action_schema.width,), dtype=np.float32)
    b_policy = _ppo_policy_and_ent_coef(b, {}, action_space, action_schema, observation_space)
    c_policy = _ppo_policy_and_ent_coef(c, {}, action_space, c_action_schema, observation_space)
    assert b_policy == c_policy


def test_feature_validity_channels_are_opt_in_and_flow_to_eval_env_kwargs() -> None:
    config = OmegaConf.load("config/base/default.yaml")

    eval_common, *_ = build_eval_common(config, arch="tcn")
    assert eval_common["feature_validity_channels"] is False
    assert eval_common["reachable_r_validity_mask"] is False

    config.env.feature_validity_channels = True
    config.env.reachable_r_validity_mask = True
    eval_common, *_ = build_eval_common(config, arch="tcn")
    assert eval_common["feature_validity_channels"] is True
    assert eval_common["reachable_r_validity_mask"] is True


def test_survival_qualification_overlay_exposes_required_sequence_validity_inputs() -> None:
    config = load_config(config_path="config/research/survival_qualification.yaml")

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["feature_validity_channels"] is True
    assert eval_common["reachable_r_validity_mask"] is True


@pytest.mark.parametrize(
    "arch",
    [
        "mtf_empty_stream_masked_v1",
        "mtf_shared_tcn_reasoning",
        "mtf_m1_tcn_htf_lite_reasoning",
        "mtf_m1_tcn_htf_snapshot_reasoning",
    ],
)
def test_e_f_g_architectures_enable_mtf_observations(arch: str) -> None:
    config = OmegaConf.create({"agent": {"arch": arch}})

    use_mtf, windows = mtf_settings(config, arch)

    assert use_mtf is True
    assert set(windows) == {"m3", "m5", "m10", "m15", "m30", "h1", "h4", "d1"}


def test_mtf_reasoning_research_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/trade_setup_mtf_reasoning.yaml")

    assert config.env.strategy_actions is True
    assert config.env.trade_setup_actions is True
    assert config.env.agent_direction_control is False
    assert config.features.include_strategy_state is True
    assert config.features.entry_ideas.enabled is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "trade_setup_hybrid_v1"
    assert config.ppo.actor_arch == "shared"


def test_mtf_reasoning_conditioned_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/trade_setup_mtf_reasoning_conditioned.yaml")

    assert config.env.strategy_actions is True
    assert config.env.trade_setup_actions is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "trade_setup_conditioned_v1"
    assert config.ppo.trade_setup_conditioned.embedding_dim == 32
    assert config.ppo.trade_setup_conditioned.execution_hidden_dim == 128


@pytest.mark.parametrize(
    ("overlay", "distribution"),
    [
        ("trade_setup_mtf_reasoning.yaml", "trade_setup_hybrid_v1"),
        ("trade_setup_mtf_reasoning_conditioned.yaml", "trade_setup_conditioned_v1"),
    ],
)
def test_canonical_trade_setup_overlays_are_explicit(overlay: str, distribution: str) -> None:
    config = load_config(config_path=f"config/research/{overlay}")

    assert config.env.strategy_actions is True
    assert config.env.trade_setup_actions is True
    assert config.ppo.policy_distribution == distribution
    eval_common, *_ = build_eval_common(config, arch="mtf_reasoning")
    assert eval_common["trade_setup_actions"] is True


def test_resolved_reasoning_treatment_uses_canonical_trade_setup_contract() -> None:
    from training.configuration.variant_resolution import resolve_variant

    resolved = resolve_variant("rq_mtf_treatment_reasoning")

    overrides = set(resolved["overrides"])
    assert "env.trade_setup_actions=true" in overrides
    assert "ppo.policy_distribution=trade_setup_hybrid_v1" in overrides


@pytest.mark.parametrize(
    ("overlay", "expected_conditioned"),
    [
        ("trade_setup_mtf_reasoning.yaml", False),
        ("trade_setup_mtf_reasoning_conditioned.yaml", True),
    ],
)
def test_canonical_distribution_resolves_matching_policy_and_mask(
    overlay: str, expected_conditioned: bool
) -> None:
    from learning.rl.agent import _ppo_policy_and_ent_coef
    from learning.rl.hybrid import (
        TradeSetupConditionedClampedStdMultiInputPolicy,
    )

    config = load_config(config_path=f"config/research/{overlay}")
    schema = build_trade_setup_action_schema(
        has_sl_mode=bool(config.env.allow_agent_sl_mode),
        has_tp_mode=bool(config.env.allow_agent_tp_mode),
        has_multi_tp=bool(config.env.allow_multi_tp),
        has_simplex=bool(config.env.allow_multi_tp and config.env.allow_simplex),
    )
    observation_space = spaces.Dict(
        {"trade_setup_mask": spaces.Box(0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32)}
    )
    policy, kwargs, _ = _ppo_policy_and_ent_coef(
        config,
        {},
        spaces.Box(-1.0, 1.0, (schema.width,), dtype=np.float32),
        schema,
        observation_space,
    )

    expected_policy = (
        TradeSetupConditionedClampedStdMultiInputPolicy
        if expected_conditioned
        else HybridClampedStdMultiInputPolicy
    )
    assert policy is expected_policy
    assert kwargs["trade_setup_mask_key"] == "trade_setup_mask"


@pytest.mark.parametrize("use_tick_execution", [False, True], ids=["bar-open", "tick-fill"])
def test_d_e_f_g_fixed_action_simulator_trace_is_identical(use_tick_execution: bool) -> None:
    """Encoder selection must not change environment transitions for fixed actions."""
    overlays = (
        "trade_setup_mtf_reasoning_conditioned_2m.yaml",
        "trade_setup_mtf_shared_tcn_2m.yaml",
        "trade_setup_mtf_m1_htf_lite_2m.yaml",
        "trade_setup_mtf_m1_htf_snapshot_2m.yaml",
    )
    bars = _make_bars(120)
    features = _make_features(bars)
    trade_setup_columns = [name for _, name in trade_setup_candidate_feature_columns()]
    strategy_columns = list(PO3IFVGStrategy.required_features)
    features = pd.concat(
        [
            features,
            pd.DataFrame(0.0, index=features.index, columns=strategy_columns, dtype=np.float32),
            pd.DataFrame(0.0, index=features.index, columns=trade_setup_columns, dtype=np.float32),
        ],
        axis=1,
    )
    candidate_id = trade_setup_candidate_id("po3", "M1", 1)
    candidate_column = dict(trade_setup_candidate_feature_columns())[candidate_id]
    features[candidate_column] = 1.0
    # Give the shared simulator a valid structural stop and a reachable target
    # so this parity trace verifies an executed open/fill, not only a
    # no-position transition for an eligible trade_setup.
    features["last_swing_low"] = bars["close"] - 30.0
    features["last_swing_high"] = bars["close"] + 60.0
    tickbook = None
    if use_tick_execution:
        tick_times = (
            pd.DatetimeIndex(bars.index)
            .tz_convert("UTC")
            .to_numpy(dtype="datetime64[ns]")
            .astype(np.int64)
            + 100_000_000
        )
        tick_mid = bars["close"].to_numpy(dtype=np.float64)
        tickbook = TickBook(tick_times, tick_mid - 0.1, tick_mid + 0.1)
    envs = []
    try:
        for overlay in overlays:
            config = load_config(config_path=f"config/research/{overlay}")
            config.costs.use_tick_execution = use_tick_execution
            config.execution.randomized_fill_latency_ms = 0.0
            config.env.open_manipulation_bars = 0
            envs.append(
                make_env(
                    bars,
                    features,
                    config,
                    algo="ppo",
                    reward="dsr",
                    tickbook=tickbook,
                )
            )

        observations = [env.reset(seed=41)[0] for env in envs]
        assert all(
            observation["trade_setup_mask"][candidate_id] == 1.0 for observation in observations
        )
        for key in observations[0]:
            for observation in observations[1:]:
                np.testing.assert_array_equal(observations[0][key], observation[key])

        entry_action = np.zeros(envs[0].action_space.shape, dtype=np.float32)
        entry_action[0] = trade_setup_center(candidate_id)
        schema = envs[0].action_schema
        assert isinstance(schema, TradeSetupActionSchema)
        entry_action[schema.indices["risk"]] = 1.0
        entry_action[schema.indices["target"]] = -1.0
        entry_action[schema.indices["exit"]] = -1.0
        transitions = [env.step(entry_action) for env in envs]
        reference = transitions[0]
        for transition in transitions[1:]:
            for key in reference[0]:
                np.testing.assert_array_equal(reference[0][key], transition[0][key])
            assert reference[1:4] == transition[1:4]
            np.testing.assert_equal(reference[4], transition[4])
        assert all(transition[4]["position"] for transition in transitions), [
            {
                "entry_rejection_reason": transition[4]["entry_rejection_reason"],
                "entry_funnel": transition[4]["entry_funnel"],
                "trade_log": env.trade_log,
            }
            for env, transition in zip(envs, transitions, strict=True)
        ]
        assert all(transition[4]["entry_rejection_reason"] == "" for transition in transitions)

        open_records = [
            [record for record in env.trade_log if record.get("type") == "open"] for env in envs
        ]
        assert all(len(records) == 1 for records in open_records)
        reference_open = open_records[0][0]
        assert reference_open["fill_quote_source"] == ("tick" if use_tick_execution else "bar_open")
        for records in open_records[1:]:
            for field in (
                "direction",
                "price",
                "sl_price",
                "tp_price",
                "lots",
                "fill_quote_source",
                "trade_setup_candidate_id",
            ):
                assert records[0][field] == reference_open[field]
        if use_tick_execution:
            assert reference_open["actual_tick_time"] == reference_open["fill_time"]
            assert reference_open["execution_latency_ns"] == 0
            for records in open_records[1:]:
                for field in (
                    "actual_tick_time",
                    "fill_time",
                    "execution_order_time",
                    "order_submission_time",
                    "execution_latency_ns",
                ):
                    assert records[0][field] == reference_open[field]

        # Include the account and position traces in the parity contract; equal
        # open records alone would not catch divergent post-fill bookkeeping.
        reference_position = envs[0].position
        assert reference_position is not None
        for env in envs[1:]:
            position = env.position
            assert position is not None
            for field in ("direction", "entry_price", "size", "sl_price", "tp_price"):
                assert getattr(position, field) == pytest.approx(getattr(reference_position, field))
            assert position.position_id == reference_position.position_id
            assert env.account.balance == pytest.approx(envs[0].account.balance)
            assert env.account.equity == pytest.approx(envs[0].account.equity)
            assert env.equity_curve == pytest.approx(envs[0].equity_curve)
    finally:
        for env in envs:
            env.close()


def test_mtf_reasoning_2m_configs_are_matched_except_for_execution_conditioning() -> None:
    control = load_config(config_path="config/research/trade_setup_mtf_reasoning_2m.yaml")
    treatment = load_config(
        config_path="config/research/trade_setup_mtf_reasoning_conditioned_2m.yaml"
    )

    for config in (control, treatment):
        assert config.env.n_envs == 8
        assert config.env.strategy_actions is True
        assert config.env.trade_setup_actions is True
        assert config.features.include_strategy_state is True
        assert config.agent.arch == "mtf_reasoning"
        assert config.ppo.n_steps == 2048
        assert config.ppo.batch_size == 512
        assert config.ppo.n_epochs == 15
        assert config.ppo.total_timesteps == 2_000_000
        assert config.ppo.checkpoint_freq == 250_000
        assert config.quality_execution.requested_n_envs == 8
        assert config.quality_execution.exact_n_envs is True

    assert control.ppo.policy_distribution == "trade_setup_hybrid_v1"
    assert treatment.ppo.policy_distribution == "trade_setup_conditioned_v1"
    assert control.ppo.trade_setup_conditioned == treatment.ppo.trade_setup_conditioned
    control_resolved = OmegaConf.to_container(control, resolve=True)
    treatment_resolved = OmegaConf.to_container(treatment, resolve=True)
    assert isinstance(control_resolved, dict)
    assert isinstance(treatment_resolved, dict)
    control_resolved["ppo"].pop("policy_distribution")
    treatment_resolved["ppo"].pop("policy_distribution")
    assert control_resolved == treatment_resolved
    action_schemas = [
        build_trade_setup_action_schema(
            has_sl_mode=bool(config.env.get("allow_agent_sl_mode", False)),
            has_tp_mode=bool(config.env.get("allow_agent_tp_mode", False)),
            has_multi_tp=bool(config.env.get("allow_multi_tp", False)),
            has_simplex=bool(
                config.env.get("allow_multi_tp", False) and config.env.get("allow_simplex", False)
            ),
        ).to_dict()
        for config in (control, treatment)
    ]
    assert action_schemas[0] == action_schemas[1]


@pytest.mark.parametrize(
    ("overlay", "expected_policy"),
    [
        ("trade_setup_mtf_reasoning.yaml", HybridClampedStdMultiInputPolicy),
        (
            "trade_setup_mtf_reasoning_conditioned.yaml",
            TradeSetupConditionedClampedStdMultiInputPolicy,
        ),
    ],
)
def test_mtf_reasoning_overlay_builds_real_env_and_agent(
    tmp_path, overlay, expected_policy
) -> None:
    config = load_config(config_path=f"config/research/{overlay}")
    config.costs.use_tick_execution = False
    config.execution.randomized_fill_latency_ms = 0.0
    config.ppo.n_steps = 2
    config.ppo.batch_size = 2
    config.ppo.n_epochs = 1
    config.agent.mtf_reasoning.latent_dim = 32
    config.agent.mtf_reasoning.feedforward_dim = 64
    config.agent.mtf_reasoning.dropout = 0.0

    bars = _make_bars(120)
    features = _make_features(bars)
    trade_setup_columns = [name for _, name in trade_setup_candidate_feature_columns()]
    strategy_columns = list(PO3IFVGStrategy.required_features)
    features = pd.concat(
        [
            features,
            pd.DataFrame(0.0, index=features.index, columns=strategy_columns, dtype=np.float32),
            pd.DataFrame(0.0, index=features.index, columns=trade_setup_columns, dtype=np.float32),
        ],
        axis=1,
    )
    eval_common, *_ = build_eval_common(config)
    assert eval_common["mtf"] is True

    env = make_env(
        bars,
        features,
        config,
        algo="ppo",
        reward="dsr",
    )
    observation, _ = env.reset(seed=41)
    assert isinstance(env.observation_space, spaces.Dict)
    assert {
        "seq_m3",
        "seq_m5",
        "seq_m10",
        "seq_m15",
        "seq_m30",
        "seq_h1",
        "seq_h4",
        "seq_d1",
        "mask_m3",
        "mask_m5",
        "mask_m10",
        "mask_m15",
        "mask_m30",
        "mask_h1",
        "mask_h4",
        "mask_d1",
        "trade_setup_mask",
    } <= set(env.observation_space.spaces)
    assert observation["trade_setup_mask"].shape == (TRADE_SETUP_CATEGORY_COUNT,)

    model = build_agent(
        env,
        config,
        arch=str(config.agent.arch),
        algo="ppo",
        device="cpu",
        seed=41,
    )
    assert isinstance(model.policy.features_extractor, MTFReasoningEncoder)
    assert type(model.policy) is expected_policy
    model.learn(total_timesteps=2)
    action, _ = model.predict(observation, deterministic=False)
    assert trade_setup_id_from_box(float(action[0])) == 0
    deterministic_action, _ = model.predict(observation, deterministic=True)

    checkpoint = tmp_path / "mtf_trade_setup_factory_smoke.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, env=env, device="cpu")
    assert isinstance(loaded.policy.features_extractor, MTFReasoningEncoder)
    assert type(loaded.policy) is expected_policy
    assert getattr(loaded, "_trade_setup_observation_schema") == env.trade_setup_observation_schema
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    np.testing.assert_array_equal(loaded_action, deterministic_action)
    assert trade_setup_id_from_box(float(loaded_action[0])) == 0
