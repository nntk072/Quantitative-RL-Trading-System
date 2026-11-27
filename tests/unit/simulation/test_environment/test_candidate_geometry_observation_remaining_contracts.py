from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from decisioning.trade_setup import TRADE_SETUP_CANDIDATES, TRADE_SETUP_CATEGORY_COUNT
from simulation.environment import candidate_geometry_observation as geometry


def _candidate_env(**overrides: Any) -> SimpleNamespace:
    candidate = TRADE_SETUP_CANDIDATES[1]
    side = "long" if candidate.direction == 1 else "short"
    setup_mask = np.zeros(TRADE_SETUP_CATEGORY_COUNT, dtype=np.float32)
    setup_mask[1] = 1.0
    values: dict[str, Any] = {
        "candidate_geometry_actions": True,
        "step_idx": 0,
        "_n_bars": 1,
        "_trade_setup_mask_for_step": lambda _index: setup_mask,
        "_feature_row_at": lambda _index: {
            "atr_5": 1.0,
            f"entry_idea_{candidate.idea}_{candidate.setup_timeframe}_{side}": 1.0,
        },
        "_bar_at": lambda _index: SimpleNamespace(close=100.0),
        "cost_model": SimpleNamespace(point_size=0.01, commission_per_lot=0.0, point_value=1.0),
        "contract_size": 1.0,
        "tick_fill_slippage_points": 0.0,
        "limit_order_max_ttl_bars": 10,
        "limit_order_max_offset_atr": 2.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_candidate_geometry_explicit_step_index_outside_data_stays_neutral() -> None:
    env = SimpleNamespace(
        candidate_geometry_actions=True,
        step_idx=0,
        _n_bars=1,
        _feature_row_at=lambda _index: pytest.fail("out-of-range step must not read features"),
    )

    observation = geometry.build_candidate_geometry_observation(env, step_idx=1)

    assert observation["candidate_mask"].sum() == 1
    assert observation["candidate_mask"][0]
    assert not observation["candidate_features"].any()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tick_fill_slippage_points", -0.01),
        ("tick_fill_slippage_points", "invalid"),
        ("contract_size", 0.0),
        ("contract_size", None),
    ],
)
def test_candidate_geometry_fails_closed_on_invalid_execution_cost_inputs(
    monkeypatch: pytest.MonkeyPatch, field: str, value: Any
) -> None:
    env = _candidate_env(**{field: value})
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.0, 100.1))

    observation = geometry.build_candidate_geometry_observation(env)

    assert observation["candidate_mask"].tolist() == [True] + [False] * (
        len(observation["candidate_mask"]) - 1
    )
    assert not observation["candidate_features"].any()


def test_candidate_geometry_rejects_crossed_quote_before_cost_calculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _candidate_env()
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.1, 100.0))

    observation = geometry.build_candidate_geometry_observation(env)

    assert observation["candidate_mask"].sum() == 1
    assert not observation["candidate_features"].any()


def test_source_zone_requires_a_valid_matching_idea_and_timeframe() -> None:
    candidate = SimpleNamespace(idea="fvg_retest", setup_timeframe="M5", direction=1)

    assert (
        geometry._source_zone(
            {},
            candidate,
            {"zones": [{"idea": "fvg_retest", "timeframe": "H1", "low": 99, "high": 100}]},
        )
        is None
    )
    assert (
        geometry._source_zone(
            {},
            candidate,
            {"zones": [{"idea": "fvg_retest", "timeframe": "M5", "low": "bad", "high": 100}]},
        )
        is None
    )


def test_session_remaining_fails_closed_when_close_is_missing_invalid_or_elapsed() -> None:
    now = pd.Timestamp("2025-01-02 10:00")
    base = {"_bar_time": lambda _index: now, "_minutes_per_step": 1.0, "_session_start": "09:00"}

    assert geometry._session_remaining(SimpleNamespace(**base), 0) is None
    assert (
        geometry._session_remaining(SimpleNamespace(**base, _session_end="not-a-time"), 0) is None
    )
    assert (
        geometry._session_remaining(SimpleNamespace(**{**base, "_session_end": "10:01"}), 0) is None
    )


def test_session_remaining_interprets_native_scheduled_close_without_timezone() -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-01-02 10:00"),
        _minutes_per_step=1.0,
        _session_start="09:00",
        _scheduled_session_closes={"2025-01-02": "16:00"},
    )

    remaining = geometry._session_remaining(env, 0)

    assert remaining is not None
    bars, fraction = remaining
    assert bars == 359
    assert fraction == pytest.approx(359.0 / 420.0)


def test_session_remaining_rebases_legacy_ftmo_clock_to_new_york_session() -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-01-02 17:00", tz="Europe/Helsinki"),
        _minutes_per_step=1.0,
        _session_start="09:30",
        _session_timezone="America/New_York",
        _source_clock_model="ftmo_mt5_us_dst",
        _scheduled_session_closes={"2025-01-02": "23:00"},
    )

    remaining = geometry._session_remaining(env, 0)

    assert remaining is not None
    bars, fraction = remaining
    assert bars == 359
    assert fraction == pytest.approx(359.0 / 390.0)


