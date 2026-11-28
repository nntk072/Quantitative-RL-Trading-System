"""Independent bounded reference checks for current product contracts."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable

import numpy as np
import pandas as pd


def oracle_risk_capacity(data: bytes) -> None:
    """Compare account and risk calculations against exact integer-cent arithmetic."""
    from trading.account.limits import canonical_daily_loss, daily_floor, remaining_daily_capacity
    from trading.risk.budget import approve_dynamic_risk

    raw = data.ljust(12, b"\0")
    a, b, c, d, e, f = (int.from_bytes(raw[i : i + 2], "little") for i in range(0, 12, 2))
    start, equity, limit = 100000 + a, 90000 + b, c
    assert canonical_daily_loss(start, equity) == max(0, start - equity)
    assert daily_floor(start, limit) == start - limit
    assert remaining_daily_capacity(start, equity, limit) == max(0, equity - start + limit)
    decision = approve_dynamic_risk(
        equity=equity,
        risk_frac=d / 65536,
        max_agent_risk_frac=e / 65536,
        daily_capacity=c,
        account_capacity=a,
        execution_reserve_usd=f,
    )
    cap = min(equity * e / 65536, c, a)
    assert decision.policy_cap_usd == cap
    assert decision.approved_usd == min(equity * d / 65536, max(0, cap - f))


def oracle_action_geometry(data: bytes) -> None:
    """Exercise versioned action coordinates and candidate geometry round trips."""
    from decisioning.actions import build_action_schema
    from decisioning.trade_setup import (
        CANDIDATE_GEOMETRY_ENTRY_TYPES,
        TRADE_SETUP_DIRECTIONS,
        TRADE_SETUP_IDEAS,
        TRADE_SETUP_TIMEFRAMES,
        candidate_geometry_slot,
        candidate_geometry_slot_semantics,
        trade_setup_candidate,
        trade_setup_candidate_id,
        trade_setup_center,
        trade_setup_id_from_box,
    )

    raw = data.ljust(5, b"\0")
    direction, sl, tp, multi, simplex = [bool(raw[0] & (1 << i)) for i in range(5)]
    try:
        schema = build_action_schema(
            has_direction=direction,
            has_sl_mode=sl,
            has_tp_mode=tp,
            has_multi_tp=multi,
            has_simplex=simplex,
        )
    except ValueError:
        assert simplex and not multi
    else:
        assert not simplex or multi
        names = (["direction"] if direction else []) + ["intensity", "stop", "risk"]
        names += ["tp1_sel", "tp2_sel", "tp3_sel"] if multi else ["target"]
        names += (["sl_mode"] if sl else []) + (["tp_mode"] if tp else [])
        names += (["z1", "z2"] if simplex else []) + ["exit"]
        assert schema.names == tuple(names)
        assert schema.width == len(set(names))
    idea = TRADE_SETUP_IDEAS[raw[1] % len(TRADE_SETUP_IDEAS)]
    tf = TRADE_SETUP_TIMEFRAMES[raw[2] % len(TRADE_SETUP_TIMEFRAMES)]
    side = TRADE_SETUP_DIRECTIONS[raw[3] % len(TRADE_SETUP_DIRECTIONS)]
    entry = CANDIDATE_GEOMETRY_ENTRY_TYPES[raw[4] % len(CANDIDATE_GEOMETRY_ENTRY_TYPES)]
    cid = trade_setup_candidate_id(idea, tf, side)
    candidate = trade_setup_candidate(cid)
    assert (candidate.idea, candidate.setup_timeframe, candidate.direction) == (idea, tf, side)
    assert trade_setup_id_from_box(trade_setup_center(cid)) == cid
    assert candidate_geometry_slot_semantics(candidate_geometry_slot(cid, entry)) == (cid, entry)


def oracle_tick_lookup(data: bytes) -> None:
    """Compare source-order quote lookup and limit crossing with linear search."""
    from market_data.loading.ticks import TickBook

    raw = data.ljust(4, b"\0")[:76]
    offset = 1735000000000000000
    times: list[int] = []
    bids: list[float] = []
    asks: list[float] = []
    current = offset
    for i in range(min(24, len(raw) // 3)):
        gap, bid, spread = raw[i * 3 : i * 3 + 3]
        current += (gap % 5) * 1000000
        times.append(current)
        bids.append(100.0 + bid / 8)
        asks.append(bids[-1] + (spread % 8) / 8)
    book = TickBook(np.array(times, dtype=np.int64), np.array(bids), np.array(asks))
    query = offset + (raw[0] % 120 - 2) * 1000000
    stamp = pd.Timestamp(query, unit="ns", tz="UTC")
    rows = list(zip(times, bids, asks, strict=True))
    expected = next((r for r in rows if r[0] >= query), None)
    actual = book.execution_quote_event_at(stamp)
    assert (None if actual is None else (actual[0].value, *actual[1:])) == expected
    expected_quote = None if not times or query < times[0] else expected
    actual = book.quote_event_at(stamp)
    assert (None if actual is None else (actual[0].value, *actual[1:])) == expected_quote
    side = 1 if raw[1] % 2 else -1
    strict = bool(raw[2] % 2)
    limit = 100 + raw[1] / 8
    expiry = query + (raw[3] % 30) * 1000000

    def crosses_limit(row: tuple[int, float, float]) -> bool:
        """Apply the independent bid/ask crossing definition."""
        if side == 1:
            return row[2] < limit if strict else row[2] <= limit
        return row[1] > limit if strict else row[1] >= limit

    expected = next((r for r in rows if query <= r[0] <= expiry and crosses_limit(r)), None)
    actual = book.first_limit_execution_event(
        side, limit, stamp, pd.Timestamp(expiry, unit="ns", tz="UTC"), require_trade_through=strict
    )
    assert (None if actual is None else (actual[0].value, *actual[1:])) == expected


def oracle_temporal_integrity(data: bytes) -> None:
    """Check purged fold geometry and higher-timeframe causal visibility."""
    from market_data.splits.walkforward import purged_walk_forward
    from market_data.transforms.align import align_timeframes

    a, b, c, d = data.ljust(4, b"\0")[:4]
    n, folds, purge, embargo = 100 + a, 1 + b % 6, c % 10, d % 8
    seen = list(purged_walk_forward(n, folds, 0.25, purge, embargo, label_horizon=3))
    assert len(seen) == folds
    prior_end = -1
    for fold in seen:
        train, test = fold.train_idx, fold.test_idx
        assert len(train) and len(test)
        assert int(test[0]) - int(train[-1]) - 1 >= purge + embargo + 3
        assert int(test[0]) > prior_end and int(test[-1]) < n
        prior_end = int(test[-1])
    minutes = (3, 5, 10)[a % 3]
    index = pd.date_range("2025-01-06", periods=(2 + b % 8) * minutes + 1, freq="min", tz="UTC")
    source = pd.DataFrame({"signal": range(len(index[::minutes]))}, index=index[::minutes])
    spine = pd.DataFrame({"bar": range(len(index))}, index=index)
    key = f"M{minutes}"
    result = align_timeframes(spine, {key: source})[key + "_signal"]
    for i, value in enumerate(result):
        assert pd.isna(value) if i < minutes else value == i // minutes - 1


def oracle_fill_and_drawdown(data: bytes) -> None:
    """Compare costs and drawdown with independently calculated finite inputs."""
    from evaluation.metrics.performance import max_drawdown
    from trading.execution.costs import CostModel

    raw = data.ljust(3, b"\0")[:40]
    model = CostModel(spread_points=raw[0] / 8, commission_per_lot=raw[1] / 8)
    bid, ask = model.bar_quote(100.0)
    assert bid == 100.0 and ask == 100.0 + raw[0] / 8
    assert model.fill_price(bid, ask, 1) == ask
    assert model.fill_price(bid, ask, -1) == bid
    assert model.total_cost(raw[2] / 8) == raw[1] * raw[2] / 64
    curve = [100.0 + v for v in raw]
    expected = max((max(curve[: i + 1]) - v) / max(curve[: i + 1]) for i, v in enumerate(curve))
    assert math.isclose(max_drawdown(curve), expected, abs_tol=1e-12)


def oracle_artifact_and_config(data: bytes) -> None:
    """Check artifact identity and fail-closed configuration parsing."""
    from artifacts.identity import artifact_id
    from configuration.configuration_loader import load_config

    raw = data[:32].hex()
    a = artifact_id("quality-fixture", {"a": raw, "b": 1})
    b = artifact_id("quality-fixture", {"b": 1, "a": raw})
    assert a == b
    expected = hashlib.sha256(('{"a":"' + raw + '","b":1}').encode()).hexdigest()
    assert a.digest == expected
    try:
        load_config(["ppo.__qrl_invalid_" + raw + "=1"])
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown optimizer config key was accepted")


PRODUCT_ORACLES: dict[str, Callable[[bytes], None]] = {
    "risk": oracle_risk_capacity,
    "actions": oracle_action_geometry,
    "ticks": oracle_tick_lookup,
    "chronology": oracle_temporal_integrity,
    "accounting": oracle_fill_and_drawdown,
    "provenance": oracle_artifact_and_config,
}

ORACLE_MODULES = {
    "risk": ["trading.account.limits", "trading.risk.budget"],
    "actions": ["decisioning.actions", "decisioning.trade_setup"],
    "ticks": ["market_data.loading.ticks"],
    "chronology": ["market_data.splits.walkforward", "market_data.transforms.align"],
    "accounting": ["trading.execution.costs", "evaluation.metrics.performance"],
    "provenance": ["artifacts.identity", "configuration.configuration_loader"],
}


def exercise_product_oracles(data: bytes, target: str) -> None:
    """Run one bounded oracle or every registered product oracle."""
    for name in PRODUCT_ORACLES if target == "all" else [target]:
        PRODUCT_ORACLES[name](data[:128])
