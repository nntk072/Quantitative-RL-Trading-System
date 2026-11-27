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
from market_data.loading.ticks import TickBook
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


def test_invalid_reference_quote_exposes_only_neutral_no_trade_candidate() -> None:
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _trade_setup_mask_for_step=lambda _index: setup_mask,
        _feature_row_at=lambda _index: {"atr_5": 1.0},
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        _bar_quote=lambda _bar: (100.1, 100.0),
    )

    observation = build_candidate_geometry_observation(env)

    features = observation["candidate_features"]
    mask = observation["candidate_mask"]
    assert mask.dtype == np.bool_
    assert mask[0]
    assert not mask[1:].any()
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    assert not features.any()


def test_required_reference_quote_uses_last_decision_bar_tick_and_refuses_empty_bar() -> None:
    bar_time = pd.Timestamp("2025-01-02 10:00", tz="UTC")
    tickbook = TickBook(
        np.asarray(
            [
                (bar_time + pd.Timedelta(seconds=5)).value,
                (bar_time + pd.Timedelta(seconds=40)).value,
                (bar_time + pd.Timedelta(minutes=1)).value,
            ],
            dtype=np.int64,
        ),
        np.asarray([99.9, 100.0, 101.0]),
        np.asarray([100.0, 100.1, 101.1]),
    )
    env = SimpleNamespace(
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        _bar_time=lambda _index: bar_time,
        _minutes_per_step=1.0,
        _tickbook=tickbook,
        tick_execution_required=True,
        _bar_quote=lambda _bar: pytest.fail("required tick quote must not use bar fallback"),
    )

    assert geometry._reference_quote(env, 0) == (100.0, 100.1)

    empty_env = SimpleNamespace(
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        _bar_time=lambda _index: bar_time,
        _minutes_per_step=1.0,
        _tickbook=TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([])),
        tick_execution_required=True,
        _bar_quote=lambda _bar: pytest.fail("required tick quote must not use bar fallback"),
    )
    assert geometry._reference_quote(empty_env, 0) is None


def test_last_bar_quote_lookup_preserves_half_open_bar_and_source_order() -> None:
    bar_start = pd.Timestamp("2025-01-02 10:00", tz="UTC")
    start_ns = bar_start.value
    end_ns = (bar_start + pd.Timedelta(minutes=1)).value
    tickbook = TickBook(
        np.asarray([start_ns - 1, start_ns, start_ns + 30, start_ns + 30, end_ns]),
        np.asarray([98.0, 99.0, 99.8, 99.9, 101.0]),
        np.asarray([98.1, 99.1, 99.9, 100.0, 101.1]),
    )

    assert tickbook.last_bar_quote_ns(bar_start, bar_minutes=1) == (
        start_ns + 30,
        99.9,
        100.0,
    )
    empty_tickbook = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))
    assert empty_tickbook.last_bar_quote_ns(bar_start, bar_minutes=1) is None


def test_optional_tick_reference_falls_back_only_to_a_valid_bar_quote() -> None:
    bar_time = pd.Timestamp("2025-01-02 10:00", tz="UTC")
    env = SimpleNamespace(
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        _bar_time=lambda _index: bar_time,
        _minutes_per_step=1.0,
        _tickbook=TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([])),
        tick_execution_required=False,
        _bar_quote=lambda _bar: (99.9, 100.1),
    )

    assert geometry._reference_quote(env, 0) == (99.9, 100.1)

    env._bar_quote = lambda _bar: (100.1, 100.0)
    assert geometry._reference_quote(env, 0) is None


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
    event.source_event_times_ns = (("source", decision_time.value - 120_000_000_000),)
    assert geometry._candidate_age_fraction(env, {}, 1, 0) == pytest.approx(0.6)
    event.source_event_times_ns = (("source", decision_time.value - 600_000_000_000),)
    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None
    event.status = "ambiguous"
    event.source_event_times_ns = (("source", decision_time.value),)
    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None


def test_candidate_geometry_hides_setup_when_no_executable_stop_and_target_pair_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _trade_setup_mask_for_step=lambda _index: setup_mask,
        _feature_row_at=lambda _index: {
            "atr_5": 1.0,
            "entry_idea_fvg_retest_M1_long": 1.0,
        },
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        cost_model=SimpleNamespace(point_size=0.01, commission_per_lot=0.0, point_value=1.0),
        contract_size=1.0,
        tick_fill_slippage_points=0.0,
        limit_order_max_ttl_bars=10,
        limit_order_max_offset_atr=2.0,
    )
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.0, 100.1))
    monkeypatch.setattr(geometry, "_source_zone", lambda *_args: (98.0, 99.0))
    monkeypatch.setattr(geometry, "_candidate_age_fraction", lambda *_args: 0.0)
    monkeypatch.setattr(geometry, "_session_remaining", lambda *_args: (10, 0.5))
    monkeypatch.setattr(geometry, "_geometry_distances", lambda *_args: None)

    observation = build_candidate_geometry_observation(env)

    assert observation["candidate_mask"][0]
    assert not observation["candidate_mask"][1:].any()
    assert not observation["candidate_features"].any()


