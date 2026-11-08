"""Event-backtest execution of already populated multi-target positions."""

from __future__ import annotations

import unittest
from types import MethodType, SimpleNamespace
from typing import cast

import numpy as np
import pandas as pd

from market_data.loading.ticks import (
    TickBook,
    TickExecutionUnavailable,
    event_keyed_execution_rng,
    resolve_tick_execution,
)
from simulation.backtest.protective_events import process_protective_and_account_events
from simulation.backtest.runtime import BacktestSettings, BacktestState
from simulation.environment.env import TradingEnv
from simulation.environment.market_view import BarView
from trading import AccountState
from trading.execution import Broker, CostModel
from trading.risk import FTMOGuardrails


class MultiTargetProtectiveLifecycleTest(unittest.TestCase):
    @staticmethod
    def _run_environment(
        *,
        tickbook: TickBook | None,
        fractions: tuple[float, ...] = (0.3, 0.3, 0.4),
        runner_fraction: float = 0.0,
        low: float = 99.5,
        high: float | None = None,
        direction: int = 1,
        require_tick_execution: bool = False,
        randomized_fill_latency_ms: float = 0.0,
        server_side_protective_orders: bool = False,
        breakeven_trigger_r: float = 0.0,
        breakeven_buffer_pts: float = 0.1,
    ) -> SimpleNamespace:
        cost_model = CostModel(spread_points=0.0, commission_per_lot=2.0, point_size=0.01)
        broker = Broker(cost_model=cost_model, contract_size=1.0)
        account = AccountState(initial_balance=100_000.0)
        position = broker.open_position(account, (100.0, 100.0), 1.0, direction)
        assert position is not None
        position.position_id = "controlled:multi-target"
        position.entry_timestamp = pd.Timestamp("2026-01-05T09:59:00Z")
        position.initial_size = 1.0
        position.tp_initial_size = 1.0
        position.sl_price = 99.0 if direction == 1 else 101.0
        first_target = 100.5 if direction == 1 else 99.5
        position.tp_price = first_target
        position.tp1_price = first_target
        position.tp2_price = (101.0 if direction == 1 else 99.0) if len(fractions) > 1 else None
        position.tp3_price = (101.5 if direction == 1 else 98.5) if len(fractions) > 2 else None
        position.tp_lot_fractions = fractions
        position.ema_runner_fraction = runner_fraction
        bar_time = pd.Timestamp("2026-01-05T10:00:00Z")

        def resolve_randomized_quote(
            tick_time: pd.Timestamp, *, event_key: str | None = None
        ) -> tuple[object, dict[str, object]]:
            assert tickbook is not None
            if randomized_fill_latency_ms == 0.0:
                quote_event = tickbook.quote_event_at(pd.Timestamp(tick_time))
                assert quote_event is not None
                quote_time, bid, ask = quote_event
                quote_snapshot = SimpleNamespace(
                    bid=bid,
                    ask=ask,
                    tick_time=quote_time,
                    order_time=pd.Timestamp(tick_time),
                    arrival_time=pd.Timestamp(tick_time),
                    latency_ns=0,
                )
                return quote_snapshot, {
                    "fill_quote_source": "tick",
                    "execution_order_time": quote_snapshot.order_time,
                    "execution_arrival_time": quote_snapshot.arrival_time,
                    "execution_latency_ns": quote_snapshot.latency_ns,
                    "actual_tick_time": quote_snapshot.tick_time,
                }
            stable_key = event_key or (
                f"protective_exit:{direction}:tp:{pd.Timestamp(tick_time).value}"
            )
            quote = resolve_tick_execution(
                tickbook,
                pd.Timestamp(tick_time),
                event_keyed_execution_rng(7, stable_key),
                max_latency_ns_exclusive=int(randomized_fill_latency_ms * 1_000_000),
                max_quote_wait_ns=1_000_000_000,
            )
            assert quote is not None
            return quote, {
                "fill_quote_source": "tick",
                "execution_order_time": quote.order_time,
                "execution_arrival_time": quote.arrival_time,
                "execution_latency_ns": quote.latency_ns,
                "actual_tick_time": quote.tick_time,
            }

        env = SimpleNamespace(
            account=account,
            broker=broker,
            cost_model=cost_model,
            position=position,
            _tickbook=tickbook,
            fill_delay_ms=0,
            randomized_fill_latency_ms=randomized_fill_latency_ms,
            tick_execution_required=require_tick_execution,
            server_side_protective_orders=server_side_protective_orders,
            _breakeven_trigger_r=breakeven_trigger_r,
            _breakeven_buffer_pts=breakeven_buffer_pts,
            _last_realized_close_pnl=None,
            _last_realized_close_r=None,
            _pending_realized_r=None,
            strategy_actions=False,
            trade_log=[],
            sessions_with_trades=set(),
            _current_session_id=lambda: 0,
            _bar_times=[bar_time],
            _bar_time=lambda _index: bar_time,
            _n_bars=1,
            _minutes_per_step=1,
            step_idx=0,
            _maybe_ema_exit=lambda *_args: None,
            _resolve_randomized_tick_quote=resolve_randomized_quote,
            tick_protective_assertion_calls=[],
        )
        for name in (
            "_stamp_exit",
            "_note_close",
            "_record_stop_update",
            "_sl_tp_fill_quote",
            "_exit_side_bar_range",
            "_check_multi_tp_ticks",
            "_assert_tick_protective_events_observed",
            "_adverse_tick_fill_quote",
            "_close_at_quote",
        ):
            setattr(env, name, MethodType(getattr(TradingEnv, name), env))
        original_assertion = env._assert_tick_protective_events_observed

        def record_assertion(self: SimpleNamespace, *args: object, **kwargs: object) -> None:
            self.tick_protective_assertion_calls.append((args, kwargs))
            original_assertion(*args, **kwargs)

        env._assert_tick_protective_events_observed = MethodType(record_assertion, env)
        bar = SimpleNamespace(
            open=100.0,
            low=low if direction == 1 else 98.0,
            high=(102.0 if direction == 1 else 100.5) if high is None else high,
            close=101.0 if direction == 1 else 99.0,
            spread=0.0,
        )
        TradingEnv._check_sl_tp(cast(TradingEnv, env), cast(BarView, bar), 101.0, 101.0, bar_idx=0)
        return env

    def _run(
        self,
        *,
        tickbook: TickBook | None = None,
        fractions: tuple[float, ...] = (0.3, 0.3, 0.4),
        runner_fraction: float = 0.0,
        low: float = 99.5,
        direction: int = 1,
        randomized_fill_latency_ms: float = 0.0,
        server_side_protective_orders: bool = False,
    ) -> BacktestState:
        cost_model = CostModel(spread_points=0.0, commission_per_lot=2.0, point_size=0.01)
        broker = Broker(cost_model=cost_model, contract_size=1.0)
        account = AccountState(initial_balance=100_000.0)
        position = broker.open_position(account, (100.0, 100.0), 1.0, direction)
        assert position is not None
        position.initial_size = 1.0
        position.tp_initial_size = 1.0
        position.sl_price = 99.0 if direction == 1 else 101.0
        first_target = 100.5 if direction == 1 else 99.5
        position.tp_price = first_target
        position.tp1_price = first_target
        position.tp2_price = (101.0 if direction == 1 else 99.0) if len(fractions) > 1 else None
        position.tp3_price = (101.5 if direction == 1 else 98.5) if len(fractions) > 2 else None
        position.tp_lot_fractions = fractions
        position.ema_runner_fraction = runner_fraction
        state = BacktestState(account=account, position=position)
        settings = BacktestSettings(
            cost_model=cost_model,
            lots=1.0,
            max_loss_per_trade_usd=None,
            take_profit_per_trade_usd=None,
            tickbook=tickbook,
            fill_delay_ms=0,
            randomized_fill_latency_ms=randomized_fill_latency_ms,
            max_tick_quote_wait_ms=1_000,
            tick_execution_required=tickbook is not None,
            server_side_protective_orders=server_side_protective_orders,
            use_structure_sl_tp=True,
            risk_frac=0.01,
            policy_risk_frac_range=(0.01, 0.01),
            rr_ratio=2.0,
            swing_buffer_pts=0.0,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01,
            contract_size=1.0,
            hold_on_zero=False,
            exit_action=None,
            block_overnight=False,
            execution_seed=7,
        )
        bar_time = pd.Timestamp("2026-01-05T10:00:00Z")
        bar_duration = pd.Timedelta(minutes=1)
        row = pd.Series(
            {
                "open": 100.0,
                "high": 102.0 if direction == 1 else 100.5,
                "low": low if direction == 1 else 98.0,
                "close": 101.0 if direction == 1 else 99.0,
                "spread": 0.0,
            }
        )
        bars = pd.DataFrame([row], index=[bar_time])

        process_protective_and_account_events(
            state,
            settings,
            broker,
            FTMOGuardrails(),
            bars,
            row,
            i=0,
            bar_time=bar_time,
            bar_duration=bar_duration,
            session=0,
            is_ny=True,
            bar_quote=(101.0, 101.0),
            entry_time=bar_time - bar_duration,
            position_active_in_bar=True,
            full_bar_available_after_entry=True,
            execution_rng=np.random.default_rng(7),
            resolve_bar_execution=lambda: (
                (101.0, 101.0),
                bar_time + bar_duration,
                "bar_close",
                {},
            ),
            fill_quote_event=lambda *args, **kwargs: ((101.0, 101.0), bar_time, "bar", {}),
            sl_tp_fill_quote=lambda _direction, price, _cost: (price, price),
            bar_spread_price_units=lambda _row, _cost: 0.0,
            is_last_ny_bar=lambda *_args: False,
            eod_guard_due=False,
        )
        return state

    def test_bar_can_fill_all_targets_with_configured_sizes(self) -> None:
        state = self._run()
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env = self._run_environment(tickbook=None)
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]
        self.assertEqual(
            [record["type"] for record in closes],
            [
                "tp_partial_close",
                "tp_partial_close",
                "tp_close",
            ],
        )
        self.assertEqual(
            [record["reason"] for record in closes],
            [
                "structure_tp1",
                "structure_tp2",
                "structure_tp3",
            ],
        )
        for record, expected_size in zip(closes, (0.3, 0.3, 0.4), strict=True):
            self.assertAlmostEqual(record["size"], expected_size)
        self.assertEqual([record["position_complete"] for record in closes], [False, False, True])
        self.assertIsNone(state.position)
        for actual, reference in zip(closes, env_closes, strict=True):
            for field in ("reason", "tp_slot", "position_complete"):
                self.assertEqual(actual[field], reference[field])
            for field in ("size", "pnl", "price", "net_pnl", "entry_commission_allocated"):
                self.assertAlmostEqual(actual[field], reference[field])
        self.assertAlmostEqual(
            sum(record["net_pnl"] for record in closes), state.account.balance - 100_000.0
        )
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_tick_path_fills_targets_at_tick_quotes(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_times = np.array(
            [
                (start + pd.Timedelta(seconds=10)).value,
                (start + pd.Timedelta(seconds=20)).value,
                (start + pd.Timedelta(seconds=30)).value,
            ],
            dtype=np.int64,
        )
        book = TickBook(
            tick_times, np.array([100.5, 101.0, 101.5]), np.array([100.51, 101.01, 101.51])
        )
        state = self._run(tickbook=book)
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env = self._run_environment(tickbook=book)
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]
        for record, expected_size in zip(closes, (0.3, 0.3, 0.4), strict=True):
            self.assertAlmostEqual(record["size"], expected_size)
        self.assertTrue(all(record["fill_quote_source"] == "tick" for record in closes))
        self.assertIsNone(state.position)
        for actual, reference in zip(closes, env_closes, strict=True):
            for field in ("reason", "tp_slot", "position_complete"):
                self.assertEqual(actual[field], reference[field])
            for field in ("size", "pnl", "price", "net_pnl", "entry_commission_allocated"):
                self.assertAlmostEqual(actual[field], reference[field])
        self.assertAlmostEqual(
            sum(record["net_pnl"] for record in closes), state.account.balance - 100_000.0
        )
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_multi_target_tick_replay_checks_only_remaining_position_levels(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_time = start + pd.Timedelta(seconds=10)
        book = TickBook(
            np.array([tick_time.value], dtype=np.int64),
            np.array([100.5]),
            np.array([100.51]),
        )
        env = self._run_environment(
            tickbook=book,
            runner_fraction=0.2,
            high=100.75,
            require_tick_execution=True,
        )

        self.assertIsNotNone(env.position)
        self.assertEqual(len(env.tick_protective_assertion_calls), 1)
        self.assertEqual([record.get("type") for record in env.trade_log], ["tp_partial_close"])

    def test_multi_target_replay_does_not_apply_new_stop_to_prior_ohlc_range(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_times = np.array(
            [
                (start + pd.Timedelta(seconds=1)).value,
                (start + pd.Timedelta(seconds=10)).value,
                (start + pd.Timedelta(seconds=11)).value,
            ],
            dtype=np.int64,
        )
        book = TickBook(
            tick_times,
            np.array([100.7, 99.4, 99.5]),
            np.array([100.8, 99.5, 99.6]),
        )
        env = self._run_environment(
            tickbook=book,
            fractions=(0.8,),
            runner_fraction=0.2,
            high=100.8,
            direction=-1,
            require_tick_execution=True,
            breakeven_trigger_r=0.5,
        )

        self.assertIsNotNone(env.position)
        self.assertAlmostEqual(env.position.size, 0.2)
        self.assertAlmostEqual(env.position.sl_price, 99.9)
        self.assertEqual(len(env.tick_protective_assertion_calls), 1)
        self.assertEqual(
            env.tick_protective_assertion_calls[0][1]["protective_levels"],
            (None, (None, None, None)),
        )

    def test_randomized_tick_latency_matches_across_all_partial_targets(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        quote_rows: list[tuple[pd.Timestamp, float, float]] = []
        for offset_seconds, bid in ((10, 100.5), (20, 101.0), (30, 101.5)):
            trigger_time = start + pd.Timedelta(seconds=offset_seconds)
            quote_rows.append((trigger_time, bid, bid + 0.01))
            quote_rows.extend(
                (
                    trigger_time + pd.Timedelta(milliseconds=offset_ms),
                    bid,
                    bid + 0.01,
                )
                for offset_ms in (5, 10, 20, 25, 30)
            )
        quote_rows.sort(key=lambda row: row[0])
        quote_times = pd.DatetimeIndex([row[0] for row in quote_rows])
        book = TickBook(
            quote_times.to_numpy(dtype="datetime64[ns]").astype(np.int64),
            np.asarray([row[1] for row in quote_rows]),
            np.asarray([row[2] for row in quote_rows]),
        )

        state = self._run(tickbook=book, randomized_fill_latency_ms=30.0)
        env = self._run_environment(
            tickbook=book,
            require_tick_execution=True,
            randomized_fill_latency_ms=30.0,
        )
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]
        self.assertEqual(len(closes), 3)
        self.assertEqual(len(env_closes), 3)
        for actual, reference in zip(closes, env_closes, strict=True):
            for field in (
                "reason",
                "tp_slot",
                "position_complete",
                "execution_latency_ns",
                "execution_arrival_time",
                "actual_tick_time",
            ):
                self.assertEqual(actual[field], reference[field])
            for field in ("size", "pnl", "price", "net_pnl"):
                self.assertAlmostEqual(actual[field], reference[field])
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_server_side_multi_target_fills_use_trigger_ticks_in_both_engines(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_times = np.array(
            [
                (start + pd.Timedelta(seconds=10)).value,
                (start + pd.Timedelta(seconds=20)).value,
                (start + pd.Timedelta(seconds=30)).value,
            ],
            dtype=np.int64,
        )
        book = TickBook(
            tick_times,
            np.array([100.5, 101.0, 101.5]),
            np.array([100.51, 101.01, 101.51]),
        )

        state = self._run(
            tickbook=book,
            randomized_fill_latency_ms=30.0,
            server_side_protective_orders=True,
        )
        env = self._run_environment(
            tickbook=book,
            require_tick_execution=True,
            randomized_fill_latency_ms=30.0,
            server_side_protective_orders=True,
        )
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]

        self.assertEqual(len(closes), 3)
        self.assertEqual(len(env_closes), 3)
        for actual, reference, expected_time in zip(
            closes,
            env_closes,
            pd.to_datetime(tick_times, unit="ns", utc=True),
            strict=True,
        ):
            for field in (
                "reason",
                "tp_slot",
                "position_complete",
                "execution_latency_ns",
                "execution_arrival_time",
                "actual_tick_time",
            ):
                self.assertEqual(actual[field], reference[field])
            self.assertEqual(actual["execution_latency_ns"], 0)
            self.assertEqual(pd.Timestamp(actual["actual_tick_time"]), expected_time)
            self.assertEqual(pd.Timestamp(actual["execution_arrival_time"]), expected_time)
            for field in ("size", "pnl", "price", "net_pnl"):
                self.assertAlmostEqual(actual[field], reference[field])
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_final_target_preserves_configured_ema_runner(self) -> None:
        state = self._run(fractions=(0.75,), runner_fraction=0.25)
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        self.assertEqual(len(closes), 1)
        self.assertAlmostEqual(closes[0]["size"], 0.75)
        self.assertFalse(closes[0]["position_complete"])
        self.assertIsNotNone(state.position)
        assert state.position is not None
        self.assertAlmostEqual(state.position.size, 0.25)
        self.assertIsNone(state.position.tp_price)

    def test_short_bar_ladder_matches_environment(self) -> None:
        state = self._run(direction=-1, low=98.0)
        env = self._run_environment(tickbook=None, direction=-1, low=98.0)
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]
        self.assertEqual(len(closes), 3)
        for actual, reference in zip(closes, env_closes, strict=True):
            self.assertEqual(actual["reason"], reference["reason"])
            for field in ("size", "pnl", "price"):
                self.assertAlmostEqual(actual[field], reference[field])
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_short_tick_ladder_matches_environment(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_times = np.array(
            [
                (start + pd.Timedelta(seconds=10)).value,
                (start + pd.Timedelta(seconds=20)).value,
                (start + pd.Timedelta(seconds=30)).value,
            ],
            dtype=np.int64,
        )
        asks = np.array([99.5, 99.0, 98.5])
        book = TickBook(tick_times, asks - 0.01, asks)
        state = self._run(tickbook=book, direction=-1, low=98.0)
        env = self._run_environment(tickbook=book, direction=-1, low=98.0)
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        env_closes = [
            record for record in env.trade_log if record.get("type", "").startswith("tp_")
        ]
        self.assertEqual(len(closes), 3)
        for actual, reference in zip(closes, env_closes, strict=True):
            self.assertEqual(actual["reason"], reference["reason"])
            for field in ("size", "pnl", "price", "net_pnl"):
                self.assertAlmostEqual(actual[field], reference[field])
            self.assertEqual(actual["position_complete"], reference["position_complete"])
        self.assertAlmostEqual(state.account.balance, env.account.balance)

    def test_strict_tick_mode_rejects_ohlc_target_without_matching_tick(self) -> None:
        start = pd.Timestamp("2026-01-05T10:00:00Z")
        tick_time = start + pd.Timedelta(seconds=10)
        book = TickBook(
            np.array([tick_time.value], dtype=np.int64),
            np.array([100.5]),
            np.array([100.51]),
        )
        with self.assertRaisesRegex(TickExecutionUnavailable, "no matching tick trigger"):
            self._run(tickbook=book)
        with self.assertRaisesRegex(TickExecutionUnavailable, "no matching tick trigger"):
            self._run_environment(tickbook=book, require_tick_execution=True)

    def test_stop_remains_first_when_bar_also_reaches_targets(self) -> None:
        state = self._run(low=98.5)
        closes = [record for record in state.trade_log if record.get("type", "").startswith("tp_")]
        stop_closes = [record for record in state.trade_log if record.get("type") == "stop_close"]
        self.assertEqual(closes, [])
        self.assertEqual(len(stop_closes), 1)
        self.assertIsNone(state.position)


if __name__ == "__main__":
    unittest.main()
