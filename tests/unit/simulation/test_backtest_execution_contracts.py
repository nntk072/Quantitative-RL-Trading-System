"""Event-backtest execution timing, quote, and configuration contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from decisioning.observations import build_observation_schema
from decisioning.trade_setup import (
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from market_data.loading.ticks import TickBook, TickExecutionUnavailable
from simulation.backtest.cross_validation import run as cross_validation
from simulation.backtest.event_driven_backtest import (
    _bar_duration,
    _decision_valuation_time,
    _entry_state_diagnostics,
    _geometry_action_record,
    _is_last_ny_bar,
    _ny_gap_guard_mask,
    _policy_action,
    _scalar_policy_action,
    run_backtest,
)
from simulation.backtest.quotes import (
    _bar_quote,
    _bar_spread_price_units,
    _fill_quote,
    _fill_quote_event,
    _sl_tp_fill_quote,
)
from simulation.entry_state import EntryStateMachine
from trading.execution import CostModel
from trading.policy.config import TradingPolicyConfig


def test_policy_action_requires_a_single_integer_and_accepts_named_observations() -> None:
    named: Mapping[str, np.ndarray[Any, Any]] = {"seq": np.asarray([1.0])}
    assert _scalar_policy_action(lambda obs: 1 if "seq" in obs else 0, named) == 1
    assert _scalar_policy_action(cast(Any, lambda _obs: np.int64(-1)), np.asarray([2.0])) == -1
    for invalid in (True, np.bool_(False), 1.0, np.asarray([1])):
        with pytest.raises(TypeError, match="one integer scalar action"):
            _scalar_policy_action(lambda _obs, value=invalid: value, np.asarray([0.0]))


def test_entry_diagnostics_report_visit_rates_with_safe_zero_denominators() -> None:
    machine = EntryStateMachine(candidate_max_age_bars=2)
    assert _entry_state_diagnostics(None, decision_count=0) == {}
    machine.visits["FLAT"] = 2
    machine.entered = 1
    machine.armed_bars = 0
    machine.trigger_refused = 1
    record = _entry_state_diagnostics(machine, decision_count=0)

    assert record["entry_state_share"]["FLAT"] == 2.0
    assert record["arm_to_trigger_rate"] == 1.0
    assert record["trigger_refusal_rate"] == 1.0
    assert record["candidate_created"] == 0


def test_geometry_event_record_preserves_explicit_modes_and_coordinates() -> None:
    from decisioning.trade_setup import TradeSetupGeometryChoice

    choice = TradeSetupGeometryChoice(
        stop_anchor_fraction=0.25,
        target_fraction=0.75,
        target_selections=(0.2, 0.3, 0.5),
        simplex_logits=(0.1, -0.1),
        exit_mode="ema_21",
        sl_mode="trailing",
        sl_mode_explicit=True,
        has_sl_mode=True,
        tp_mode="breakeven",
        tp_mode_explicit=True,
        has_tp_mode=True,
    )

    assert _geometry_action_record(None) is None
    assert _geometry_action_record(choice) == {
        "stop_anchor_fraction": 0.25,
        "target_fraction": 0.75,
        "target_selections": (0.2, 0.3, 0.5),
        "simplex_logits": (0.1, -0.1),
        "exit_mode": "ema_21",
        "sl_mode": "trailing",
        "sl_mode_explicit": True,
        "has_sl_mode": True,
        "tp_mode": "breakeven",
        "tp_mode_explicit": True,
        "has_tp_mode": True,
    }


def test_event_time_uses_latest_matching_fill_and_falls_back_to_boundary() -> None:
    boundary = pd.Timestamp("2026-01-05 17:00", tz="UTC")
    events = [
        {"type": "open", "bar": 3, "fill_time": boundary - pd.Timedelta(minutes=1)},
        {"type": "sl_update", "bar": 4, "time": boundary},
        {
            "type": "close",
            "bar": 3,
            "actual_tick_time": None,
            "fill_time": boundary - pd.Timedelta(seconds=2),
        },
        {"type": "close", "bar": "invalid", "time": boundary},
    ]

    assert _decision_valuation_time(boundary, events, 3) == boundary - pd.Timedelta(seconds=2)
    assert _decision_valuation_time(boundary, [], 3) == boundary


def test_bar_duration_and_session_edge_guards_cover_gaps_and_terminal_bars() -> None:
    idx = pd.DatetimeIndex(
        [
            "2026-01-05 16:30",
            "2026-01-05 16:31",
            "2026-01-05 16:32",
            "2026-01-05 16:34",
        ],
        tz="UTC",
    )
    bars = pd.DataFrame(
        {"session": ["ny", "ny", "london", "ny"], "session_id": [1, 1, 1, 2]},
        index=idx,
    )

    assert _bar_duration(pd.DatetimeIndex([])) == pd.Timedelta(minutes=1)
    assert _bar_duration(pd.DatetimeIndex([idx[0]])) == pd.Timedelta(minutes=1)
    assert _bar_duration(pd.DatetimeIndex([idx[0], idx[0]])) == pd.Timedelta(minutes=1)
    assert _bar_duration(idx) == pd.Timedelta(minutes=1)
    assert not _is_last_ny_bar(bars, 0, False)
    assert not _is_last_ny_bar(bars, 0, True)
    assert _is_last_ny_bar(bars, 1, True)
    assert not _is_last_ny_bar(bars, 2, False)
    assert _is_last_ny_bar(bars.iloc[:1], 0, True)
    np.testing.assert_array_equal(_ny_gap_guard_mask(bars), [False, True, False, False])
    np.testing.assert_array_equal(
        _ny_gap_guard_mask(pd.DataFrame(index=idx)), [False, False, False, False]
    )


def test_quote_helpers_convert_bar_spread_and_protective_levels() -> None:
    cost = CostModel(spread_points=0.6, slippage_points=0.2, point_size=0.01)
    row = pd.Series({"open": 100.0, "close": 100.2, "low": 99.0, "high": 101.0, "spread": 25})

    assert _bar_spread_price_units(row, cost) == pytest.approx(0.25)
    assert _bar_spread_price_units(pd.Series({"spread": np.nan}), cost) is None
    assert _bar_spread_price_units(pd.Series(dtype=float), cost) is None
    assert _bar_quote(row, cost) == pytest.approx((100.2, 100.45))
    assert _bar_quote(row.drop(labels="spread"), cost) == pytest.approx((100.2, 100.8))
    assert _sl_tp_fill_quote(1, 99.0, cost) == pytest.approx((98.8, 99.4))
    assert _sl_tp_fill_quote(-1, 101.0, cost) == pytest.approx((100.6, 101.2))


def test_fill_quote_event_uses_bar_fallback_and_valid_tick_quote() -> None:
    time = pd.Timestamp("2026-01-05 16:30", tz="UTC")
    cost = CostModel(spread_points=0.6, point_size=0.01)
    row = pd.Series({"open": 100.0, "low": 99.0, "high": 101.0, "close": 100.2, "spread": 25})

    fallback = _fill_quote_event(time, row, cost, None)
    assert fallback == ((100.0, 100.25), time, "bar_open", {})
    book = TickBook(np.asarray([time.value]), np.asarray([100.1]), np.asarray([100.3]))
    tick = _fill_quote_event(time, row, cost, book)
    assert tick[0] == (100.1, 100.3)
    assert tick[1:3] == (time, "tick")
    assert tick[3]["fill_quote_source"] == "tick"
    assert _fill_quote(time, row, cost, book) == (100.1, 100.3)


def test_fill_quote_event_rejects_stale_outlier_or_missing_required_ticks() -> None:
    time = pd.Timestamp("2026-01-05 16:30", tz="UTC")
    cost = CostModel(spread_points=0.6, point_size=0.01)
    row = pd.Series({"open": 100.0, "low": 99.0, "high": 101.0, "close": 100.2})
    outlier = TickBook(np.asarray([time.value]), np.asarray([110.0]), np.asarray([110.2]))

    result = _fill_quote_event(time, row, cost, outlier)
    assert result[0] == (100.0, 100.6)
    assert result[2] == "bar_open"
    with pytest.raises(TickExecutionUnavailable, match="TickBook and RNG"):
        _fill_quote_event(time, row, cost, None, tick_execution_required=True)
    empty_book = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))
    with pytest.raises(TickExecutionUnavailable, match="no executable tick"):
        _fill_quote_event(
            time,
            row,
            cost,
            empty_book,
            rng=np.random.default_rng(0),
            tick_execution_required=True,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fill_latency_bars": True}, "fill_latency_bars"),
        ({"fill_latency_bars": 1.5}, "fill_latency_bars"),
        ({"fill_latency_bars": "invalid"}, "fill_latency_bars"),
        ({"fill_latency_bars": -1}, "fill_latency_bars"),
        ({"tick_fill_slippage_points": True}, "tick_fill_slippage_points"),
        ({"tick_fill_slippage_points": "invalid"}, "tick_fill_slippage_points"),
        ({"tick_fill_slippage_points": -0.1}, "tick_fill_slippage_points"),
        ({"server_side_protective_orders": True}, "server-side protective fills"),
        ({"randomized_fill_latency_ms": 31.0}, "randomized_fill_latency_ms"),
        ({"randomized_fill_latency_ms": -1.0}, "randomized_fill_latency_ms"),
        ({"limit_order_max_offset_atr": 0.0}, "limit_order_max_offset_atr"),
        ({"limit_order_max_ttl_bars": 0}, "limit_order_max_ttl_bars"),
        ({"limit_order_max_ttl_bars": True}, "limit_order_max_ttl_bars"),
        ({"limit_order_max_ttl_bars": 1.5}, "limit_order_max_ttl_bars"),
        ({"sl_mode": "unknown"}, "sl_mode must"),
        ({"tp_mode": "unknown"}, "tp_mode must"),
        ({"sl_mode_defer_threshold": 0.6}, "sl_mode_defer_threshold"),
        ({"tp_mode_defer_threshold": -0.1}, "tp_mode_defer_threshold"),
        ({"tp_breakeven_alpha": -0.1}, "tp_breakeven_alpha"),
        ({"sl_buffer_pts": -1.0}, "sl_buffer_pts"),
        ({"sl_buffer_pts": "invalid"}, "sl_buffer_pts"),
        ({"lot_step": 0.0}, "lot_step"),
        ({"trade_setup_action_schema": object()}, "requires trade_setup_actions"),
        ({"pre_ny_data": pd.DataFrame()}, "pre-NY VAE inputs require vae"),
        ({"vae": object()}, "vae requires pre_ny_by_date"),
        ({"candidate_max_age_bars": True}, "candidate_max_age_bars"),
        ({"arm_requires_retest": 1}, "arm_requires_retest"),
        ({"trade_setup_geometry": True}, "requires trade_setup_actions"),
        ({"min_sl_atr_mult": -0.1}, "min_sl_atr_mult"),
        ({"min_sl_atr_mult": True}, "min_sl_atr_mult"),
        ({"min_sl_points": -0.1}, "min_sl_points"),
        ({"target_timeframes": ()}, "target_timeframes"),
        (
            {"trade_setup_actions": True, "observation_age_scale_bars": 0.0},
            "observation_age_scale_bars",
        ),
        (
            {"mtf_observation": True, "mtf_windows": {"H7": 1}},
            "unsupported MTF observation window",
        ),
        (
            {"mtf_observation": True, "mtf_windows": {"H1": True}},
            "must be a positive integer",
        ),
        ({"policy_rr_ratio_range": (1.0,)}, "policy_rr_ratio_range must contain two values"),
        ({"policy_rr_ratio_range": (2.0, 1.0)}, "policy_rr_ratio_range"),
        ({"ema_runner_fraction": 1.0}, "ema_runner_fraction"),
        ({"open_manipulation_bars": True}, "open_manipulation_bars"),
        ({"broker_kwargs": {"contract_size": 2.0}}, "broker_kwargs.contract_size must match"),
    ],
)
def test_backtest_rejects_invalid_execution_and_observation_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        run_backtest(pd.DataFrame(), pd.DataFrame(), lambda _obs: 0, **cast(Any, kwargs))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"trade_setup_actions": True, "trade_setup_action_schema": object()},
            "trade_setup_action_schema must be a TradeSetupActionSchema",
        ),
        (
            {
                "trade_setup_actions": True,
                "trade_setup_action_schema": build_trade_setup_action_schema(),
                "observation_schema": object(),
            },
            "observation_schema must be an ObservationSchema",
        ),
    ],
)
def test_backtest_rejects_wrong_action_and_observation_schema_types(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        run_backtest(pd.DataFrame(), pd.DataFrame(), lambda _obs: 0, **cast(Any, kwargs))


def test_backtest_rejects_unsupported_trading_policy_value() -> None:
    with pytest.raises(
        TypeError, match="trading_policy must be TradingPolicyConfig, a mapping, or None"
    ):
        run_backtest(
            pd.DataFrame(), pd.DataFrame(), lambda _obs: 0, trading_policy=cast(Any, object())
        )


def test_backtest_rejects_observation_schema_coordinates_that_disagree_with_version() -> None:
    malformed = replace(build_observation_schema(), coordinates=("unknown_coordinate",))

    with pytest.raises(
        ValueError, match="observation_schema coordinates disagree with its version"
    ):
        run_backtest(
            pd.DataFrame(),
            pd.DataFrame(),
            lambda _obs: 0,
            observation_schema=malformed,
        )


def test_regime_observation_requires_the_declared_feature_columns() -> None:
    with pytest.raises(ValueError, match="regime observation is missing required D1 features"):
        run_backtest(
            pd.DataFrame(),
            pd.DataFrame(),
            lambda _obs: 0,
            regime_observation=True,
        )


@pytest.mark.parametrize(("randomized", "max_wait"), [(-0.1, 100), (30.1, 100), (0.0, 0)])
def test_quote_event_rejects_invalid_latency_bounds(randomized: float, max_wait: int) -> None:
    time = pd.Timestamp("2026-01-05 16:30", tz="UTC")
    row = pd.Series({"open": 100.0, "low": 99.0, "high": 101.0})
    with pytest.raises(ValueError):
        _fill_quote_event(
            time,
            row,
            CostModel(),
            None,
            rng=np.random.default_rng(0),
            randomized_fill_latency_ms=randomized,
            max_tick_quote_wait_ms=max_wait,
        )


def test_schema_policy_action_rejects_wrong_width_and_nonfinite_action() -> None:
    from decisioning.trade_setup import build_trade_setup_action_schema

    schema = build_trade_setup_action_schema()
    common = {
        "feature_row": pd.Series({"entry_candidate_eligible": 1.0}),
        "trade_setup_schema": schema,
        "max_limit_offset_atr": 1.0,
        "max_limit_ttl_bars": 10,
        "policy_risk_frac_range": (0.01, 0.02),
        "allow_ema_exit": True,
        "default_sl_mode": "fixed",
        "default_tp_mode": "fixed",
        "sl_mode_defer_threshold": 0.1,
        "tp_mode_defer_threshold": 0.1,
    }
    with pytest.raises(ValueError, match="disagrees with schema"):
        _policy_action(lambda _obs: np.zeros(schema.width - 1), np.zeros(1), **cast(Any, common))
    with pytest.raises(ValueError, match="must all be finite"):
        _policy_action(lambda _obs: np.full(schema.width, np.nan), np.zeros(1), **cast(Any, common))


def test_schema_policy_action_requires_a_risk_coordinate() -> None:
    schema = build_trade_setup_action_schema()
    malformed = replace(schema, names=tuple(name for name in schema.names if name != "risk"))

    with pytest.raises(ValueError, match="no risk coordinate"):
        _policy_action(
            lambda _observation: np.zeros(malformed.width),
            np.zeros(1),
            feature_row=pd.Series(dtype=float),
            trade_setup_schema=malformed,
            max_limit_offset_atr=1.0,
            max_limit_ttl_bars=10,
            policy_risk_frac_range=(0.01, 0.02),
            allow_ema_exit=True,
            default_sl_mode="fixed",
            default_tp_mode="fixed",
            sl_mode_defer_threshold=0.1,
            tp_mode_defer_threshold=0.1,
        )


def test_schema_policy_action_decodes_active_candidate_execution_and_risk() -> None:
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["risk"]] = 1.0
    action[schema.indices["entry_execution"]] = -1.0
    action[schema.indices["limit_offset_atr"]] = 0.0
    action[schema.indices["limit_ttl_bars"]] = 1.0
    action[schema.indices["exit"]] = 1.0
    observed_masks: list[np.ndarray[Any, Any]] = []

    def choose_action(
        observation: np.ndarray[Any, Any] | Mapping[str, np.ndarray[Any, Any]],
    ) -> np.ndarray[Any, Any]:
        assert isinstance(observation, Mapping)
        observed_masks.append(observation["trade_setup_mask"])
        return action

    decoded = _policy_action(
        choose_action,
        np.asarray([0.0]),
        feature_row=pd.Series({"entry_idea_fvg_retest_M1_long": 1.0}),
        trade_setup_schema=schema,
        max_limit_offset_atr=2.0,
        max_limit_ttl_bars=10,
        policy_risk_frac_range=(0.005, 0.02),
        allow_ema_exit=False,
        default_sl_mode="fixed",
        default_tp_mode="fixed",
        sl_mode_defer_threshold=0.1,
        tp_mode_defer_threshold=0.1,
    )

    direction, candidate, eligible, execution, risk_frac, geometry = decoded
    assert len(observed_masks) == 1
    assert observed_masks[0][candidate_id] == 1.0
    assert direction == 1
    assert candidate is not None and candidate.candidate_id == candidate_id
    assert eligible is True
    assert execution is not None
    assert execution.order_type == "market"
    assert execution.limit_offset_atr == pytest.approx(1.0)
    assert execution.ttl_bars == 10
    assert risk_frac == pytest.approx(0.02)
    assert geometry is not None
    assert geometry.exit_mode == "structural"


def test_schema_policy_action_abstains_on_inactive_candidate() -> None:
    schema = build_trade_setup_action_schema()
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    action[schema.indices["risk"]] = 1.0

    direction, candidate, eligible, execution, risk_frac, geometry = _policy_action(
        lambda _observation: action,
        np.asarray([0.0]),
        feature_row=pd.Series(dtype=float),
        trade_setup_schema=schema,
        max_limit_offset_atr=1.0,
        max_limit_ttl_bars=10,
        policy_risk_frac_range=(0.005, 0.02),
        allow_ema_exit=True,
        default_sl_mode="fixed",
        default_tp_mode="fixed",
        sl_mode_defer_threshold=0.1,
        tp_mode_defer_threshold=0.1,
    )

    assert direction == 0
    assert candidate is not None and candidate.candidate_id == candidate_id
    assert eligible is False
    assert execution is None
    assert risk_frac == 0.0
    assert geometry is not None


def test_market_entry_without_timely_tick_is_rejected_without_opening() -> None:
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.1, 100.2, 100.3, 100.4],
            "high": [100.2, 100.3, 100.4, 100.5, 100.6],
            "low": [99.8, 99.9, 100.0, 100.1, 100.2],
            "close": [100.0, 100.1, 100.2, 100.3, 100.4],
            "session": ["ny"] * 5,
            "session_id": [1] * 5,
        },
        index=pd.date_range("2026-02-02 14:30", periods=5, freq="min", tz="UTC"),
    )
    features = pd.DataFrame(index=bars.index)
    actions = iter((1, 0, 0, 0))
    empty_book = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        tickbook=empty_book,
        tick_execution_required=True,
        hold_on_zero=True,
        block_overnight=False,
    )

    rejects = result["trades"].loc[result["trades"]["type"].eq("reject")]
    assert len(rejects) == 1
    assert rejects.iloc[0]["reason"] == "no_executable_tick_within_wait"
    assert not result["trades"]["type"].eq("open").any()
    assert result["account"].balance == 10_000.0


def test_repeated_payout_risk_capacity_refusal_keeps_account_unchanged() -> None:
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.1, 100.2, 100.3, 100.4],
            "high": [100.2, 100.3, 100.4, 100.5, 100.6],
            "low": [99.8, 99.9, 100.0, 100.1, 100.2],
            "close": [100.0, 100.1, 100.2, 100.3, 100.4],
            "session": ["ny"] * 5,
            "session_id": [1] * 5,
        },
        index=pd.date_range("2026-02-02 14:30", periods=5, freq="min", tz="UTC"),
    )
    features = pd.DataFrame(
        {"last_swing_low": [99.0] * 5, "last_swing_high": [102.0] * 5}, index=bars.index
    )
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=10_000.0,
        profit_target_balance=11_000.0,
        account_floor=9_000.0,
        daily_loss_limit_pct=0.2,
        max_agent_risk_frac=0.009,
    ).validate()
    actions = iter((1, 0, 0, 0))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        trading_policy=policy,
        use_structure_sl_tp=True,
        risk_frac=0.009,
        max_loss_per_trade_usd=0.001,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    rejects = result["trades"].loc[result["trades"]["type"].eq("reject")]
    assert len(rejects) == 1
    assert rejects.iloc[0]["reason"] == "risk_capacity"
    assert rejects.iloc[0]["approved_risk_usd"] == pytest.approx(0.001)
    assert rejects.iloc[0]["all_in_risk_usd"] == 0.0
    assert not result["trades"]["type"].eq("open").any()
    assert result["account"].balance == 10_000.0


def test_cross_validation_engines_consume_one_aligned_action_tape() -> None:
    index = pd.date_range("2026-02-02 14:30", periods=6, freq="min", tz="UTC")
    close = np.asarray([100.0, 100.0, 101.0, 102.0, 101.0, 101.0])
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.ones(len(index)),
        },
        index=index,
    )
    actions = pd.Series([0, 1, 0, 2, 0, 0], index=index, dtype="int64")

    backtrader_result = cross_validation.run_backtrader_engine(bars, actions=actions)
    custom_result = cross_validation.run_custom_engine(bars, actions=actions)
    comparison = cross_validation.compare_results(backtrader_result, custom_result)

    assert backtrader_result["engine"] == "backtrader"
    assert custom_result["engine"] == "custom"
    assert backtrader_result["trade_count"] == custom_result["trade_count"] == 1
    assert backtrader_result["open_position_size"] == 0.0
    assert isinstance(comparison["agreement"]["overall_pass"], bool)


@pytest.mark.parametrize("engine_name", ["backtrader", "custom"])
def test_cross_validation_engines_reject_misaligned_action_timestamps(
    engine_name: str,
) -> None:
    index = pd.date_range("2026-02-02 14:30", periods=2, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1.0, 1.0],
        },
        index=index,
    )
    actions = pd.Series([0, 1], index=index + pd.Timedelta(minutes=1), dtype="int64")
    engine = (
        cross_validation.run_backtrader_engine
        if engine_name == "backtrader"
        else cross_validation.run_custom_engine
    )

    with pytest.raises(ValueError, match="actions must align exactly"):
        engine(bars, actions=actions)