def test_legacy_ftmo_clock_without_timezone_fails_closed() -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-01-02 10:00"),
        _minutes_per_step=1.0,
        _session_start="09:30",
        _session_end="16:00",
        _source_clock_model="ftmo_mt5_us_dst",
    )

    assert geometry._session_remaining(env, 0) is None


def test_candidate_age_requires_an_identified_source_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = SimpleNamespace(
        _bar_time=lambda _index: pd.Timestamp("2025-01-02 10:00", tz="UTC"),
        _minutes_per_step=1.0,
    )
    monkeypatch.setattr(geometry, "trade_setup_candidate_event_identities", lambda *_args: [])

    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None

    event = SimpleNamespace(status="identified", source_event_times_ns=())
    monkeypatch.setattr(geometry, "trade_setup_candidate_event_identities", lambda *_args: [event])
    assert geometry._candidate_age_fraction(env, {}, 1, 0) is None


@pytest.mark.parametrize(
    ("sl_menu", "tp_menu", "expected"),
    [
        ([("tight", 98.0), ("wide", 97.0)], [("tp", 102.0), ("far", 104.0)], (2.0, 3.0, 2.0, 4.0)),
        ([], [("tp", 102.0)], None),
        ([("zero", 100.0)], [("tp", 102.0)], None),
    ],
)
def test_geometry_distance_adapter_requires_executable_positive_stop_and_target_ranges(
    monkeypatch: pytest.MonkeyPatch,
    sl_menu: list[tuple[str, float]],
    tp_menu: list[tuple[str, float]],
    expected: tuple[float, float, float, float] | None,
) -> None:
    candidate = TRADE_SETUP_CANDIDATES[1]
    env = SimpleNamespace(
        strategy=object(),
        _min_sl_distance=lambda _row: 0.2,
        sl_buffer_pts=0.1,
        _max_tp_here=lambda: 10.0,
        rr_ratio_range=(1.0, 4.0),
        _target_timeframes=("M5",),
        cost_model=SimpleNamespace(point_size=0.01),
    )
    calls: list[dict[str, Any]] = []

    def fake_place_strategy_order(strategy: Any, **kwargs: Any) -> SimpleNamespace:
        calls.append({"strategy": strategy, **kwargs})
        return SimpleNamespace(sl_menu=sl_menu, tp_menu=tp_menu)

    monkeypatch.setattr(geometry, "place_strategy_order", fake_place_strategy_order)

    distances = geometry._geometry_distances(env, {"atr": 1.0}, candidate, 100.0, 1.0)

    assert distances == expected
    assert calls[0]["strategy"] is env.strategy
    assert calls[0]["trade_setup"] is candidate
    assert calls[0]["allow_multi_tp"] is False
    assert calls[0]["allow_simplex"] is True


def test_limit_candidate_is_omitted_when_price_rounding_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _candidate_env()
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (100.0, 100.1))
    monkeypatch.setattr(geometry, "_source_zone", lambda *_args: (98.0, 99.0))
    monkeypatch.setattr(geometry, "_candidate_age_fraction", lambda *_args: 0.0)
    monkeypatch.setattr(geometry, "_session_remaining", lambda *_args: (10, 0.5))
    monkeypatch.setattr(geometry, "_geometry_distances", lambda *_args: (1.0, 2.0, 1.0, 2.0))
    monkeypatch.setattr(
        geometry,
        "limit_price_from_atr_offset",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("invalid price increment")),
    )

    observation = geometry.build_candidate_geometry_observation(env)

    assert observation["candidate_mask"][0]
    assert observation["candidate_mask"][1]
    assert not observation["candidate_mask"][2]
    assert not observation["candidate_features"][2].any()


def test_limit_candidate_stays_inside_source_zone_after_price_grid_rounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _candidate_env(
        cost_model=SimpleNamespace(point_size=0.1, commission_per_lot=0.0, point_value=1.0)
    )
    monkeypatch.setattr(geometry, "_reference_quote", lambda *_args: (99.9, 100.0))
    monkeypatch.setattr(geometry, "_source_zone", lambda *_args: (99.02, 99.08))
    monkeypatch.setattr(geometry, "_candidate_age_fraction", lambda *_args: 0.0)
    monkeypatch.setattr(geometry, "_session_remaining", lambda *_args: (10, 0.5))
    monkeypatch.setattr(geometry, "_geometry_distances", lambda *_args: (1.0, 2.0, 1.0, 2.0))

    observation = geometry.build_candidate_geometry_observation(env)

    assert observation["candidate_mask"][1]
    assert not observation["candidate_mask"][2]
    assert not observation["candidate_features"][2].any()
