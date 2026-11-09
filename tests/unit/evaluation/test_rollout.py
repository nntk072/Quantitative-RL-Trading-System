"""Tests for evaluation.rollout.trained_policy_rollout.evaluate_model (RL model walk-forward eval).

Regression coverage for the bug where RL runs reported ``equity == 100k``
for every case with zero trades executed: the evaluation step used a
hardcoded hold-forever stub instead of querying the trained model. These
tests exercise the real fix — rolling a model through
``TradingEnv(episodic=False)`` — with a scripted stand-in model so no actual
PPO training is required.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest
from gymnasium import spaces

from decisioning.actions import build_discrete_trading_action_schema
from decisioning.adapters.sb3 import SB3DecisionProvider
from decisioning.observations import OBSERVATION_SCHEMA_V1
from decisioning.trade_setup import NO_TRADE_ID, TRADE_SETUP_CATEGORY_COUNT
from evaluation.reporting.policy_decision_reconciliation import reconcile_policy_decisions
from evaluation.rollout.trained_policy_rollout import (
    _candidate_geometry_action_trace,
    _setup_choice_probability_summary,
    evaluate_model,
    evaluate_provider,
)


class _ScriptedModel:
    """Minimal stand-in for a trained SB3 model's ``.predict()`` API.

    Ignores the observation and returns a scripted action per call index,
    mirroring ``model.predict(obs, deterministic=True) -> (action, state)``.
    """

    def __init__(self, script: dict[int, int], default: int = 0):
        self.script = script
        self.default = default
        self.t = 0
        self.action_space: spaces.Space[Any] = spaces.Discrete(20)
        self._action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()

    def predict(self, obs, deterministic: bool = True):
        action = self.script.get(self.t, self.default)
        self.t += 1
        return np.array([action]), None


def _make_bars(n: int, session_split: int | None = None) -> pd.DataFrame:
    """Flat-price synthetic M1 bars (deterministic transaction costs)."""
    idx = pd.date_range("2025-01-06 16:30", periods=n, freq="1min", tz="Etc/GMT-3")
    close = np.full(n, 20000.0)
    session_id = np.zeros(n, dtype=int)
    if session_split is not None:
        session_id[session_split:] = 1
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "session_id": session_id,
        },
        index=idx,
    )


def test_setup_probability_summary_records_compact_choice_context() -> None:
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[[NO_TRADE_ID, 5, 37]] = 1.0
    probabilities = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    probabilities[[NO_TRADE_ID, 5, 37]] = [0.2, 0.3, 0.5]

    summary = _setup_choice_probability_summary(probabilities, mask, NO_TRADE_ID)

    assert summary == {
        "trade_setup_selected_probability": pytest.approx(0.2),
        "trade_setup_no_trade_probability": pytest.approx(0.2),
        "trade_setup_max_trade_probability": pytest.approx(0.5),
        "trade_setup_max_trade_candidate_id": 37,
    }
    assert _setup_choice_probability_summary(None, mask, NO_TRADE_ID) == {
        "trade_setup_selected_probability": None,
        "trade_setup_no_trade_probability": None,
        "trade_setup_max_trade_probability": None,
        "trade_setup_max_trade_candidate_id": None,
    }


@pytest.mark.parametrize(
    ("probabilities", "message"),
    [
        (np.zeros(TRADE_SETUP_CATEGORY_COUNT - 1), "match the current eligibility mask"),
        (np.full(TRADE_SETUP_CATEGORY_COUNT, np.nan), "finite and non-negative"),
        (np.zeros(TRADE_SETUP_CATEGORY_COUNT), "sum to one"),
    ],
)
def test_setup_probability_summary_rejects_invalid_distribution(
    probabilities: npt.NDArray[np.float64], message: str
) -> None:
    mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    mask[[NO_TRADE_ID, 5]] = 1.0

    with pytest.raises(RuntimeError, match=message):
        _setup_choice_probability_summary(probabilities, mask, NO_TRADE_ID)


def test_candidate_geometry_trace_records_selected_slot_snapshot_and_decoded_action() -> None:
    from decisioning.trade_setup import (
        CANDIDATE_GEOMETRY_FEATURE_NAMES,
        candidate_geometry_slot,
        candidate_geometry_slot_count,
        candidate_geometry_slot_semantics,
    )

    selected_id = 5
    slot = candidate_geometry_slot(selected_id, "limit")
    count = candidate_geometry_slot_count()
    candidate_ids = np.asarray(
        [candidate_geometry_slot_semantics(index)[0] for index in range(count)],
        dtype=np.int64,
    )
    features = np.zeros((count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32)
    features[slot] = np.arange(len(CANDIDATE_GEOMETRY_FEATURE_NAMES), dtype=np.float32) + 0.5
    mask = np.zeros(count, dtype=np.bool_)
    mask[[NO_TRADE_ID, slot]] = True
    info = {
        "execution_type": "limit",
        "action": 1,
        "trade_setup_selected_direction": 1,
        "trade_setup_action_schema_version": "trade-setup-entry-execution-action-v2",
        "limit_offset_atr": 0.25,
        "limit_ttl_bars": 3,
        "action_trade_setup": 0.01,
        "trade_setup_u": 0.505,
        "risk_u": 0.5,
    }

    trace = _candidate_geometry_action_trace(
        {
            "candidate_ids": candidate_ids,
            "candidate_features": features,
            "candidate_mask": mask,
        },
        selected_id,
        info,
    )

    import json

    snapshot = json.loads(trace["candidate_geometry_snapshot_json"])
    decoded = json.loads(trace["candidate_geometry_decoded_action_json"])
    assert trace["candidate_geometry_trace_schema_version"] == "candidate-geometry-action-trace-v1"
    assert trace["candidate_geometry_slot"] == slot
    assert trace["candidate_geometry_setup_id"] == selected_id
    assert trace["candidate_geometry_entry_type"] == "limit"
    assert snapshot["entry_price_offset_atr"] == pytest.approx(2.5)
    assert decoded["candidate_id"] == selected_id
    assert decoded["action_schema_version"] == "trade-setup-entry-execution-action-v2"
    assert decoded["entry_type"] == "limit"
    assert decoded["limit_ttl_bars"] == 3
    assert decoded["action_coordinates"]["risk_u"] == pytest.approx(0.5)
    invalid_mask = np.zeros(count, dtype=np.bool_)
    invalid_mask[NO_TRADE_ID] = True
    with pytest.raises(RuntimeError, match="slot that was masked"):
        _candidate_geometry_action_trace(
            {
                "candidate_ids": candidate_ids,
                "candidate_features": features,
                "candidate_mask": invalid_mask,
            },
            selected_id,
            info,
        )


def test_evaluate_model_exports_candidate_geometry_trace_for_no_trade() -> None:
    from types import SimpleNamespace

    from decisioning.trade_setup import build_trade_setup_action_schema, trade_setup_center

    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    action = np.zeros(schema.width, dtype=np.float32)
    action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
    action[schema.indices["entry_execution"]] = -0.5

    class _CandidateGeometryModel:
        policy = SimpleNamespace(hybrid_action_coordinates=schema.names)

        def predict(self, obs: dict[str, Any], deterministic: bool = True):
            assert "candidate_ids" in obs
            assert "candidate_features" in obs
            assert "candidate_mask" in obs
            return action, None

    bars = _make_bars(24)
    features = _make_features(bars).copy()
    from features.context.trade_setup_candidates import trade_setup_candidate_feature_columns

    setup_features = pd.DataFrame(
        0.0,
        index=features.index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features = pd.concat((features, setup_features), axis=1)
    result = evaluate_model(
        _CandidateGeometryModel(),
        bars=bars,
        features=features,
        obs_window=10,
        strategy_actions=True,
        trade_setup_actions=True,
        candidate_geometry_actions=True,
        agent_entry_execution=True,
    )

    setup_decisions = result["trade_setup_decisions"]
    policy_decisions = result["policy_decisions"]
    assert not setup_decisions.empty
    assert not policy_decisions.empty
    for frame in (setup_decisions, policy_decisions):
        assert set(frame["candidate_geometry_trace_schema_version"]) == {
            "candidate-geometry-action-trace-v1"
        }
        assert set(frame["candidate_geometry_slot"]) == {NO_TRADE_ID}
        assert set(frame["candidate_geometry_setup_id"]) == {NO_TRADE_ID}
        assert set(frame["candidate_geometry_entry_type"]) == {"market"}


def _make_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Trivial feature matrix aligned 1:1 with *bars*.

    Provides swing levels so entries compute structure SL/TP (the env no
    longer opens naked lots=1.0 positions when swing levels are missing).
    """
    n = len(bars)
    return pd.DataFrame(
        {
            "ret_1": np.zeros(n),
            "last_swing_low": np.full(n, 19990.0),
            "last_swing_high": np.full(n, 20010.0),
        },
        index=bars.index,
    )


