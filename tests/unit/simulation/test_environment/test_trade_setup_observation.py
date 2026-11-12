from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    TRADE_SETUP_OBSERVATION_VERSION,
    TradeSetupActionSchema,
    candidate_geometry_observation_schema,
    candidate_geometry_slot_count,
    trade_setup_candidate,
    trade_setup_candidate_id,
    trade_setup_center,
    trade_setup_id_from_box,
    validate_trade_setup_observation_schema,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from simulation.environment.candidate_geometry_observation import (
    build_candidate_geometry_observation,
)
from simulation.environment.env import TradingEnv
from tests.unit.simulation.test_environment._account_fixtures import (
    _make_bars,
    _make_features,
)


def _features_with_trade_setup_columns() -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = _make_bars(120)
    features = _make_features(bars)
    trade_setup_features = pd.DataFrame(
        0.0,
        index=features.index,
        columns=[column for _, column in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat([features, trade_setup_features], axis=1)
    active_column = "entry_idea_fvg_retest_M5_long"
    features.loc[bars.index[50], active_column] = 1.0
    return bars, features


def test_trade_setup_observation_mask_is_exact_and_optional() -> None:
    bars, features = _features_with_trade_setup_columns()
    trade_setup_env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    assert trade_setup_env.trade_setup_observation_schema is not None
    assert (
        trade_setup_env.trade_setup_observation_schema["version"] == TRADE_SETUP_OBSERVATION_VERSION
    )
    assert isinstance(trade_setup_env.observation_space, spaces.Dict)
    assert trade_setup_env.observation_space["trade_setup_mask"].shape == (
        TRADE_SETUP_CATEGORY_COUNT,
    )

    trade_setup_env.step_idx = 49
    previous = trade_setup_env._get_observation()["trade_setup_mask"]
    trade_setup_env.step_idx = 50
    current = trade_setup_env._get_observation()["trade_setup_mask"]
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    assert previous[NO_TRADE_ID] == current[NO_TRADE_ID] == 1.0
    assert previous[candidate_id] == 0.0
    assert current[candidate_id] == 1.0
    assert current[trade_setup_candidate_id("fvg_retest", "M1", 1)] == 0.0
    assert current[trade_setup_candidate_id("fvg_retest", "M5", -1)] == 0.0
    assert int(current.sum()) == 2

    env_without_trade_setup = TradingEnv(
        bars=bars, features=features, obs_window=10, strategy_actions=True
    )
    observation, _ = env_without_trade_setup.reset(seed=3)
    assert "trade_setup_mask" not in observation
    assert isinstance(env_without_trade_setup.observation_space, spaces.Dict)
    assert "trade_setup_mask" not in env_without_trade_setup.observation_space
    assert env_without_trade_setup.trade_setup_observation_schema is None


def test_candidate_masks_are_history_independent_and_timeframe_scoped() -> None:
    bars, features = _features_with_trade_setup_columns()
    features.loc[bars.index[50], "entry_idea_fvg_retest_M1_long"] = 1.0
    features["M5_history_probe"] = np.arange(len(features), dtype=np.float64) + 1.0
    common: dict[str, Any] = dict(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        trade_setup_candidate_timeframes=("M1", "M5"),
        mtf=True,
    )
    b_env = TradingEnv(**common, completed_htf_history_enabled=False)
    c_env = TradingEnv(**common, completed_htf_history_enabled=True)
    for env in (b_env, c_env):
        env.step_idx = 50
    b_mask = b_env._trade_setup_mask_for_step()
    c_mask = c_env._trade_setup_mask_for_step()
    np.testing.assert_array_equal(b_mask, c_mask)
    assert b_env.trade_setup_observation_schema != c_env.trade_setup_observation_schema
    b_observation = b_env._get_observation()
    c_observation = c_env._get_observation()
    np.testing.assert_array_equal(b_observation["seq"], c_observation["seq"])
    assert isinstance(b_env.observation_space, spaces.Dict)
    assert isinstance(c_env.observation_space, spaces.Dict)
    assert b_env.observation_space.spaces.keys() == c_env.observation_space.spaces.keys()
    assert {key: space.shape for key, space in b_env.observation_space.spaces.items()} == {
        key: space.shape for key, space in c_env.observation_space.spaces.items()
    }
    assert b_observation["seq_m5"].shape == c_observation["seq_m5"].shape
    assert b_observation["mask_m5"].shape == c_observation["mask_m5"].shape
    assert not b_observation["seq_m5"].any()
    assert not b_observation["mask_m5"].any()
    assert b_observation["seq_mask"].any()
    assert "seq_m5" in c_observation
    assert c_observation["mask_m5"].any()
    assert c_observation["seq_m5"].any()
    from models.encoders.mtf_reasoning import MTFReasoningEncoder

    encoder_kwargs: dict[str, Any] = {
        "latent_dim": 8,
        "channels": (4, 8),
        "attention_heads": 2,
        "feedforward_dim": 16,
        "dropout": 0.0,
    }
    b_encoder = MTFReasoningEncoder(b_env.observation_space, **encoder_kwargs)
    c_encoder = MTFReasoningEncoder(c_env.observation_space, **encoder_kwargs)
    assert sum(parameter.numel() for parameter in b_encoder.parameters()) == sum(
        parameter.numel() for parameter in c_encoder.parameters()
    )
    import torch

    b_encoder.eval()
    masked_input = {
        key: torch.as_tensor(value).unsqueeze(0) for key, value in b_observation.items()
    }
    perturbed_input = {key: value.clone() for key, value in masked_input.items()}
    for key, value in perturbed_input.items():
        if key.startswith("seq_") and key != "seq_mask":
            value.fill_(1e6)
    with torch.no_grad():
        torch.testing.assert_close(b_encoder(masked_input), b_encoder(perturbed_input))
    assert not any(name.startswith("entry_idea_") for name in b_env._obs_columns)
    probe_idx = c_env._obs_columns.index("M5_history_probe")
    c_env._obs_features_arr[51:, probe_idx] = 1e9
    np.testing.assert_array_equal(c_env._get_observation()["seq_m5"], c_observation["seq_m5"])
    b_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    c_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    assert b_mask[b_id] == c_mask[b_id] == 1.0
    assert b_mask[c_id] == c_mask[c_id] == 1.0
    assert trade_setup_id_from_box(trade_setup_center(c_id)) == c_id
    assert b_env.trade_setup_observation_schema is not None
    assert c_env.trade_setup_observation_schema is not None
    assert (
        b_env.trade_setup_observation_schema["candidate_timeframes"]
        == c_env.trade_setup_observation_schema["candidate_timeframes"]
    )
    assert (
        b_env.trade_setup_observation_schema["eligible_candidate_ids"]
        == c_env.trade_setup_observation_schema["eligible_candidate_ids"]
    )
    assert not b_env.trade_setup_observation_schema["completed_htf_history_enabled"]
    assert c_env.trade_setup_observation_schema["completed_htf_history_enabled"]
    with pytest.raises(ValueError, match="schema differs"):
        validate_trade_setup_observation_schema(
            b_env.trade_setup_observation_schema, c_env.trade_setup_observation_schema
        )

    b_env._obs_features_arr[:] = 0.0
    np.testing.assert_array_equal(b_env._trade_setup_mask_for_step(), b_mask)

    a_env = TradingEnv(**{**common, "trade_setup_candidate_timeframes": ("M1",), "mtf": False})
    a_env.step_idx = 50
    a_mask = a_env._trade_setup_mask_for_step()
    assert a_mask[b_id] == 1.0
    assert a_mask[c_id] == 0.0
    assert a_env.trade_setup_observation_schema is not None
    assert a_env.trade_setup_observation_schema["candidate_timeframes"] == ["M1"]
    a_eligible_ids = a_env.trade_setup_observation_schema["eligible_candidate_ids"]
    assert isinstance(a_eligible_ids, list)
    assert c_id not in a_eligible_ids
    geometry_schema = candidate_geometry_observation_schema(("M1",))
    geometry_eligible_ids = geometry_schema["eligible_candidate_ids"]
    assert isinstance(geometry_eligible_ids, list)
    assert c_id not in geometry_eligible_ids
    geometry = build_candidate_geometry_observation(
        SimpleNamespace(
            step_idx=0,
            _n_bars=10,
            _trade_setup_candidate_ids=np.asarray([b_id]),
            candidate_geometry_actions=False,
        )
    )
    assert geometry["candidate_ids"][candidate_geometry_slot_count() - 1] == 0
    assert b_id in geometry["candidate_ids"]


def test_m1_reference_target_timeframes_are_execution_only() -> None:
    from configuration.configuration_loader import load_config

    config = load_config(config_path="config/research/m1_opportunity_reference.yaml")
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        trade_setup_candidate_timeframes=tuple(config.env.trade_setup_candidate_timeframes),
        target_timeframes=tuple(config.risk.target_timeframes),
    )
    env.step_idx = 50
    observation = env._get_observation()
    schema = env.trade_setup_observation_schema
    assert schema is not None
    m1_candidate_ids = [
        candidate_id
        for candidate_id in range(1, TRADE_SETUP_CATEGORY_COUNT)
        if trade_setup_candidate(candidate_id).setup_timeframe == "M1"
    ]

    assert list(config.features.entry_ideas.timeframes) == ["M1"]
    assert list(config.data.timeframes) == ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]
    assert list(config.features.htf_timeframes) == [
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
    ]
    assert list(config.risk.target_timeframes) == [
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
    ]
    assert schema["candidate_timeframes"] == ["M1"]
    assert schema["eligible_candidate_ids"] == m1_candidate_ids
    assert schema["candidate_count"] == TRADE_SETUP_CATEGORY_COUNT
    assert set(np.flatnonzero(observation["trade_setup_mask"])) <= {NO_TRADE_ID, *m1_candidate_ids}
    assert set(observation) == {"seq", "seq_mask", "account", "trade_setup_mask"}
    assert "candidate_ids" not in observation and not env.candidate_geometry_actions
    assert "seq_m5" not in observation
    assert env._target_timeframes == tuple(config.risk.target_timeframes)
    assert "target_timeframes" not in schema


