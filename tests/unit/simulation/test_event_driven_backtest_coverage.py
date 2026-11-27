"""Public event-backtest lifecycle and accounting contracts."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

from decisioning.observations import (
    OBSERVATION_SCHEMA_V1,
    OBSERVATION_SCHEMA_V2,
    build_observation_schema,
)
from decisioning.regime_observations import REGIME_FEATURES
from decisioning.trade_setup import (
    NO_TRADE_ID,
    build_trade_setup_action_schema,
    trade_setup_candidate_id,
    trade_setup_center,
)
from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns
from market_data.loading.ticks import TickBook, TickExecutionUnavailable
from simulation.backtest import run_backtest
from trading.execution import CostModel
from trading.policy.config import TradingPolicyConfig
from trading.strategies import BaselineStrategy


def _market_frame(n: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2026-02-02 14:30", periods=n, freq="min", tz="UTC")
    close = 100.0 + np.arange(n, dtype=float) * 0.1
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "spread": 0.0,
            "session_id": 1,
            "session": "ny",
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "atr_5": 1.0,
            "last_swing_low": close - 1.0,
            "last_swing_high": close + 1.0,
        },
        index=index,
    )
    return bars, features


def test_no_trade_run_returns_complete_typed_result_surfaces() -> None:
    bars, features = _market_frame()

    result = run_backtest(
        bars,
        features,
        lambda _observation: 0,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        block_overnight=False,
    )

    assert result["trades"].empty
    assert result["trades"].columns.tolist() == ["type"]
    assert isinstance(result["equity"], pd.Series)
    assert result["equity"].index.equals(result["equity_valuation_times"])
    assert result["account_state_trace_complete"] is True
    assert result["policy_decisions_complete"] is True
    assert len(result["account_state_trace"]) == len(result["policy_decisions"]) + 1
    assert result["account"].balance == 10_000.0
    assert result["execution_contract"]["schema_version"] == "backtest_execution_contract.v1"
    assert result["execution_contract"]["market_fill"]["slippage_points"] == 0.0


def test_regime_observation_exposes_zero_filled_values_and_per_feature_mask() -> None:
    bars, features = _market_frame()
    for offset, name in enumerate(REGIME_FEATURES):
        features[name] = float(offset + 1)
    features[REGIME_FEATURES[0]] = np.nan
    captured: list[dict[str, np.ndarray[Any, Any]]] = []

    def capture_observation(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured.append(cast(dict[str, np.ndarray[Any, Any]], observation))
        return 0

    run_backtest(
        bars,
        features,
        capture_observation,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        regime_observation=True,
        block_overnight=False,
    )

    assert captured
    regime = captured[0]["regime"]
    mask = captured[0]["regime_mask"]
    assert regime.shape == mask.shape == (len(REGIME_FEATURES),)
    assert mask.dtype == regime.dtype == np.float32
    assert mask[0] == 0.0
    assert regime[0] == 0.0
    assert np.all(mask[1:] == 1.0)


class _MeanSequenceVae:
    """Tiny encoder whose latent exposes the sequence values supplied by backtest."""

    def __init__(self) -> None:
        import torch

        self.encoder = SimpleNamespace(latent_dim=1, seq_len=3, n_features=2)
        self._parameter = torch.nn.Parameter(torch.zeros(1))

    def parameters(self) -> Any:
        return iter((self._parameter,))

    def encode(self, sequence: Any) -> tuple[Any, Any]:
        import torch

        latent = sequence.mean(dim=1)[:, :1]
        return latent, torch.zeros_like(latent)


def test_vae_observation_uses_zero_latent_when_date_has_no_pre_ny_sequence() -> None:
    bars, features = _market_frame()
    captured: list[dict[str, np.ndarray[Any, Any]]] = []

    def capture(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured.append(cast(dict[str, np.ndarray[Any, Any]], observation))
        return 0

    run_backtest(
        bars,
        features,
        capture,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        vae=_MeanSequenceVae(),
        pre_ny_by_date={pd.Timestamp("2026-02-03").date(): np.ones((3, 2), dtype=np.float32)},
        block_overnight=False,
    )

    assert captured
    assert captured[0]["vae_z"].shape == (1,)
    assert captured[0]["vae_z"] == pytest.approx(np.zeros(1, dtype=np.float32))


def test_vae_observation_encodes_legacy_flattened_pre_ny_sequence() -> None:
    bars, features = _market_frame()
    captured: list[dict[str, np.ndarray[Any, Any]]] = []
    sequence = np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32)

    def capture(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured.append(cast(dict[str, np.ndarray[Any, Any]], observation))
        return 0

    run_backtest(
        bars,
        features,
        capture,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        vae=_MeanSequenceVae(),
        pre_ny_data=pd.DataFrame(
            np.tile(sequence.reshape(1, -1), (len(bars), 1)), index=bars.index
        ),
        block_overnight=False,
    )

    assert captured
    assert captured[0]["vae_z"] == pytest.approx(np.asarray([3.0], dtype=np.float32))


def test_vae_observation_pads_short_pre_ny_sequence_without_looking_ahead() -> None:
    bars, features = _market_frame()
    captured: list[dict[str, np.ndarray[Any, Any]]] = []

    def capture(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured.append(cast(dict[str, np.ndarray[Any, Any]], observation))
        return 0

    run_backtest(
        bars,
        features,
        capture,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        vae=_MeanSequenceVae(),
        pre_ny_by_date={bars.index[0].date(): np.asarray([[1.0], [2.0]], dtype=np.float32)},
        block_overnight=False,
    )

    assert captured
    assert captured[0]["vae_z"] == pytest.approx(np.asarray([1.0], dtype=np.float32))


def test_v2_account_observation_reports_elapsed_position_age() -> None:
    bars, features = _market_frame(n=8)
    # This observation path stores event times as naive numpy datetime64 values;
    # give the fixture the same UTC-naive representation at the public boundary.
    bars.index = pd.DatetimeIndex(bars.index).tz_convert(None)
    features.index = pd.DatetimeIndex(features.index).tz_convert(None)
    captured_accounts: list[np.ndarray[Any, Any]] = []

    def enter_once(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured_accounts.append(np.asarray(observation["account"]))
        return 1 if len(captured_accounts) == 1 else 0

    run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        lots=1.0,
        hold_on_zero=True,
        observation_schema=build_observation_schema(OBSERVATION_SCHEMA_V2),
        normalize_account=True,
        block_overnight=False,
    )

    age_index = build_observation_schema(OBSERVATION_SCHEMA_V2).coordinates.index(
        "position_age_over_scale"
    )
    assert captured_accounts
    assert any(account[age_index] > 0.0 for account in captured_accounts)


def test_v1_account_observation_can_preserve_legacy_raw_coordinates() -> None:
    bars, features = _market_frame(n=4)
    captured: list[np.ndarray[Any, Any]] = []

    def capture(observation: object) -> int:
        assert isinstance(observation, Mapping)
        captured.append(np.asarray(observation["account"]))
        return 0

    run_backtest(
        bars,
        features,
        capture,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        observation_schema=build_observation_schema(OBSERVATION_SCHEMA_V1),
        normalize_account=False,
        block_overnight=False,
    )

    assert captured
    assert captured[0].shape == (6,)
    assert captured[0][0] == pytest.approx(10_000.0)


def _baseline_fsm_result(risk_frac: float) -> dict[str, Any]:
    bars, features = _market_frame()
    features["sweep_low"] = 0.0
    features.loc[bars.index[1], "sweep_low"] = 1.0
    actions = iter((1, 1, 1, 2, 0, 0, 0))

    return run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        risk_frac=risk_frac,
        policy_risk_frac_range=(risk_frac, risk_frac),
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        exit_action=2,
        block_overnight=False,
        entry_state_machine=True,
        strategy=BaselineStrategy(),
    )


def test_baseline_fsm_trigger_opens_and_records_in_position_transition() -> None:
    result = _baseline_fsm_result(risk_frac=0.001)

    trades = result["trades"]
    diagnostics = result["entry_state_diagnostics"]
    opened = trades.loc[trades["type"].eq("open")]
    assert len(opened) == 1
    assert diagnostics["trigger_requested"] == 1
    assert diagnostics["trigger_refused"] == 0
    assert diagnostics["entered"] == 1
    assert diagnostics["entry_state_visits"] == {
        "FLAT": 0,
        "CANDIDATE": 1,
        "ARMED": 1,
        "IN_POSITION": 1,
    }


def test_baseline_fsm_records_refused_trigger_when_risk_is_below_minimum_lot() -> None:
    result = _baseline_fsm_result(risk_frac=1e-10)

    trades = result["trades"]
    diagnostics = result["entry_state_diagnostics"]
    rejected = trades.loc[trades["type"].eq("reject")]
    assert len(rejected) == 1
    assert rejected.iloc[0]["reason"] == "risk_budget_below_minimum_lot"
    assert not trades["type"].eq("open").any()
    assert diagnostics["trigger_requested"] == 1
    assert diagnostics["trigger_refused"] == 1
    assert diagnostics["entered"] == diagnostics["closed"] == 0


def test_tick_only_backtest_requires_a_tickbook_before_processing_bars() -> None:
    bars, features = _market_frame()

    with pytest.raises(TickExecutionUnavailable, match="tick-only execution requires a TickBook"):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            cost_model=CostModel(spread_points=0.0, point_size=0.01),
            tick_execution_required=True,
            block_overnight=False,
        )


def test_scalar_backtest_rejects_boolean_policy_actions() -> None:
    bars, features = _market_frame(n=3)

    with pytest.raises(TypeError, match="must return one integer scalar action"):
        run_backtest(
            bars,
            features,
            lambda _observation: True,
            obs_window=1,
            block_overnight=False,
        )


def test_open_position_is_terminally_liquidated_and_accounted_once() -> None:
    bars, features = _market_frame()
    calls = 0

    def enter_once(_observation: object) -> int:
        nonlocal calls
        calls += 1
        return 1 if calls == 1 else 0

    result = run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    trades = result["trades"]
    opened = trades.loc[trades["type"].eq("open")]
    terminal = trades.loc[trades["type"].isin(["eod_close", "forced_close"])]
    assert len(opened) == 1
    assert len(terminal) == 1
    assert terminal.iloc[0]["position_id"] == opened.iloc[0]["position_id"]
    assert terminal.iloc[0]["pnl"] == pytest.approx(result["account"].balance - 10_000.0)
    assert result["n_sessions_with_trades"] == 1
    assert result["n_sessions_skipped"] == 0


def test_tick_only_terminal_liquidation_uses_final_minute_quote_and_exit_side_slippage() -> None:
    bars, features = _market_frame()
    tick_times = pd.date_range(
        start=bars.index[0] + pd.Timedelta(seconds=10),
        periods=len(bars),
        freq="min",
    )
    tickbook = TickBook(
        np.asarray(tick_times, dtype="datetime64[ns]").astype(np.int64),
        np.full(len(tick_times), 100.0),
        np.full(len(tick_times), 100.25),
    )
    calls = 0

    def enter_once(_observation: object) -> int:
        nonlocal calls
        calls += 1
        return 1 if calls == 1 else 0

    result = run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.25),
        initial_balance=10_000.0,
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        tickbook=tickbook,
        tick_execution_required=True,
        tick_fill_slippage_points=0.5,
        hold_on_zero=True,
        block_overnight=False,
    )

    opened = result["trades"].loc[result["trades"]["type"].eq("open")].iloc[0]
    terminal = result["trades"].loc[result["trades"]["type"].eq("eod_close")].iloc[0]
    assert terminal["fill_quote_source"] == "tick"
    assert terminal["actual_tick_time"] == tick_times[-1]
    assert terminal["pre_execution_quote_bid"] == 100.0
    assert terminal["pre_execution_quote_ask"] == 100.25
    assert terminal["broker_execution_quote_bid"] == 99.5
    assert terminal["broker_execution_quote_ask"] == 100.25
    assert terminal["slippage_points_applied_here"] == 0.5
    assert terminal["position_id"] == opened["position_id"]


def test_policy_exit_closes_the_open_position_at_the_next_executable_bar() -> None:
    bars, features = _market_frame()
    actions = iter((1, 0, 2))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        exit_action=2,
        block_overnight=False,
    )

    trades = result["trades"]
    opened = trades.loc[trades["type"].eq("open")]
    closed = trades.loc[trades["type"].eq("close")]
    assert len(opened) == 1
    assert len(closed) == 1
    assert closed.iloc[0]["position_id"] == opened.iloc[0]["position_id"]
    assert closed.iloc[0]["decision_time"] == bars.index[3]
    assert closed.iloc[0]["fill_time"] >= closed.iloc[0]["decision_time"]
    assert not trades["type"].isin(["eod_close", "forced_close"]).any()
    assert result["account"].balance == pytest.approx(10_000.0 + closed.iloc[0]["pnl"])


def test_account_currency_take_profit_closes_and_realizes_the_open_pnl() -> None:
    bars, features = _market_frame(n=6)
    actions = iter((1, 0, 0, 0, 0))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 0),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        lots=1.0,
        take_profit_per_trade_usd=0.05,
        hold_on_zero=True,
        block_overnight=False,
    )

    trades = result["trades"]
    opened = trades.loc[trades["type"].eq("open")]
    take_profit = trades.loc[
        trades["type"].eq("tp_close") & trades["reason"].eq("take_profit_per_trade")
    ]
    assert len(opened) == len(take_profit) == 1
    assert take_profit.iloc[0]["position_id"] == opened.iloc[0]["position_id"]
    assert take_profit.iloc[0]["pnl"] >= 0.05
    assert result["account"].balance == pytest.approx(10_000.0 + take_profit.iloc[0]["pnl"])
    assert not trades["type"].isin(["eod_close", "forced_close"]).any()


def test_structural_stop_closes_before_terminal_liquidation() -> None:
    bars, features = _market_frame()
    bars.loc[bars.index[2], "low"] = 98.0
    features["last_swing_low"] = 99.0
    features["last_swing_high"] = 110.0
    calls = 0

    def enter_once(_observation: object) -> int:
        nonlocal calls
        calls += 1
        return 1 if calls == 1 else 0

    result = run_backtest(
        bars,
        features,
        enter_once,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    trades = result["trades"]
    opened = trades.loc[trades["type"].eq("open")]
    stopped = trades.loc[trades["type"].eq("stop_close")]
    assert len(opened) == len(stopped) == 1
    assert stopped.iloc[0]["reason"] == "structure_sl"
    assert stopped.iloc[0]["position_id"] == opened.iloc[0]["position_id"]
    assert stopped.iloc[0]["bar"] == 2
    assert not trades["type"].eq("eod_close").any()


def _limit_case() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray[Any, Any], int]:
    bars, _ = _market_frame(n=5)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    columns = [name for _, name in trade_setup_candidate_feature_columns()]
    features = pd.DataFrame(0.0, index=bars.index, columns=columns)
    features["atr_5"] = 1.0
    features.loc[bars.index[1] :, "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[bars.index[1] :, "fvg_bull_active"] = 1.0
    features.loc[bars.index[1] :, "fvg_bull_retest_confirmed_at_time_ns"] = bars.index[1].value
    features.loc[bars.index[1] :, "fvg_bull_retest_origin_time_ns"] = bars.index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    limit_action = np.zeros(schema.width, dtype=np.float32)
    limit_action[schema.indices["trade_setup"]] = trade_setup_center(candidate_id)
    limit_action[schema.indices["entry_execution"]] = 1.0
    limit_action[schema.indices["limit_offset_atr"]] = -1.0
    limit_action[schema.indices["limit_ttl_bars"]] = 1.0
    limit_action[schema.indices["stop"]] = -0.4
    limit_action[schema.indices["target"]] = 0.8
    limit_action[schema.indices["exit"]] = -1.0
    no_trade = np.zeros(schema.width, dtype=np.float32)
    no_trade[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    no_trade[schema.indices["entry_execution"]] = -1.0
    return bars, features, np.stack((limit_action, no_trade)), candidate_id


def test_pending_limit_is_cancelled_at_data_end_without_an_executable_tick() -> None:
    bars, features, actions, candidate_id = _limit_case()
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    selected = False

    def select_one_eligible_limit(
        observation: np.ndarray[Any, Any] | Mapping[str, np.ndarray[Any, Any]],
    ) -> np.ndarray[Any, Any]:
        nonlocal selected
        if not isinstance(observation, Mapping):
            return cast(np.ndarray[Any, Any], actions[1])
        mask = np.asarray(observation["trade_setup_mask"])
        if not selected and mask[candidate_id] > 0.0:
            selected = True
            return cast(np.ndarray[Any, Any], actions[0])
        return cast(np.ndarray[Any, Any], actions[1])

    result = run_backtest(
        bars,
        features,
        select_one_eligible_limit,
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        hold_on_zero=True,
        block_overnight=False,
        trade_setup_actions=True,
        trade_setup_action_schema=schema,
        trade_setup_geometry=False,
        tickbook=TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([])),
    )

    trades = result["trades"]
    submissions = trades.loc[trades["type"].eq("order_submit")]
    cancellations = trades.loc[trades["type"].eq("order_cancel")]
    assert len(submissions) == 1
    assert submissions.iloc[0]["order_type"] == "limit"
    assert submissions.iloc[0]["trade_setup_candidate_id"] == candidate_id
    assert len(cancellations) == 1
    assert cancellations.iloc[0]["reason"] == "data_end_before_limit_expiry"
    assert not trades["type"].eq("open").any()
    assert result["account"].balance == 100_000.0


def test_rollout_hard_drawdown_breach_closes_and_latches_across_sessions() -> None:
    bars, features = _market_frame(n=7)
    bars["session_id"] = [0, 0, 0, 0, 0, 1, 1]
    bars.loc[bars.index[4], ["close", "high", "low"]] = [98.0, 98.1, 97.9]
    features["last_swing_low"] = 90.0
    features["last_swing_high"] = 110.0
    actions = iter((1, 0, 0, 0, 1, 1, 1))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 1),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=100_000.0,
        guardrail_kwargs={
            "limit_value_mode": "fixed_usd",
            "daily_loss_limit_pct": 0.5,
            "max_loss_limit_initial_pct": 0.00001,
            "risk_per_trade_limit": 10_000.0,
            "soft_daily_loss_limit_pct": 0.0,
            "soft_max_loss_limit_initial_pct": 0.0,
        },
        risk_frac=0.001,
        policy_risk_frac_range=(0.001, 0.001),
        rr_ratio=1.0,
        use_structure_sl_tp=True,
        swing_buffer_pts=0.0,
        min_lot=0.01,
        max_lot=1.0,
        max_loss_per_trade_usd=100.0,
        contract_size=1.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    trades = result["trades"]
    assert len(trades.loc[trades["type"].eq("open")]) == 1
    forced = trades.loc[trades["type"].eq("forced_close")]
    assert len(forced) == 1
    assert forced.iloc[0]["reason"] == "max_drawdown"
    assert len(result["breach_events"]) == 1
    assert result["breach_events"][0]["reason"] == "max_drawdown"
    assert result["breach_events"][0]["session_id"] == 0
    assert result["n_breach_sessions"] == 1


def test_daily_loss_breach_forces_close_and_blocks_entries_in_later_session() -> None:
    bars, features = _market_frame(n=7)
    bars["session_id"] = [0, 0, 0, 0, 0, 1, 1]
    bars.loc[bars.index[4], ["open", "high", "low", "close"]] = [98.0, 98.1, 97.9, 98.0]
    bars.loc[bars.index[5] :, ["open", "high", "low", "close"]] = [98.0, 98.1, 97.9, 98.0]
    actions = iter((1, 0, 0, 0, 1, 1))

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions, 1),
        obs_window=1,
        cost_model=CostModel(spread_points=0.0, point_size=0.01),
        initial_balance=10_000.0,
        guardrail_kwargs={
            "limit_value_mode": "fixed_usd",
            "daily_loss_limit_pct": 0.00005,
            "max_loss_limit_initial_pct": 0.5,
            "risk_per_trade_limit": 10_000.0,
            "soft_daily_loss_limit_pct": 0.0,
            "soft_max_loss_limit_initial_pct": 0.0,
        },
        lots=1.0,
        hold_on_zero=True,
        block_overnight=False,
    )

    trades = result["trades"]
    opened = trades.loc[trades["type"].eq("open")]
    forced = trades.loc[trades["type"].eq("forced_close")]
    assert len(opened) == len(forced) == 1
    assert forced.iloc[0]["reason"] == "daily_loss"
    assert forced.iloc[0]["position_id"] == opened.iloc[0]["position_id"]
    assert forced.iloc[0]["pnl"] < -0.5
    assert result["account"].balance == pytest.approx(10_000.0 + forced.iloc[0]["pnl"])
    assert len(result["breach_events"]) == 1
    breach = result["breach_events"][0]
    assert breach["reason"] == "daily_loss"
    assert breach["daily_pnl_basis"] == "session_net_equity"
    assert breach["session_id"] == 0
    assert breach["daily_loss"] > result["daily_loss_limit_usd"]
    assert result["n_breach_sessions"] == 1


def _repeated_payout_policy() -> TradingPolicyConfig:
    return TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=10_000.0,
        profit_target_balance=11_000.0,
        account_floor=9_000.0,
        daily_loss_limit_pct=0.2,
        max_agent_risk_frac=0.009,
    ).validate()


@pytest.mark.parametrize("policy_input", ["instance", "resolved_mapping", "full_config"])
def test_repeated_payout_rejects_initial_balance_mismatch_for_supported_inputs(
    policy_input: str,
) -> None:
    policy = _repeated_payout_policy()
    policy_config: TradingPolicyConfig | dict[str, Any]
    if policy_input == "instance":
        policy_config = policy
    elif policy_input == "resolved_mapping":
        policy_config = policy.to_dict()
    else:
        policy_config = {
            "account": {"initial_balance": policy.operating_balance},
            "trading_policy": {
                "mode": "repeated_payout",
                "repeated_payout": {
                    "operating_balance": policy.operating_balance,
                    "profit_target_balance": policy.profit_target_balance,
                    "account_floor": policy.account_floor,
                    "daily_loss_limit_pct": policy.daily_loss_limit_pct,
                    "max_agent_risk_frac": policy.max_agent_risk_frac,
                },
            },
        }
    bars, features = _market_frame()

    with pytest.raises(ValueError, match="initial_balance must equal operating_balance"):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            initial_balance=policy.operating_balance - 1.0,
            trading_policy=policy_config,
            block_overnight=False,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"daily_pnl_basis": "legacy_gross_closed_losses"}, "daily_pnl_basis conflicts"),
        ({"use_structure_sl_tp": False}, "require structure-derived stop levels"),
        ({"risk_frac": 0.01}, "risk_frac must be within the repeated-payout policy limit"),
        (
            {"policy_risk_frac_range": (0.0, 0.01)},
            "policy_risk_frac_range exceeds the repeated-payout policy risk limit",
        ),
    ],
)
def test_repeated_payout_rejects_conflicting_risk_and_execution_inputs(
    overrides: dict[str, object], message: str
) -> None:
    bars, features = _market_frame()
    kwargs: dict[str, Any] = {
        "initial_balance": 10_000.0,
        "trading_policy": _repeated_payout_policy(),
        "use_structure_sl_tp": True,
        "block_overnight": False,
    }
    kwargs.update(overrides)

    with pytest.raises(ValueError, match=message):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            **kwargs,
        )


@pytest.mark.parametrize("candidate_max_age_bars", [-1, 1.5])
def test_entry_candidate_age_must_be_a_nonnegative_integer(candidate_max_age_bars: float) -> None:
    bars, features = _market_frame()

    with pytest.raises(ValueError, match="candidate_max_age_bars must be a non-negative integer"):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            candidate_max_age_bars=cast(Any, candidate_max_age_bars),
            block_overnight=False,
        )


def test_normalized_account_schema_rejects_disabled_account_normalization() -> None:
    bars, features = _market_frame()

    with pytest.raises(ValueError, match="requires normalize_account=True"):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            entry_state_machine=True,
            observation_schema=build_observation_schema(OBSERVATION_SCHEMA_V2),
            normalize_account=False,
            block_overnight=False,
        )


@pytest.mark.parametrize(
    "policy_risk_frac_range",
    [(float("nan"), 0.02), (float("inf"), 0.02), (-0.001, 0.02)],
)
def test_policy_risk_fraction_range_requires_finite_nonnegative_bounds(
    policy_risk_frac_range: tuple[float, float],
) -> None:
    bars, features = _market_frame()

    with pytest.raises(ValueError, match="policy_risk_frac_range must be finite, non-negative"):
        run_backtest(
            bars,
            features,
            lambda _observation: 0,
            obs_window=1,
            policy_risk_frac_range=policy_risk_frac_range,
            block_overnight=False,
        )