def test_evaluate_model_forwards_trade_setup_mode_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {}

    class _CapturedEnvironmentConstruction(Exception):
        pass

    def capture_environment(**kwargs: Any) -> None:
        received.update(kwargs)
        raise _CapturedEnvironmentConstruction

    monkeypatch.setattr("evaluation.rollout.trained_policy_rollout.TradingEnv", capture_environment)
    bars = _make_bars(20)

    with pytest.raises(_CapturedEnvironmentConstruction):
        evaluate_model(
            _ScriptedModel({}),
            bars=bars,
            features=_make_features(bars),
            trade_setup_actions=True,
        )

    assert received["trade_setup_actions"] is True


def test_evaluate_model_produces_trades_and_valid_equity():
    """A model that enters/holds/exits repeatedly must produce real trades,
    not the flat 100k-equity/zero-trade result the hardcoded hold-stub gave.
    """
    obs_window = 10
    n = 120
    bars = _make_bars(n)
    features = _make_features(bars)

    # Enter long every 20 calls, exit 5 calls later, hold otherwise.
    script = {t: (1 if t % 20 == 0 else 19 if t % 20 == 5 else 0) for t in range(n - obs_window)}
    model = _ScriptedModel(script, default=0)

    result = evaluate_model(
        model,
        bars=bars,
        features=features,
        obs_window=obs_window,
        initial_balance=100_000.0,
    )

    trades = result["trades"]
    assert not trades.empty, "evaluate_model must produce real trades from a trading model"
    assert (trades["type"] == "open").sum() > 0

    equity = result["equity"]
    assert isinstance(equity, pd.Series)
    assert len(equity) == n - obs_window + 1
    assert isinstance(equity.index, pd.DatetimeIndex)
    assert result["completed_data_split"] is True
    assert result["episode_end_reason"] == "data_end"
    assert result["account_state_trace_complete"] is True
    account_trace = result["account_state_trace"]
    assert len(account_trace) == result["n_steps"]
    assert account_trace["schema_version"].eq("account_state_trace.v2").all()
    assert account_trace["balance"].notna().all()
    assert account_trace["equity"].notna().all()
    assert account_trace["daily_floor_equity"].eq(95_000.0).all()
    assert "pending_order_limit_price" in account_trace.columns
    decisions = result["policy_decisions"]
    assert len(decisions) == result["n_steps"]
    assert decisions["schema_version"].eq("environment_policy_decision.v2").all()
    assert decisions["decision_id"].is_unique
    assert result["policy_decisions_complete"] is True
    policy_reconciliation = reconcile_policy_decisions(
        decisions,
        trades,
        result["breach_events"],
    )
    assert policy_reconciliation["status"] == "matched", policy_reconciliation

    close_rows = trades[trades["type"] == "close"]
    assert not close_rows.empty
    assert close_rows["price"].notna().all()
    assert close_rows["bar"].notna().all()
    # Equity must not stay flat at the initial balance the whole rollout.
    assert not np.isclose(equity.iloc[-1], 100_000.0)