def test_candidate_geometry_exposes_no_entry_after_the_session_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = TRADE_SETUP_CANDIDATES[1]
    side = "long" if candidate.direction == 1 else "short"
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _trade_setup_mask_for_step=lambda _index: setup_mask,
        _feature_row_at=lambda _index: {
            "atr_5": 1.0,
            f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}": 1.0,
        },
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        cost_model=SimpleNamespace(point_size=0.01, commission_per_lot=0.0, point_value=1.0),
        contract_size=1.0,
        tick_fill_slippage_points=0.0,
        limit_order_max_ttl_bars=10,
        limit_order_max_offset_atr=2.0,
    )
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.0, 100.1))
    monkeypatch.setattr(geometry, "_session_remaining", lambda *_args: None)

    observation = build_candidate_geometry_observation(env)

    assert observation["candidate_mask"][0]
    assert not observation["candidate_mask"][1:].any()
    assert not observation["candidate_features"].any()


@pytest.mark.parametrize("offset_case", ["non_passive", "beyond_configured_limit_offset"])
def test_candidate_geometry_never_admits_nonpassive_or_too_distant_limit_entry(
    monkeypatch: pytest.MonkeyPatch, offset_case: str
) -> None:
    candidate = TRADE_SETUP_CANDIDATES[1]
    direction = int(candidate.direction)
    midpoint = (
        (100.15 if direction == 1 else 99.85)
        if offset_case == "non_passive"
        else (97.5 if direction == 1 else 102.5)
    )
    zone = (midpoint - 0.5, midpoint + 0.5)
    signal_name = (
        f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_"
        f"{'long' if direction == 1 else 'short'}"
    )
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _trade_setup_mask_for_step=lambda _index: setup_mask,
        _feature_row_at=lambda _index: {"atr_5": 1.0, signal_name: 1.0},
        _bar_at=lambda _index: SimpleNamespace(close=100.0),
        cost_model=SimpleNamespace(point_size=0.01, commission_per_lot=0.0, point_value=1.0),
        contract_size=1.0,
        tick_fill_slippage_points=0.0,
        limit_order_max_ttl_bars=10,
        limit_order_max_offset_atr=2.0,
    )
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.0, 100.1))
    monkeypatch.setattr(geometry, "_source_zone", lambda *_args: zone)
    monkeypatch.setattr(geometry, "_candidate_age_fraction", lambda *_args: 0.0)
    monkeypatch.setattr(geometry, "_session_remaining", lambda *_args: (10, 0.5))
    monkeypatch.setattr(geometry, "_geometry_distances", lambda *_args: (1.0, 2.0, 1.0, 2.0))

    observation = build_candidate_geometry_observation(env)

    market_slot = candidate_geometry_slot(1, "market")
    limit_slot = candidate_geometry_slot(1, "limit")
    assert observation["candidate_mask"][0]
    assert observation["candidate_mask"][market_slot]
    assert not observation["candidate_mask"][limit_slot]
    assert not observation["candidate_features"][limit_slot].any()


def test_source_zone_uses_timeframe_band_or_latest_matching_po3_ifvg() -> None:
    sd_candidate = SimpleNamespace(idea="standard_deviation", setup_timeframe="M1")
    assert geometry._source_zone(
        {
            "standard_deviation_band_low": 98.0,
            "standard_deviation_band_high": 102.0,
        },
        sd_candidate,
    ) == (98.0, 102.0)
    assert (
        geometry._source_zone(
            {"standard_deviation_band_low": 103.0, "standard_deviation_band_high": 102.0},
            sd_candidate,
        )
        is None
    )

    po3_candidate = SimpleNamespace(idea="po3", setup_timeframe="M5")
    context = {
        "zones": [
            {
                "idea": "po3",
                "timeframe": "M5",
                "family": "ifvg",
                "start_time_ns": 2,
                "low": 99,
                "high": 101,
            },
            {
                "idea": "po3",
                "timeframe": "M5",
                "family": "fvg",
                "start_time_ns": 4,
                "low": 90,
                "high": 110,
            },
            {
                "idea": "po3",
                "timeframe": "M5",
                "family": "ifvg",
                "start_time_ns": 3,
                "low": 98,
                "high": 100,
            },
            {
                "idea": "po3",
                "timeframe": "H1",
                "family": "ifvg",
                "start_time_ns": 5,
                "low": 1,
                "high": 2,
            },
        ]
    }

    assert geometry._source_zone({}, po3_candidate, context) == (98.0, 100.0)


def test_session_remaining_uses_regular_close_when_no_special_schedule_exists() -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-11-26 17:30", tz="Europe/Helsinki"),
        _minutes_per_step=1.0,
        _session_start="08:30",
        _session_end="15:00",
        _session_timezone="America/Chicago",
        _source_clock_model="europe_helsinki",
        _scheduled_session_closes={},
    )

    remaining = geometry._session_remaining(env, 0)

    assert isinstance(remaining, tuple)
    bars, fraction = remaining
    assert bars == 329
    assert fraction == pytest.approx(329.0 / 390.0)


def test_session_remaining_converts_special_close_from_source_clock() -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-11-28 17:00", tz="Europe/Helsinki"),
        _minutes_per_step=1.0,
        _session_start="08:30",
        _session_end="15:00",
        _session_timezone="America/Chicago",
        _source_clock_model="europe_helsinki",
        _scheduled_session_closes={"2025-11-28": "20:15"},
    )

    remaining = geometry._session_remaining(env, 0)

    assert isinstance(remaining, tuple)
    bars, fraction = remaining
    assert bars == 194
    assert fraction == pytest.approx(194.0 / 225.0)
