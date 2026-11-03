#!/usr/bin/env python3
"""Compare scheduled TickBook session closes across the environment and backtest.

The fixture is synthetic and controlled. It checks execution semantics; it is
not a local-feed sample, policy replay, or economic-performance estimate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root
from market_data.loading.ticks import TickBook
from simulation.backtest import run_backtest
from simulation.environment.env import TradingEnv
from trading.execution import CostModel

ROOT = repository_root(__file__)
DEFAULT_OUTPUT = Path(
    "evidence/research/simulator_execution_parity/scheduled_session_close/"
    "scheduled_session_close.json"
)
SOURCE_PATHS = (
    "simulation/backtest/event_driven_backtest.py",
    "simulation/backtest/protective_events.py",
    "simulation/backtest/runtime.py",
    "simulation/environment/episode_runtime.py",
    "market_data/loading/ticks.py",
    "tests/integration/backtest/test_risk_lifecycle_characterization.py",
)
FIELDS = (
    "type",
    "reason",
    "direction",
    "price",
    "pnl",
    "time",
    "order_submission_time",
    "execution_arrival_time",
    "execution_latency_ns",
    "actual_tick_time",
    "fill_time",
    "fill_quote_source",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: _json_value(event.get(key)) for key in FIELDS if key in event}
        for event in events
        if event.get("type") in {"open", "eod_close"}
    ]


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame, TickBook, dict[str, Any]]:
    index = pd.date_range("2025-01-06 16:30", periods=8, freq="1min", tz="Etc/GMT-3")
    session_labels = ("ny", "ny", "ny", "ny", "ny", "ny", "asia", "asia")
    bars = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.1,
            "low": 99.9,
            "close": 100.0,
            "spread": 0.0,
            "session_id": 0,
            "session": session_labels,
        },
        index=index,
    )
    features = pd.DataFrame({"last_swing_low": 90.0, "last_swing_high": 120.0}, index=index)
    minute_times = pd.DatetimeIndex([*index, index[-1] + pd.Timedelta(minutes=1)])
    minute_bids = (100.0, 100.0, 100.0, 100.0, 100.0, 101.0, 102.0, 103.0, 104.0)
    quote_rows = []
    for timestamp, bid in zip(minute_times, minute_bids, strict=True):
        quote_rows.append((timestamp, bid, bid + 0.2))
        if timestamp == index[5]:
            quote_rows.extend(
                (timestamp + pd.Timedelta(milliseconds=offset), price, price + 0.2)
                for offset, price in (
                    (5, 101.1),
                    (10, 101.2),
                    (20, 101.3),
                    (25, 101.4),
                )
            )
    quote_rows.sort(key=lambda quote: quote[0])
    tick_times = pd.DatetimeIndex([quote[0] for quote in quote_rows])
    bids = np.asarray([quote[1] for quote in quote_rows])
    asks = np.asarray([quote[2] for quote in quote_rows])
    tickbook = TickBook(tick_times.to_numpy(dtype="datetime64[ns]").astype(np.int64), bids, asks)
    source = {
        "timezone": "Etc/GMT-3",
        "bars": [
            {
                "time": timestamp.isoformat(),
                "open": 100.0,
                "high": 100.1,
                "low": 99.9,
                "close": 100.0,
                "session": session,
            }
            for timestamp, session in zip(index, bars["session"], strict=True)
        ],
        "ticks": [
            {"time": timestamp.isoformat(), "bid": float(bid), "ask": float(ask)}
            for timestamp, bid, ask in zip(tick_times, bids, asks, strict=True)
        ],
        "features": {"last_swing_low": 90.0, "last_swing_high": 120.0},
    }
    return bars, features, tickbook, source


def _valid_scheduled_fill(event: dict[str, Any], latency_limit_ms: float) -> bool:
    submission = pd.Timestamp(event["order_submission_time"])
    arrival = pd.Timestamp(event["execution_arrival_time"])
    actual_tick = pd.Timestamp(event["actual_tick_time"])
    latency_ns = int(event["execution_latency_ns"])
    deadline = submission + pd.Timedelta(minutes=1)
    sampled_latency_valid = (
        latency_ns == 0
        if latency_limit_ms == 0.0
        else 0 <= latency_ns < int(latency_limit_ms * 1_000_000)
    )
    return bool(
        sampled_latency_valid
        and arrival - submission == pd.Timedelta(latency_ns, unit="ns")
        and arrival <= actual_tick <= deadline
    )


def build_report() -> dict[str, Any]:
    bars, features, tickbook, fixture = _fixture()
    fixture_bytes = json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode()
    scenarios = []
    for latency_ms in (0.0, 30.0):
        eod_risk = {
            "max_loss_usd": 1e9,
            "respect_planned_risk": False,
            "max_age_hours": 1e9,
            "stale_bars": 1_000,
            "progress_threshold_atr": 1_000.0,
            "breakeven_trigger_r": 0.0,
        }
        common: dict[str, Any] = {
            "obs_window": 1,
            "initial_balance": 50_000.0,
            "cost_model": CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0),
            "tickbook": tickbook,
            "tick_execution_required": True,
            "randomized_fill_latency_ms": latency_ms,
            "guardrail_kwargs": {
                "daily_loss_limit": 50_000.0,
                "max_loss_limit": 50_000.0,
                "risk_per_trade_limit": 10_000.0,
                "soft_daily_loss_limit": 0.0,
                "soft_max_loss_limit": 0.0,
                "trailing_dd_limit": 0.0,
            },
            "min_lot": 0.01,
            "max_lot": 1.0,
            "contract_size": 1.0,
            "max_loss_per_trade_usd": 1_000.0,
            "eod_risk": eod_risk,
            "block_overnight": True,
        }
        env = TradingEnv(
            bars=bars,
            features=features,
            risk_frac_range=(0.001, 0.001),
            rr_ratio_range=(1.0, 1.0),
            **common,
        )
        env.reset(seed=11)
        for action in (1, 0, 0, 0, 0):
            env.step(action)

        actions = iter((1, 0, 0, 0, 0))
        backtest = run_backtest(
            bars,
            features,
            lambda _observation: next(actions, 0),
            execution_seed=11,
            risk_frac=0.001,
            rr_ratio=1.0,
            use_structure_sl_tp=True,
            swing_buffer_pts=0.0,
            hold_on_zero=True,
            **common,
        )
        env_events = _event_rows(env.trade_log)
        backtest_events = _event_rows(backtest["trades"].to_dict("records"))
        env_close = next(event for event in env_events if event.get("reason") == "session_end")
        backtest_close = next(
            event for event in backtest_events if event.get("reason") == "session_end"
        )
        matched_fields = (
            "time",
            "order_submission_time",
            "actual_tick_time",
            "fill_time",
            "price",
            "pnl",
        )
        close_matches = all(env_close[field] == backtest_close[field] for field in matched_fields)
        env_equity = float(env.account.equity)
        backtest_equity = float(backtest["account"].equity)
        scenarios.append(
            {
                "randomized_fill_latency_ms": latency_ms,
                "environment_events": env_events,
                "backtest_events": backtest_events,
                "close_fields_match": bool(close_matches),
                "environment_final_equity": env_equity,
                "backtest_final_equity": backtest_equity,
                "final_equity_matches": bool(
                    np.isclose(env_equity, backtest_equity, rtol=0, atol=1e-9)
                ),
                "environment_close_latency_valid": _valid_scheduled_fill(env_close, latency_ms),
                "backtest_close_latency_valid": _valid_scheduled_fill(backtest_close, latency_ms),
                "randomized_arrival_instants_match": (
                    env_close["execution_arrival_time"] == backtest_close["execution_arrival_time"]
                ),
            }
        )
    source_hashes = {path: _sha256(ROOT / path) for path in SOURCE_PATHS}
    generator_path = Path(__file__).resolve().relative_to(ROOT).as_posix()
    source_hashes[generator_path] = _sha256(Path(__file__).resolve())
    return {
        "schema_version": 1,
        "scenario": "scheduled_session_close",
        "interpretation": "Synthetic execution-contract regression; not a local-feed sample, policy replay, or economic estimate.",
        "fixture": fixture,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "controlled_settings": {
            "initial_balance": 50_000.0,
            "risk_fraction": 0.001,
            "risk_per_trade_limit": 10_000.0,
            "contract_size": 1.0,
            "cost_spread_points": 0.0,
            "point_size": 0.01,
            "commission_per_lot": 0.0,
            "bar_duration_seconds": 60,
        },
        "scenarios": scenarios,
        "trace_passed": all(
            item["close_fields_match"]
            and item["final_equity_matches"]
            and item["environment_close_latency_valid"]
            and item["backtest_close_latency_valid"]
            for item in scenarios
        ),
        "source_sha256": source_hashes,
        "limitations": [
            "The fixture uses one-minute quote spacing; equal selected quotes do not establish common randomized arrivals on sub-minute quote sequences.",
            "The environment and backtest RNG streams select different arrival instants with 30 ms latency in this fixture.",
            "One controlled session close does not complete Stage E lifecycle, account, live-risk, or feed-chronology acceptance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(args.out, report)
    print(json.dumps({"out": str(args.out), "trace_passed": report["trace_passed"]}, indent=2))
    if not report["trace_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
