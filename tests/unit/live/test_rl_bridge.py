"""Chain C tests: latency-injected fills + RL→MT5 bridge contract.

Runs headless (no MT5, no SB3 weights): the bridge is exercised with a
stub model and a stub data source matching the duck-typed interface the
live robot loop expects. ``MetaTrader5`` (a Windows-only package) is
stubbed in conftest so the ``integrations.mt5.domain.signal`` import works.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces
from omegaconf import OmegaConf

from decisioning.actions import build_discrete_trading_action_schema
from decisioning.adapters.sb3 import SB3DecisionProvider
from decisioning.contracts import (
    ActionSchemaRef,
    ContinuousAction,
    Decision,
    DecisionInput,
    DiscreteAction,
    PredictorMetadata,
    StructuredAction,
)
from decisioning.observations import (
    OBSERVATION_SCHEMA_REPEATED_PAYOUT,
    OBSERVATION_SCHEMA_V2,
    build_observation_schema,
)
from integrations.mt5.adapters.data import TradingData
from live.runtime.strategy import RLStrategyAdapter

# --- headless MetaTrader5 stub (Windows-only package, absent on Linux) -----
if "MetaTrader5" not in sys.modules:
    try:  # pragma: no cover - depends on platform
        import MetaTrader5  # noqa: F401
    except ImportError:
        _mt5_stub = ModuleType("MetaTrader5")
        for attr in (
            "TIMEFRAME_M1",
            "TIMEFRAME_M5",
            "TIMEFRAME_M15",
            "TIMEFRAME_M30",
            "TIMEFRAME_H1",
            "TIMEFRAME_H4",
            "TIMEFRAME_D1",
        ):
            setattr(_mt5_stub, attr, 1)
        sys.modules["MetaTrader5"] = _mt5_stub


@pytest.fixture
def trending_bars() -> pd.DataFrame:
    """Deterministic bars with drift so latency shifts fills adversely."""
    n = 400
    idx = pd.date_range("2025-01-06 16:30", periods=n, freq="1min", tz="Etc/GMT-3")
    close = 20000.0 + np.arange(n) * 0.5  # steady uptrend: later fills are pricier
    return pd.DataFrame(
        {
            "open": np.roll(close, 1),
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "tickvol": np.full(n, 100.0),
            "vol": np.zeros(n),
            "spread": np.full(n, 0.6),
        },
        index=idx,
    )


def _make_env(bars: pd.DataFrame, latency: int):
    from simulation.environment.env import TradingEnv

    # Swing levels below/above the uptrend's entry prices so long entries
    # compute structure SL/TP. Without them the env now rejects entries
    # (no naked positions), which would skip the latency assertions.
    feats = pd.DataFrame(0.0, index=bars.index, columns=["f0"])
    feats["last_swing_low"] = 19990.0
    feats["last_swing_high"] = 20020.0
    return TradingEnv(
        bars=bars,
        features=feats,
        obs_window=10,
        fill_latency_bars=latency,
    )


@pytest.mark.parametrize("latency", [0, 1, 3])
def test_latency_env_constructs_and_steps(trending_bars, latency):
    """Env accepts fill_latency_bars and steps without error."""
    env = _make_env(trending_bars, latency)
    obs, _ = env.reset(seed=42)
    # Raw absolute swing prices stay in execution context, not the model tensor.
    # The sequence contains f0 and the derived reachable_r column.
    assert obs["seq"].shape == (10, 2)
    for _ in range(20):
        obs, *_ = env.step(0)  # hold
    assert env.fill_latency_bars == latency


def test_latency_changes_fill_price(trending_bars):
    """A delayed entry stays pending until its future quote time."""
    env0 = _make_env(trending_bars, 0)
    env2 = _make_env(trending_bars, 2)
    env0.reset(seed=42)
    env2.reset(seed=42)

    # Drive both to the same step, then submit a long.
    for _ in range(10):
        env0.step(0)
        env2.step(0)
    env0.step(3)  # open long, discrete action
    scheduled_bar = env2.step_idx + 3
    env2.step(3)
    p0 = env0.position
    if p0 is None:  # action mapping guard
        pytest.skip("long entry action did not open a position")
    assert env2.position is None
    assert not any(row.get("type") == "open" for row in env2.trade_log)
    # Source timestamps label bar opens. The pending fill is the scheduled
    # bar's open, which is the same instant as the preceding bar's close.
    expected_fill_time = trending_bars.index[scheduled_bar]
    assert pd.Timestamp(env2.equity_times[-1]) < expected_fill_time

    while env2.step_idx < scheduled_bar - 1:
        env2.step(0)
        assert env2.position is None
    env2.step(0)
    p2 = env2.position
    if p2 is None:
        pytest.fail("pending latency order did not fill at its scheduled bar")

    assert p2.entry_price > p0.entry_price, (
        "latency-injected fill should be later (pricier) in an uptrend"
    )
    open_row = next(row for row in env2.trade_log if row.get("type") == "open")
    assert pd.Timestamp(open_row["fill_time"]) == expected_fill_time
    assert pd.Timestamp(open_row["order_submission_time"]) < expected_fill_time


def test_zero_latency_matches_legacy_default(trending_bars):
    """fill_latency_bars=0 keeps the previous next-bar fill behaviour."""
    env = _make_env(trending_bars, 0)
    env.reset(seed=42)
    bid, ask = env._bar_quote(env._bar_at(env.step_idx + 1))
    # step once with hold; the internal fill quote must equal bar t+1 quote
    env.step(0)
    assert env.fill_latency_bars == 0


def test_pending_latency_order_is_cancelled_when_episode_ends(trending_bars):
    env = _make_env(trending_bars, 2)
    env.reset(seed=42)
    env.max_episode_steps = 1

    _, _, _, truncated, _ = env.step(3)

    assert truncated
    assert env.position is None
    assert env._pending_entry_order is None
    assert any(
        row.get("type") == "order_cancel"
        and row.get("reason") == "episode_ended_before_scheduled_fill"
        for row in env.trade_log
    )


class _StubModel:
    """Duck-typed SB3 model: action = +1 (long) always."""

    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V2).to_dict()
    action_space: Any = spaces.Discrete(20)
    _action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])


class _StubData(TradingData):
    """Duck-typed MT5Data returning a small bars frame."""

    def __init__(self, bars: pd.DataFrame) -> None:
        self._bars = bars

    def get_symbol(self) -> str:
        return "US100.cash"

    def get_data(self) -> pd.DataFrame:
        return self._bars


def test_rl_bridge_observation_contract(trending_bars):
    """Bridge builds the same dict obs contract as the env (T, F) + (5,)."""
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)
    state = {
        "equity": 100_000.0,
        "planned_risk_usd": 0.0,
        "trailing_drawdown": 0.0,
        "trailing_drawdown_limit": 10_000.0,
        "daily_loss": 0.0,
        "daily_loss_limit": 5_000.0,
        "loss_from_initial": 0.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 900.0,
        "entry_price": 0.0,
        "initial_sl_price": 0.0,
        "active_sl_price": 0.0,
        "remaining_size": 0.0,
        "initial_size": 0.0,
        "position_age_bars": 0.0,
        "tp_hit_mask": 0,
        "tp1_price": 0.0,
        "tp2_price": 0.0,
        "tp3_price": 0.0,
        "sl_mode": "fixed",
        "tp_mode": "fixed",
        "exit_mode": "structural",
    }
    obs = adapter.build_observation(state)
    assert set(obs) == {"seq", "seq_mask", "account"}
    assert obs["seq"].dtype == np.float32
    assert obs["account"].shape == (28,)
    assert obs["seq_mask"].shape == (obs["seq"].shape[0],)
    action = adapter.predict_signal(state)
    assert action == 1


def test_live_adapter_requires_fit_state_without_diagnostic_opt_in() -> None:
    from live.runtime.strategy import RLStrategyAdapter

    with pytest.raises(ValueError, match="train-fitted feature normalization state is required"):
        RLStrategyAdapter(model=_StubModel(), config_path="config/base/default.yaml")

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    assert adapter is not None


def test_live_adapter_constructor_rejects_ambiguous_provider_and_model_inputs() -> None:
    from live.runtime.strategy import RLStrategyAdapter

    with pytest.raises(ValueError, match="provide exactly one of model or provider"):
        RLStrategyAdapter(config_path="config/base/default.yaml")
    with pytest.raises(ValueError, match="provide exactly one of model or provider"):
        RLStrategyAdapter(
            model=_StubModel(),
            provider=SB3DecisionProvider(_StubModel(), input_schema_version=OBSERVATION_SCHEMA_V2),
            config_path="config/base/default.yaml",
            allow_runtime_normalization_fallback=True,
        )


def test_live_adapter_applies_config_overlay_and_selects_strategy_raw_columns(
    tmp_path: Path,
) -> None:
    from live.runtime.strategy import RLStrategyAdapter
    from trading.strategies import DistributionStrategy, PO3IFVGStrategy

    overlay = tmp_path / "live-overlay.yaml"
    overlay.write_text(
        "env:\n  obs_window: 12\n  strategy_actions: true\n",
        encoding="utf-8",
    )
    adapter = RLStrategyAdapter(
        provider=SB3DecisionProvider(_StubModel(), input_schema_version=OBSERVATION_SCHEMA_V2),
        config_path="config/base/default.yaml",
        features_config_path=overlay,
        allow_runtime_normalization_fallback=True,
    )

    assert adapter.obs_window == 12
    assert adapter._raw_columns() == tuple(PO3IFVGStrategy.raw_columns)
    adapter.cfg.strategy.name = "distribution"
    assert adapter._raw_columns() == tuple(DistributionStrategy.raw_columns)
    adapter.cfg.strategy.name = "baseline"
    assert adapter._raw_columns() == ()


def test_primary_only_runtime_does_not_forward_secondary_market_data(
    trending_bars: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import features
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.cfg.training.primary_only = True
    secondary_bars = trending_bars.iloc[:5]
    received: list[dict[str, Any]] = []

    def fake_build_features(bars: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        received.append(kwargs)
        return pd.DataFrame({"feature": np.zeros(len(bars))}, index=bars.index)

    monkeypatch.setattr(features, "build_features", fake_build_features)
    adapter.update_bars(trending_bars, secondary_bars=secondary_bars)

    assert received[0]["secondary"] is None
    assert received[0]["force"] is True
    assert adapter._secondary_bars is secondary_bars


@pytest.mark.parametrize("bars", [pd.DataFrame(), pd.DataFrame({"open": [1.0]})])
def test_live_adapter_preserves_last_close_when_update_has_no_close(
    bars: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter._last_close = 123.0
    monkeypatch.setattr(adapter, "_rebuild_features", lambda _bars: pd.DataFrame())

    adapter.update_bars(bars)

    assert adapter._last_close == 123.0
    assert adapter._bars is bars


def test_live_adapter_requires_bars_before_building_observation() -> None:
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    with pytest.raises(RuntimeError, match=r"update_bars\(\) must be called"):
        adapter.build_observation()


def test_live_entry_state_visibility_requires_lifecycle_snapshot(tmp_path: Path) -> None:
    from live.runtime.strategy import RLStrategyAdapter

    overlay = tmp_path / "entry-state-overlay.yaml"
    overlay.write_text(
        "env:\n  entry_state_machine: true\n  entry_state_observation: true\n",
        encoding="utf-8",
    )
    adapter = RLStrategyAdapter(
        provider=SB3DecisionProvider(_StubModel(), input_schema_version=OBSERVATION_SCHEMA_V2),
        config_path="config/base/default.yaml",
        features_config_path=overlay,
        allow_runtime_normalization_fallback=True,
    )
    adapter._features = pd.DataFrame({"close": [20_000.0]})

    with pytest.raises(ValueError, match="entry_state"):
        adapter.build_observation({})


def test_live_adapter_rejects_provider_schema_and_normalization_artifact_mismatch(
    tmp_path: Path,
) -> None:
    from live.runtime.strategy import RLStrategyAdapter

    action_schema = ActionSchemaRef("a1", "hold", ("hold",), "discrete")

    class WrongSchemaProvider:
        metadata = PredictorMetadata("test", "test", "test", "wrong-observation", action_schema)

        def predict(self, input: DecisionInput, *, deterministic: bool = True) -> Decision:
            del input, deterministic
            return Decision(DiscreteAction(0, "hold"), action_schema)

    with pytest.raises(ValueError, match="input schema differs from the live observation schema"):
        RLStrategyAdapter(
            provider=WrongSchemaProvider(),
            config_path="config/base/default.yaml",
            allow_runtime_normalization_fallback=True,
        )

    missing_state = tmp_path / "missing-normalization.json"
    with pytest.raises(FileNotFoundError, match="feature normalization state not found"):
        RLStrategyAdapter(
            model=_StubModel(),
            config_path="config/base/default.yaml",
            normalization_state_path=missing_state,
        )

    invalid_state = tmp_path / "invalid-normalization.json"
    invalid_state.write_text('{"schema": "wrong"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported feature normalization state"):
        RLStrategyAdapter(
            model=_StubModel(),
            config_path="config/base/default.yaml",
            normalization_state_path=invalid_state,
        )

    valid_state = tmp_path / "normalization.json"
    valid_state.write_text('{"schema": "feature-normalization-v1", "stages": {}}', encoding="utf-8")
    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        normalization_state_path=valid_state,
    )
    assert adapter._normalization_state == {"schema": "feature-normalization-v1", "stages": {}}


def test_live_adapter_maps_scalar_and_directional_provider_decisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from live.runtime.strategy import RLStrategyAdapter

    class Provider:
        def __init__(self, action: ContinuousAction | StructuredAction) -> None:
            self.action = action
            coordinates = (
                tuple(action.coordinates)
                if isinstance(action, StructuredAction)
                else ("direction",)
            )
            self.metadata = PredictorMetadata(
                "test",
                "test",
                "test",
                OBSERVATION_SCHEMA_V2,
                ActionSchemaRef("a1", "action", coordinates, "continuous"),
            )

        def predict(self, input: DecisionInput, *, deterministic: bool = True) -> Decision:
            del input, deterministic
            return Decision(self.action, self.metadata.action_schema)

    adapter = RLStrategyAdapter(
        provider=Provider(ContinuousAction(-0.25)),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    monkeypatch.setattr(adapter, "build_observation", lambda _account_state=None: {})
    assert adapter.predict_signal() == -0.25
    assert adapter.last_decision is not None
    assert isinstance(adapter.last_decision.action, ContinuousAction)

    adapter.provider = Provider(StructuredAction({"direction": 1.0}))
    assert adapter.predict_signal() == 1.0
    assert adapter.last_decision is not None
    assert cast(Any, adapter.last_decision.action) == StructuredAction({"direction": 1.0})
    adapter.provider = Provider(StructuredAction({"risk": 0.5}))
    with pytest.raises(ValueError, match="must be discrete, scalar or include direction"):
        adapter.predict_signal()


def test_live_strategy_fails_closed_and_maps_sell_hold_with_secondary_data(
    trending_bars: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from live.runtime.contracts import LiveSignal
    from live.runtime.strategy import RLStrategyAdapter

    provider = SB3DecisionProvider(_StubModel(), input_schema_version=OBSERVATION_SCHEMA_V2)
    adapter = RLStrategyAdapter(
        provider=provider,
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    recorded_updates: list[tuple[pd.DataFrame, pd.DataFrame | None]] = []
    monkeypatch.setattr(
        adapter,
        "update_bars",
        lambda bars, secondary_bars=None: recorded_updates.append((bars, secondary_bars)),
    )

    secondary_bars = trending_bars.iloc[:2]

    class SecondaryData(_StubData):
        calls = 0

        def get_data(self) -> pd.DataFrame:
            self.calls += 1
            return secondary_bars

    secondary_data = SecondaryData(secondary_bars)
    strategy = adapter.as_strategy(_StubData(trending_bars), secondary_data)

    monkeypatch.setattr(adapter, "predict_signal", lambda: -1)
    assert strategy.signal() == ("US100.cash", LiveSignal.SELL)
    assert recorded_updates[-1][0] is trending_bars
    assert recorded_updates[-1][1] is secondary_bars
    assert secondary_data.calls == 1

    monkeypatch.setattr(adapter, "predict_signal", lambda: 0)
    assert strategy.signal() == ("US100.cash", LiveSignal.HOLD)

    def fail_inference() -> int:
        raise ValueError("invalid account snapshot")

    monkeypatch.setattr(adapter, "predict_signal", fail_inference)
    assert strategy.signal() == ("US100.cash", LiveSignal.NONE)


def test_rl_bridge_accepts_a_decision_provider(trending_bars):
    """The live consumer uses the provider contract independently of model loading."""
    from live.runtime.strategy import RLStrategyAdapter

    provider = SB3DecisionProvider(
        _StubModel(),
        input_schema_version=OBSERVATION_SCHEMA_V2,
    )
    adapter = RLStrategyAdapter(
        provider=provider,
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)

    state = {
        "equity": 100_000.0,
        "planned_risk_usd": 0.0,
        "trailing_drawdown": 0.0,
        "trailing_drawdown_limit": 10_000.0,
        "daily_loss": 0.0,
        "daily_loss_limit": 5_000.0,
        "loss_from_initial": 0.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 900.0,
        "entry_price": 0.0,
        "initial_sl_price": 0.0,
        "active_sl_price": 0.0,
        "remaining_size": 0.0,
        "initial_size": 0.0,
        "position_age_bars": 0.0,
        "tp_hit_mask": 0,
        "tp1_price": 0.0,
        "tp2_price": 0.0,
        "tp3_price": 0.0,
        "sl_mode": "fixed",
        "tp_mode": "fixed",
        "exit_mode": "structural",
    }
    assert adapter.predict_signal(state) == 1


def test_rl_bridge_maps_actions_to_signals(trending_bars, tmp_path: Path):
    """as_strategy maps action>0 → BUY, 0 → HOLD via the duck-typed source."""
    from live.runtime.strategy import RLStrategyAdapter

    cfg = OmegaConf.load("config/base/default.yaml")
    cfg.env.observation_schema_version = "account-state-v1"
    config_path = tmp_path / "bridge_test_config.yaml"
    OmegaConf.save(cfg, config_path)
    model = _StubModel()
    model._observation_schema = build_observation_schema("account-state-v1").to_dict()
    adapter = RLStrategyAdapter(
        model=model,
        config_path=config_path,
        allow_runtime_normalization_fallback=True,
    )
    strategy = adapter.as_strategy(_StubData(trending_bars))
    symbol, sig = strategy.signal()
    assert symbol == "US100.cash"
    assert sig.value == "buy"


def test_account_state_v2_live_policy_fails_closed_without_snapshot(
    trending_bars: pd.DataFrame, tmp_path: Path
) -> None:
    """The live strategy must not infer from account-state-v2 defaults."""
    from live.runtime.strategy import RLStrategyAdapter

    cfg = OmegaConf.load("config/base/default.yaml")
    cfg.env.observation_schema_version = "account-state-v2"
    config_path = tmp_path / "account_state_v2.yaml"
    OmegaConf.save(cfg, config_path)

    model = _StubModel()
    model._observation_schema = build_observation_schema("account-state-v2").to_dict()
    adapter = RLStrategyAdapter(
        model=model,
        config_path=config_path,
        allow_runtime_normalization_fallback=True,
    )
    strategy = adapter.as_strategy(_StubData(trending_bars))

    symbol, signal = strategy.signal()

    assert symbol == "US100.cash"
    assert signal.value == "none"


def test_repeated_payout_live_policy_builds_its_full_account_schema(
    trending_bars: pd.DataFrame, tmp_path: Path
) -> None:
    from live.runtime.strategy import RLStrategyAdapter

    cfg = OmegaConf.load("config/base/default.yaml")
    cfg.trading_policy.mode = "repeated_payout"
    config_path = tmp_path / "repeated_payout.yaml"
    OmegaConf.save(cfg, config_path)

    model = _StubModel()
    model._observation_schema = build_observation_schema(
        OBSERVATION_SCHEMA_REPEATED_PAYOUT
    ).to_dict()
    adapter = RLStrategyAdapter(
        model=model,
        config_path=config_path,
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)
    state = {
        "equity": 99_500.0,
        "planned_risk_usd": 900.0,
        "trailing_drawdown": 0.005,
        "trailing_drawdown_limit": 10_000.0,
        "daily_loss": 500.0,
        "daily_loss_limit": 5_000.0,
        "loss_from_initial": 500.0,
        "max_loss_limit": 10_000.0,
        "risk_per_trade_limit": 900.0,
        "entry_price": 20_000.0,
        "initial_sl_price": 19_990.0,
        "active_sl_price": 19_995.0,
        "remaining_size": 1.0,
        "initial_size": 1.0,
        "position_age_bars": 3.0,
        "tp_hit_mask": 0,
        "tp1_price": 20_010.0,
        "tp2_price": 20_020.0,
        "tp3_price": 20_030.0,
        "sl_mode": "fixed",
        "tp_mode": "fixed",
        "exit_mode": "structural",
    }

    observation = adapter.build_observation(state)

    assert adapter._observation_schema.version == OBSERVATION_SCHEMA_REPEATED_PAYOUT
    assert observation["account"].shape == (28,)
    assert observation["account"][5] == pytest.approx(0.1)
    assert adapter.predict_signal(state) == 1
    with pytest.raises(ValueError, match="requires complete account state"):
        adapter.build_observation({"equity": 100_000.0})


def test_rl_bridge_too_few_bars_no_signal(trending_bars):
    """Bridge returns NONE when there isn't enough history."""
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    strategy = adapter.as_strategy(_StubData(trending_bars.iloc[:5]))
    _, sig = strategy.signal()
    assert sig.value == "none"


def test_live_adapter_retains_the_single_typed_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    schema = ActionSchemaRef(
        version="live-action-v1",
        key="hold-enter",
        coordinates=("hold", "enter"),
        kind="discrete",
    )
    decision = Decision(DiscreteAction(1, "enter"), schema)

    class Provider:
        metadata = PredictorMetadata(
            provider_id="test-provider",
            model_family="test",
            training_paradigm="test",
            input_schema_version="account-state-v2",
            action_schema=schema,
        )

        def __init__(self) -> None:
            self.calls = 0

        def predict(self, input: DecisionInput, *, deterministic: bool = True) -> Decision:
            assert input.schema_version == "account-state-v2"
            assert deterministic is True
            self.calls += 1
            return decision

    provider = Provider()
    adapter = RLStrategyAdapter(
        provider=provider,
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    monkeypatch.setattr(adapter, "build_observation", lambda _account_state=None: {})

    assert adapter.predict_signal() == 1
    assert provider.calls == 1
    assert adapter.last_decision is decision