def test_bundle_candidate_mask_matches_frame_candidate_contract(tmp_path) -> None:
    from omegaconf import OmegaConf

    from simulation.environment.bundles import build_env_bundle
    from trading.strategies import BaselineStrategy

    bars, features = _features_with_trade_setup_columns()
    common: dict[str, Any] = {
        "obs_window": 10,
        "strategy_actions": True,
        "trade_setup_actions": True,
        "trade_setup_candidate_timeframes": ("M1", "M5"),
    }
    frame_env = TradingEnv(bars=bars, features=features, **common)
    frame_env.step_idx = 50
    bundle_path = build_env_bundle(
        tmp_path,
        bars,
        features,
        OmegaConf.create({"env": common, "data": {"raw_dir": str(tmp_path)}}),
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="candidate-mask-test-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )
    bundle_env = TradingEnv.from_bundle(bundle_path, **common)
    bundle_env.step_idx = 50
    np.testing.assert_array_equal(
        frame_env._trade_setup_mask_for_step(), bundle_env._trade_setup_mask_for_step()
    )
    assert frame_env.trade_setup_observation_schema == bundle_env.trade_setup_observation_schema


@pytest.mark.parametrize(
    ("saved_timeframes", "requested_timeframes"),
    [(("M1",), ("M1", "M5")), (("M1", "M5"), ("M1",))],
)
def test_bundle_rejects_candidate_timeframe_contract_mismatch(
    tmp_path, saved_timeframes, requested_timeframes
) -> None:
    from omegaconf import OmegaConf

    from simulation.environment.bundles import build_env_bundle
    from trading.strategies import BaselineStrategy

    bars, features = _features_with_trade_setup_columns()
    bundle_config = {
        "obs_window": 10,
        "strategy_actions": True,
        "trade_setup_actions": True,
        "trade_setup_candidate_timeframes": saved_timeframes,
    }
    bundle_path = build_env_bundle(
        tmp_path,
        bars,
        features,
        OmegaConf.create({"env": bundle_config, "data": {"raw_dir": str(tmp_path)}}),
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="candidate-timeframe-contract-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )

    with pytest.raises(ValueError, match="requested trade setup candidate timeframes"):
        TradingEnv.from_bundle(
            bundle_path,
            **{**bundle_config, "trade_setup_candidate_timeframes": requested_timeframes},
        )


def test_bundle_history_ablation_preserves_opportunities_and_shapes(tmp_path) -> None:
    from omegaconf import OmegaConf

    from simulation.environment.bundles import build_env_bundle
    from trading.strategies import BaselineStrategy

    bars, features = _features_with_trade_setup_columns()
    features["M5_history_probe"] = np.arange(len(features), dtype=np.float64) + 1.0
    common: dict[str, Any] = {
        "obs_window": 10,
        "strategy_actions": True,
        "trade_setup_actions": True,
        "trade_setup_candidate_timeframes": ("M1", "M5"),
        "mtf": True,
    }
    strategy_columns = BaselineStrategy().raw_columns
    bundle_paths = {}
    envs = {}
    for history_enabled in (False, True):
        env_config = {**common, "completed_htf_history_enabled": history_enabled}
        bundle_paths[history_enabled] = build_env_bundle(
            tmp_path,
            bars,
            features,
            OmegaConf.create({"env": env_config, "data": {"raw_dir": str(tmp_path)}}),
            raw_columns=strategy_columns,
            feature_config_hash="candidate-history-v1",
            tickbook=None,
            pre_ny_by_date=None,
        )
        envs[history_enabled] = TradingEnv.from_bundle(bundle_paths[history_enabled], **env_config)
        envs[history_enabled].step_idx = 50

    assert bundle_paths[False] != bundle_paths[True]
    hidden_obs = envs[False]._get_observation()
    visible_obs = envs[True]._get_observation()
    assert hidden_obs.keys() == visible_obs.keys()
    assert hidden_obs["seq_m5"].shape == visible_obs["seq_m5"].shape
    assert hidden_obs["mask_m5"].shape == visible_obs["mask_m5"].shape
    assert not hidden_obs["seq_m5"].any() and not hidden_obs["mask_m5"].any()
    assert visible_obs["seq_m5"].any() and visible_obs["mask_m5"].any()
    np.testing.assert_array_equal(hidden_obs["trade_setup_mask"], visible_obs["trade_setup_mask"])
    hidden_schema = envs[False].trade_setup_observation_schema
    visible_schema = envs[True].trade_setup_observation_schema
    assert hidden_schema is not None
    assert visible_schema is not None
    assert hidden_schema["eligible_candidate_ids"] == visible_schema["eligible_candidate_ids"]
    with pytest.raises(ValueError, match="history mode differs"):
        TradingEnv.from_bundle(
            bundle_paths[False], **{**common, "completed_htf_history_enabled": True}
        )


def test_candidate_geometry_is_wired_into_real_environment_observations() -> None:
    bars, features = _features_with_trade_setup_columns()
    close_date = bars.index[50].date().isoformat()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        candidate_geometry_actions=True,
        agent_entry_execution=True,
        scheduled_session_closes={close_date: "23:59"},
        session_start="00:00",
    )
    env.step_idx = 50

    observation = env._get_observation()

    count = candidate_geometry_slot_count()
    assert observation["candidate_ids"].shape == (count,)
    assert observation["candidate_features"].shape == (
        count,
        len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
    )
    assert observation["candidate_mask"].dtype == np.bool_
    assert observation["candidate_mask"][0]
    assert isinstance(env.observation_space, spaces.Dict)
    candidate_mask_space = env.observation_space.spaces["candidate_mask"]
    assert isinstance(candidate_mask_space, spaces.Box)
    assert candidate_mask_space.dtype == np.bool_


def test_step_returns_candidate_mask_for_next_decision_row() -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
    )
    env.reset(seed=3)
    env.step_idx = 49
    env._ny_pos = int(np.searchsorted(env._ny_indices, env.step_idx))
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    assert isinstance(env.action_schema, TradeSetupActionSchema)
    action = np.zeros(env.action_schema.width, dtype=np.float32)
    action[env.action_schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)

    next_observation, _, terminated, truncated, _ = env.step(action)

    assert not terminated
    assert not truncated
    assert env.step_idx == 50
    assert next_observation["trade_setup_mask"][candidate_id] == 1.0
    np.testing.assert_array_equal(
        next_observation["trade_setup_mask"], env._trade_setup_mask_for_step()
    )


