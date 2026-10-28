from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces
from omegaconf import OmegaConf
from stable_baselines3 import PPO

from configuration.loader import load_config
from decisioning.thesis import (
    THESIS_CATEGORY_COUNT,
    ThesisActionSchema,
    build_thesis_action_schema,
    thesis_candidate_id,
    thesis_center,
    thesis_id_from_box,
)
from features.context.thesis_candidates import thesis_candidate_feature_columns
from learning.rl.agent import build_agent
from learning.rl.hybrid import (
    HybridClampedStdMultiInputPolicy,
    ThesisConditionedClampedStdMultiInputPolicy,
)
from market_data.loading.ticks import TickBook
from models.encoders import MTFReasoningEncoder
from simulation.environment.factory import build_eval_common, make_env, mtf_settings
from tests.test_envs.test_account_normalization import _make_bars, _make_features
from trading.strategies import PO3IFVGStrategy


def test_thesis_observation_mode_flows_into_train_and_eval_env_kwargs() -> None:
    config = OmegaConf.load("config/base/default.yaml")
    config.env.strategy_actions = True
    config.env.thesis_actions = True

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["strategy_actions"] is True
    assert eval_common["thesis_actions"] is True


def test_thesis_observation_mode_defaults_off() -> None:
    config = OmegaConf.load("config/base/default.yaml")

    eval_common, *_ = build_eval_common(config, arch="tcn")

    assert eval_common["thesis_actions"] is False