def test_evaluate_provider_uses_the_same_trading_rollout():
    obs_window = 10
    n = 120
    bars = _make_bars(n)
    features = _make_features(bars)
    script = {t: (1 if t % 20 == 0 else 19 if t % 20 == 5 else 0) for t in range(n - obs_window)}
    provider = SB3DecisionProvider(
        _ScriptedModel(script),
        input_schema_version=OBSERVATION_SCHEMA_V1,
    )

    result = evaluate_provider(
        provider,
        bars=bars,
        features=features,
        obs_window=obs_window,
        initial_balance=100_000.0,
    )

    assert not result["trades"].empty
    assert result["completed_data_split"] is True
    assert result["equity"].index[0] == bars.index[obs_window]
    assert len(result["equity"]) == len(bars) - obs_window + 1


class _ExposureEnv:
    def __init__(self) -> None:
        self.exposure = iter((True, True, False))
        self.constraint_steps = iter(
            (
                {"daily_cost": 0.1},
                {"trailing_cost": 0.2},
                {"max_loss_cost": 0.1},
            )
        )
        self.equity_curve = [100_000.0]
        self.equity_times = [pd.Timestamp("2025-01-06T16:40:00+03:00")]
        self.trade_log: list[dict[str, Any]] = []
        self.breach_events: list[dict[str, Any]] = []
        self.breach_log: list[dict[str, Any]] = []
        self.all_sessions = {"s0"}
        self.sessions_with_trades: set[str] = set()
        self.breached_sessions: set[str] = set()
        self.account = object()
        self._entry_diag: dict[str, int] = {}
        self.reset_seed: int | None = None
        self.step_idx = 0
        self._session_ids_arr = None

    @staticmethod
    def _bar_time(index: int) -> pd.Timestamp:
        return pd.Timestamp("2025-01-06T16:40:00+03:00") + pd.Timedelta(minutes=index)

    def reset(self, *, seed: int | None = None) -> tuple[dict[str, object], dict[str, object]]:
        self.reset_seed = seed
        return {}, {}

    def step(
        self, action: object
    ) -> tuple[dict[str, object], float, bool, bool, dict[str, object]]:
        del action
        is_open = next(self.exposure)
        self.step_idx += 1
        self.equity_curve.append(100_000.0)
        self.equity_times.append(self.equity_times[-1] + pd.Timedelta(minutes=1))
        completed = len(self.equity_curve) == 4
        info: dict[str, object] = {
            "position": is_open,
            "constraints": next(self.constraint_steps),
        }
        if completed:
            info["episode_equity"] = {
                "completed_data_split": True,
                "episode_end_reason": "data_end",
            }
        return {}, 0.0, completed, False, info