def test_trade_setup_observation_requires_strategy_overlay_and_idea_features() -> None:
    bars, features = _features_with_trade_setup_columns()
    with pytest.raises(ValueError, match="trade setup actions require strategy_actions=true"):
        TradingEnv(bars=bars, features=features, obs_window=10, trade_setup_actions=True)

    with pytest.raises(ValueError, match="per-timeframe entry-idea"):
        TradingEnv(
            bars=bars,
            features=_make_features(bars),
            obs_window=10,
            strategy_actions=True,
            trade_setup_actions=True,
        )


def test_trade_setup_decoder_uses_selected_direction_and_rejects_inactive_candidate() -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        allow_multi_tp=True,
        allow_agent_sl_mode=True,
        allow_agent_tp_mode=True,
        allow_simplex=True,
    )
    env.step_idx = 50
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    active_id = trade_setup_candidate_id("fvg_retest", "M5", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(active_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 1
    assert risk > 0.0
    assert env._selected_trade_setup is not None
    assert env._selected_trade_setup.candidate_id == active_id

    action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0

    inactive_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    action[schema.indices["trade_setup"]] = trade_setup_center(inactive_id)
    direction, risk, _, _ = env._decode_action(action, features.iloc[50])
    assert direction == 0
    assert risk == 0.0
    assert env._selected_trade_setup is None


def test_delayed_entry_keeps_the_selected_primary_trade_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars, features = _features_with_trade_setup_columns()
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        fill_latency_bars=1,
    )
    primary = trade_setup_candidate(trade_setup_candidate_id("fvg_retest", "M5", 1))
    later_context = trade_setup_candidate(trade_setup_candidate_id("order_block", "H1", -1))
    env._selected_trade_setup = primary
    env.step_idx = 50
    when = env._bar_time(50)
    bar = env._bar_at(50)
    feat_row = env._feature_row_at(50)
    action = np.zeros(env.action_schema.width, dtype=np.float32)

    env._execute_step_action(
        action=action,
        discrete_action=1,
        risk_frac=0.005,
        rr_ratio=2.0,
        bar=bar,
        feat_row=feat_row,
        bar_time=when,
        session_id=env._current_session_id(),
        fill_idx=51,
        action_fill_time=env._bar_time(51),
        fill_bid=bar.open,
        fill_ask=bar.open + 0.6,
        fill_time=when,
        entry_fill_bid=bar.open,
        entry_fill_ask=bar.open + 0.6,
        entry_fill_time=when,
        market_fill_idx=51,
        entry_candidate=None,
        done=False,
        pending_due=False,
        session_blocked=False,
        peak_dd_block=False,
    )
    pending = env._pending_entry_order
    assert pending is not None
    assert pending["selected"]["_selected_trade_setup"].candidate_id == primary.candidate_id
    assert env.trade_log[-1]["type"] == "order_submit"
    assert env.trade_log[-1]["trade_setup_candidate_id"] == primary.candidate_id
    assert env.trade_log[-1]["primary_setup_timeframe"] == "M5"
    assert env.trade_log[-1]["decision_bar_time"] == when
    completed_bar_time = when + pd.Timedelta(minutes=env._minutes_per_step)
    assert env.trade_log[-1]["decision_time"] == completed_bar_time
    assert env.trade_log[-1]["signal_time"] == completed_bar_time
    assert env.trade_log[-1]["order_submission_time"] == completed_bar_time

    entered_trade_setups: list[int | None] = []

    def capture_entry(self: TradingEnv, *args: object, **kwargs: object) -> None:
        selected = self._selected_trade_setup
        entered_trade_setups.append(selected.candidate_id if selected is not None else None)

    monkeypatch.setattr(TradingEnv, "_try_enter_position", capture_entry)
    env._selected_trade_setup = later_context
    env._enforce_step_constraints(
        env._bar_at(51),
        env._feature_row_at(51),
        env._bar_time(51),
        env._current_session_id(),
        float(bars.iloc[51]["open"]),
        float(bars.iloc[51]["open"] + 0.6),
        env._bar_time(51),
        pending_due=True,
        entry_fill_bid=float(bars.iloc[51]["open"]),
        entry_fill_ask=float(bars.iloc[51]["open"] + 0.6),
        entry_fill_time=env._bar_time(51),
        market_fill_idx=51,
    )

    assert entered_trade_setups == [primary.candidate_id]
    assert env._selected_trade_setup == later_context
    assert env._pending_entry_order is None