@pytest.mark.parametrize(
    "arch",
    [
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
    config = load_config(config_path="config/research/thesis_mtf_reasoning.yaml")

    assert config.env.strategy_actions is True
    assert config.env.thesis_actions is True
    assert config.env.agent_direction_control is False
    assert config.features.include_strategy_state is True
    assert config.features.entry_ideas.enabled is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "thesis_hybrid_v1"
    assert config.ppo.actor_arch == "shared"


def test_mtf_reasoning_conditioned_overlay_is_opt_in_and_complete() -> None:
    config = load_config(config_path="config/research/thesis_mtf_reasoning_conditioned.yaml")

    assert config.env.strategy_actions is True
    assert config.env.thesis_actions is True
    assert config.agent.arch == "mtf_reasoning"
    assert config.ppo.policy_distribution == "thesis_conditioned_v1"
    assert config.ppo.thesis_conditioned.embedding_dim == 32
    assert config.ppo.thesis_conditioned.execution_hidden_dim == 128


@pytest.mark.parametrize("use_tick_execution", [False, True], ids=["bar-open", "tick-fill"])
def test_d_e_f_g_fixed_action_simulator_trace_is_identical(use_tick_execution: bool) -> None:
    """Encoder selection must not change environment transitions for fixed actions."""
    overlays = (
        "thesis_mtf_reasoning_conditioned_2m.yaml",
        "thesis_mtf_shared_tcn_2m.yaml",
        "thesis_mtf_m1_htf_lite_2m.yaml",
        "thesis_mtf_m1_htf_snapshot_2m.yaml",
    )
    bars = _make_bars(120)
    features = _make_features(bars)
    thesis_columns = [name for _, name in thesis_candidate_feature_columns()]
    strategy_columns = list(PO3IFVGStrategy.required_features)
    features = pd.concat(
        [
            features,
            pd.DataFrame(0.0, index=features.index, columns=strategy_columns, dtype=np.float32),
            pd.DataFrame(0.0, index=features.index, columns=thesis_columns, dtype=np.float32),
        ],
        axis=1,
    )
    candidate_id = thesis_candidate_id("po3", "M1", 1)
    candidate_column = dict(thesis_candidate_feature_columns())[candidate_id]
    features[candidate_column] = 1.0
    # Give the shared simulator a valid structural stop and a reachable target
    # so this parity trace verifies an executed open/fill, not only a
    # no-position transition for an eligible thesis.
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
        assert all(observation["thesis_mask"][candidate_id] == 1.0 for observation in observations)
        for key in observations[0]:
            for observation in observations[1:]:
                np.testing.assert_array_equal(observations[0][key], observation[key])

        entry_action = np.zeros(envs[0].action_space.shape, dtype=np.float32)
        entry_action[0] = thesis_center(candidate_id)
        schema = envs[0].action_schema
        assert isinstance(schema, ThesisActionSchema)
        entry_action[schema.indices["risk"]] = 1.0
        entry_action[schema.indices["target"]] = -1.0
        entry_action[schema.indices["exit"]] = -1.0
        transitions = [env.step(entry_action) for env in envs]
        reference = transitions[0]
        for transition in transitions[1:]:
            for key in reference[0]:
                np.testing.assert_array_equal(reference[0][key], transition[0][key])
            assert reference[1:4] == transition[1:4]
            assert reference[4] == transition[4]
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
                "thesis_candidate_id",
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
    control = load_config(config_path="config/research/thesis_mtf_reasoning_2m.yaml")
    treatment = load_config(config_path="config/research/thesis_mtf_reasoning_conditioned_2m.yaml")

    for config in (control, treatment):
        assert config.env.n_envs == 8
        assert config.env.strategy_actions is True
        assert config.env.thesis_actions is True
        assert config.features.include_strategy_state is True
        assert config.agent.arch == "mtf_reasoning"
        assert config.ppo.n_steps == 2048
        assert config.ppo.batch_size == 512
        assert config.ppo.n_epochs == 15
        assert config.ppo.total_timesteps == 2_000_000
        assert config.ppo.checkpoint_freq == 250_000
        assert config.quality_execution.requested_n_envs == 8
        assert config.quality_execution.exact_n_envs is True

    assert control.ppo.policy_distribution == "thesis_hybrid_v1"
    assert treatment.ppo.policy_distribution == "thesis_conditioned_v1"
    assert control.ppo.thesis_conditioned == treatment.ppo.thesis_conditioned
    control_resolved = OmegaConf.to_container(control, resolve=True)
    treatment_resolved = OmegaConf.to_container(treatment, resolve=True)
    assert isinstance(control_resolved, dict)
    assert isinstance(treatment_resolved, dict)
    control_resolved["ppo"].pop("policy_distribution")
    treatment_resolved["ppo"].pop("policy_distribution")
    assert control_resolved == treatment_resolved
    action_schemas = [
        build_thesis_action_schema(
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
        ("thesis_mtf_reasoning.yaml", HybridClampedStdMultiInputPolicy),
        ("thesis_mtf_reasoning_conditioned.yaml", ThesisConditionedClampedStdMultiInputPolicy),
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
    thesis_columns = [name for _, name in thesis_candidate_feature_columns()]
    strategy_columns = list(PO3IFVGStrategy.required_features)
    features = pd.concat(
        [
            features,
            pd.DataFrame(0.0, index=features.index, columns=strategy_columns, dtype=np.float32),
            pd.DataFrame(0.0, index=features.index, columns=thesis_columns, dtype=np.float32),
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
        "thesis_mask",
    } <= set(env.observation_space.spaces)
    assert observation["thesis_mask"].shape == (THESIS_CATEGORY_COUNT,)

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
    assert thesis_id_from_box(float(action[0])) == 0

    checkpoint = tmp_path / "mtf_thesis_factory_smoke.zip"
    model.save(checkpoint)
    loaded = PPO.load(checkpoint, env=env, device="cpu")
    assert isinstance(loaded.policy.features_extractor, MTFReasoningEncoder)
    assert type(loaded.policy) is expected_policy
    assert getattr(loaded, "_thesis_observation_schema", None) == env.thesis_observation_schema
    loaded_action, _ = loaded.predict(observation, deterministic=True)
    assert thesis_id_from_box(float(loaded_action[0])) == 0