def test_evaluate_model_reports_bar_close_exposure_fraction() -> None:
    result = evaluate_model(
        _ScriptedModel({}),
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        env=_ExposureEnv(),  # type: ignore[arg-type]
    )

    assert result["n_steps"] == 3
    assert result["completed_data_split"] is True
    assert result["survived_full_year"] is True
    assert result["exposure_bars"] == 2
    assert result["exposure_fraction"] == 2 / 3
    assert result["exposure_measure"] == "fraction_of_evaluation_steps_with_position_at_bar_close"


@pytest.mark.parametrize(
    ("breach_reason", "episodic", "repeated_payout", "survived"),
    [
        ("daily_loss", False, False, False),
        ("daily_loss", True, False, False),
        ("daily_loss", False, True, False),
        ("max_drawdown", False, False, False),
    ],
)
def test_evaluate_model_counts_daily_breach_as_full_evaluation_failure(
    breach_reason: str,
    episodic: bool,
    repeated_payout: bool,
    survived: bool,
) -> None:
    env = _ExposureEnv()
    setattr(env, "episodic", episodic)
    setattr(env, "repeated_payout_policy", repeated_payout)
    breach_time = "2025-01-06T16:41:00+03:00"
    detection_time = "2025-01-06T16:41:00.218+03:00"
    env.breach_events = [
        {
            "time": breach_time,
            "detection_time": detection_time,
            "trade_event_count": 0,
            "reason": breach_reason,
        }
    ]

    result = evaluate_model(
        _ScriptedModel({}),
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        env=env,  # type: ignore[arg-type]
    )

    assert result["completed_data_split"] is True
    assert result["survived_full_year"] is survived
    assert result["fail_time"] == detection_time
    assert result["breach_events"] == env.breach_events


def test_evaluate_model_seeds_environment_execution_rng() -> None:
    env = _ExposureEnv()

    evaluate_model(
        _ScriptedModel({}),
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        env=env,  # type: ignore[arg-type]
        randomized_fill_latency_ms=30.0,
        execution_seed=17,
    )

    assert env.reset_seed == 17


def test_randomized_tick_evaluation_requires_execution_seed() -> None:
    with pytest.raises(ValueError, match="execution_seed is required"):
        evaluate_model(
            _ScriptedModel({}),
            bars=pd.DataFrame(),
            features=pd.DataFrame(),
            env=_ExposureEnv(),  # type: ignore[arg-type]
            randomized_fill_latency_ms=30.0,
        )


def test_q5_evaluation_reports_discounted_constraint_costs() -> None:
    model = _ScriptedModel({})
    setattr(model, "_constrained_rl_state", {"version": 2, "gamma": 0.9})
    result = evaluate_model(
        model,
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        env=_ExposureEnv(),  # type: ignore[arg-type]
    )

    summary = result["constraint_cost_summary"]
    assert summary["schema"] == "q5_discounted_constraint_cost_v1"
    assert summary["n_steps"] == 3
    assert summary["undiscounted_total"] == pytest.approx(0.4)
    assert summary["discounted_total"] == pytest.approx(0.361)
    assert summary["components"]["trailing_cost"]["discounted_total"] == pytest.approx(0.18)
    assert result["constraint_costs"]["discount_factor"].tolist() == pytest.approx([1.0, 0.9, 0.81])


