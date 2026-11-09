from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import (
    CANDIDATE_GEOMETRY_FEATURE_NAMES,
    TRADE_SETUP_CANDIDATES,
    TRADE_SETUP_CATEGORY_COUNT,
    candidate_geometry_slot,
    candidate_geometry_slot_count,
)
from simulation.environment import candidate_geometry_observation as geometry
from simulation.environment.candidate_geometry_observation import (
    build_candidate_geometry_observation,
)


def test_disabled_candidate_geometry_observation_is_fixed_width_no_trade_only() -> None:
    env = SimpleNamespace(step_idx=0, candidate_geometry_actions=False)

    observation = build_candidate_geometry_observation(env)

    count = candidate_geometry_slot_count()
    assert observation["candidate_ids"].shape == (count,)
    assert observation["candidate_ids"].dtype == np.int64
    assert observation["candidate_ids"][0] == 0
    assert observation["candidate_ids"][1:5].tolist() == [1, 1, 2, 2]
    assert observation["candidate_features"].shape == (
        count,
        len(CANDIDATE_GEOMETRY_FEATURE_NAMES),
    )
    assert observation["candidate_features"].dtype == np.float32
    assert observation["candidate_mask"].shape == (count,)
    assert observation["candidate_mask"].dtype == np.bool_
    assert observation["candidate_mask"][0]
    assert not observation["candidate_mask"][1:].any()


def test_candidate_observation_emits_causal_geometry_cost_and_session_features(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = TRADE_SETUP_CANDIDATES[1]
    direction = int(candidate.direction)
    zone = (98.0, 99.0) if direction == 1 else (101.0, 102.0)
    signal_name = (
        f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_"
        f"{'long' if direction == 1 else 'short'}"
    )
    row = {"atr_5": 1.0, signal_name: 1.0}
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _scheduled_session_closes={"2025-01-02": "16:00"},
        _session_start="09:00",
        _bar_time=lambda _index: pd.Timestamp("2025-01-02 10:00", tz="America/New_York"),
        _minutes_per_step=1.0,
        _trade_setup_mask_for_step=lambda _index: setup_mask,
        _feature_row_at=lambda _index: row,
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        cost_model=SimpleNamespace(point_size=0.01, commission_per_lot=2.0, point_value=1.0),
        contract_size=10.0,
        tick_fill_slippage_points=0.1,
        limit_order_max_ttl_bars=60,
        limit_order_max_offset_atr=2.0,
    )
    monkeypatch.setattr(geometry, "_reference_quote", lambda _env, _index: (100.0, 100.1))
    monkeypatch.setattr(geometry, "_source_zone", lambda *_args: zone)
    monkeypatch.setattr(geometry, "_candidate_age_fraction", lambda *_args: 0.25)
    monkeypatch.setattr(geometry, "_geometry_distances", lambda *_args: (1.0, 2.0, 1.5, 3.0))

    observation = build_candidate_geometry_observation(env)

    market_slot = candidate_geometry_slot(1, "market")
    limit_slot = candidate_geometry_slot(1, "limit")
    assert observation["candidate_mask"].dtype == np.bool_
    assert observation["candidate_mask"][0]
    assert observation["candidate_mask"][market_slot]
    assert observation["candidate_mask"][limit_slot]
    assert not observation["candidate_mask"][3:].any()
    feature = observation["candidate_features"]
    assert feature[
        market_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("round_trip_cost_atr")
    ] == pytest.approx(0.7)
    assert feature[
        limit_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("source_zone_width_atr")
    ] == pytest.approx(1.0)
    assert feature[
        limit_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("candidate_age_fraction")
    ] == pytest.approx(0.25)
    assert feature[
        limit_slot, CANDIDATE_GEOMETRY_FEATURE_NAMES.index("session_close_time_fraction")
    ] == pytest.approx(359.0 / 420.0)


def test_candidate_age_rejects_future_and_expired_source_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision_time = pd.Timestamp("2025-01-02 10:00", tz="UTC")
    env = SimpleNamespace(
        _bar_time=lambda _index: decision_time,
        _minutes_per_step=1.0,
        candidate_max_age_bars=5,
    )
    event = SimpleNamespace(status="identified", source_event_times_ns=())
    monkeypatch.setattr(geometry, "trade_setup_candidate_event_identities", lambda *_args: [event])

    event.source_event_times_ns = (("source", decision_time.value + 120_000_000_000),)
    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None
    event.source_event_times_ns = (("source", decision_time.value - 600_000_000_000),)
    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None