def test_q5_v3_evaluation_reports_undiscounted_max_loss_fraction_costs() -> None:
    model = _ScriptedModel({})
    setattr(
        model,
        "_constrained_rl_state",
        {
            "version": 3,
            "cost_discount_gamma": 1.0,
            "daily_loss_limit_usd": 5_000.0,
            "max_loss_limit_usd": 10_000.0,
            "trailing_dd_limit_usd": 0.0,
        },
    )
    result = evaluate_model(
        model,
        bars=pd.DataFrame(),
        features=pd.DataFrame(),
        env=_ExposureEnv(),  # type: ignore[arg-type]
    )

    summary = result["constraint_cost_summary"]
    assert summary["schema"] == "q5_max_loss_fraction_cost_v1"
    assert summary["cost_unit"] == "fraction_of_max_loss_limit"
    assert summary["discount_gamma"] == pytest.approx(1.0)
    assert summary["undiscounted_total"] == pytest.approx(0.15)
    assert summary["discounted_total"] == pytest.approx(0.15)
    assert result["constraint_costs"]["discount_factor"].tolist() == [1.0, 1.0, 1.0]


def test_evaluate_model_does_not_mark_step_capped_rollout_as_full_survival():
    bars = _make_bars(120)
    features = _make_features(bars)

    result = evaluate_model(
        _ScriptedModel({}, default=0),
        bars=bars,
        features=features,
        obs_window=10,
        max_episode_steps=10,
    )

    assert result["n_steps"] == 10
    assert result["completed_data_split"] is False
    assert result["episode_end_reason"] == "max_episode_steps"
    assert result["survived_full_year"] is False


def test_evaluate_model_uses_requested_observation_schema(monkeypatch):
    """Training and evaluation must construct the same account observation."""
    from decisioning.observations import OBSERVATION_SCHEMA_V2, V2_COORDINATES
    from simulation.environment.env import TradingEnv as OriginalTradingEnv

    env_kwargs = {}

    def _capture_env_kwargs(**kwargs):
        env_kwargs.update(kwargs)
        return OriginalTradingEnv(**kwargs)

    monkeypatch.setattr("evaluation.rollout.trained_policy_rollout.TradingEnv", _capture_env_kwargs)

    class _SchemaCheckingModel(_ScriptedModel):
        def predict(self, obs, deterministic: bool = True):
            assert np.asarray(obs["account"]).shape[-1] == len(V2_COORDINATES)
            return super().predict(obs, deterministic=deterministic)

    bars = _make_bars(40)
    features = _make_features(bars)
    result = evaluate_model(
        _SchemaCheckingModel({}, default=0),
        bars=bars,
        features=features,
        obs_window=10,
        observation_schema_version=OBSERVATION_SCHEMA_V2,
        observation_age_scale_bars=30.0,
        sl_mode="trailing",
        tp_mode="breakeven",
        tp_reference="prior_session_extreme",
        sl_mode_defer_threshold=0.23,
        tp_mode_defer_threshold=0.29,
        tp_breakeven_alpha=0.37,
    )

    assert result["n_steps"] == len(bars) - 10
    assert env_kwargs["observation_schema_version"] == OBSERVATION_SCHEMA_V2
    assert env_kwargs["observation_age_scale_bars"] == 30.0
    assert env_kwargs["sl_mode"] == "trailing"
    assert env_kwargs["tp_mode"] == "breakeven"
    assert env_kwargs["tp_reference"] == "prior_session_extreme"
    assert env_kwargs["sl_mode_defer_threshold"] == 0.23
    assert env_kwargs["tp_mode_defer_threshold"] == 0.29
    assert env_kwargs["tp_breakeven_alpha"] == 0.37


def test_eval_mode_daily_breach_fails_full_evaluation():
    """A daily breach blocks later sessions and marks full evaluation failed.

    Regression for episodic=True breach handling ending the whole
    evaluation early (the root cause of the flat-equity/zero-trade bug).
    """
    obs_window = 10
    n = 100
    session_split = 50
    bars = _make_bars(n, session_split=session_split)
    features = _make_features(bars)

    # t=0 -> enter long (bar=obs_window); t=1 -> exit (realises a small
    # spread-only loss); every other call retries entering long.
    script = {0: 1, 1: 19}
    model = _ScriptedModel(script, default=1)

    result = evaluate_model(
        model,
        bars=bars,
        features=features,
        obs_window=obs_window,
        initial_balance=100_000.0,
        # Any realised loss (even just the bid/ask spread) breaches the
        # daily limit immediately, independent of price action.
        guardrail_kwargs={
            "limit_value_mode": "percent_equity",
            "daily_loss_limit_pct": 1e-9,
            "max_loss_limit_initial_pct": 1.0,
        },
    )

    trades = result["trades"]
    opens = trades[trades["type"] == "open"]
    assert len(opens) == 1, f"expected one open before account failure, got {len(opens)}"
    assert opens.iloc[0]["bar"] == obs_window
    assert result["n_breach_sessions"] == 1
    assert [event["session_id"] for event in result["breach_events"]] == [0]
    assert result["daily_loss_is_session_scoped"] is False
    assert result["survived_full_year"] is False
