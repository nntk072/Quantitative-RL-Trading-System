from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.strategies import DistributionStrategy, PO3IFVGStrategy


def test_distribution_candidate_modes_enforce_confirmations_and_age() -> None:
    first = DistributionStrategy(entry_mode="confirmed_first_eligible")
    row = pd.Series(
        {
            "po3_distribution": 1,
            "po3_distribution_direction": 1,
            "htf_day_bias": 1,
            "po3_ifvg_confirmed": 0,
            "ifvg_bull_confirmed": 1,
        }
    )
    assert first.context_direction(row) == 1
    row["ifvg_bull_confirmed"] = 0
    assert first.context_direction(row) == 0

    retest = DistributionStrategy(entry_mode="confirmed_retest", candidate_max_age_bars=3)
    row["po3_distribution_after_ifvg"] = 1
    row["ifvg_retest_bull"] = 1
    row["ifvg_bull_age"] = 2
    assert retest.context_direction(row) == 1
    row["ifvg_bull_age"] = 4
    assert retest.context_direction(row) == 0


def test_distribution_gates_session_price_and_returns_structural_candidates() -> None:
    strategy = DistributionStrategy(enforce_gate=False, previous_session_pd_gate=True)
    row = pd.Series(
        {
            "previous_session_midpoint": 100.0,
            "decision_close": 99.0,
            "sweep_low_level": 95.0,
            "sweep_high_level": 105.0,
            "prev_day_high": np.nan,
            "prev_day_low": 90.0,
        }
    )
    assert strategy.validate_entry(direction=1, row=row)
    assert not strategy.validate_entry(direction=-1, row=row)
    assert strategy.entry_rejection_reason(direction=-1, row=row) == "discount_block"
    assert strategy.sl_reference(direction=1, row=row) == 95.0
    assert strategy.sl_reference(direction=-1, row=pd.Series()) is None
    assert np.isnan(strategy.target_candidates(direction=1, row=row)["previous_day_high_low"])
    assert strategy.target_candidates(direction=-1, row=row)["previous_day_high_low"] == 90.0
    row["decision_close"] = np.nan
    assert strategy.entry_rejection_reason(direction=1, row=row) == "missing_previous_session"
    assert not strategy.previous_session_pd_eligible(row, direction=1)


def test_distribution_stop_ladder_orders_live_zones_and_nonlegacy_ifvg_edges() -> None:
    strategy = DistributionStrategy(entry_mode="confirmed_retest")
    row = pd.Series(
        {
            "last_swing_low": 90.0,
            "sweep_low_level": np.nan,
            "ifvg_bull_active": 1.0,
            "ifvg_bull_low": 98.0,
            "ifvg_bull_origin": 99.0,
            "M5_ifvg_bull_active": 1.0,
            "M5_ifvg_bull_low": 97.0,
            "M5_ifvg_bull_origin": 97.5,
            "H1_ifvg_bull_active": 1.0,
            "H1_ifvg_bull_low": 96.0,
            "po3_ifvg_low": 95.0,
            "po3_ifvg_through_zone_extreme": 94.0,
        }
    )
    strategy.bind_columns(row.index)

    names = [name for name, _ in strategy.sl_candidates(direction=1, row=row)]

    assert names[:4] == [
        "last_swing_low",
        "ifvg_bull_low",
        "ifvg_bull_origin",
        "M5_ifvg_bull_low",
    ]
    assert names[-2:] == ["ifvg_far_edge", "ifvg_through_zone_extreme"]
    assert strategy.sl_candidates(direction=0, row=row) == []


def test_po3_strategy_requires_config_consistent_retest_mode_and_reads_live_gaps() -> None:
    with pytest.raises(ValueError, match="conflicts with"):
        PO3IFVGStrategy(entry_mode="confirmed_retest", require_price_retest=False)
    strategy = PO3IFVGStrategy(require_price_retest=True, enforce_gate=False)
    assert not strategy.entry_gap(pd.Series({"ifvg_bull_active": 1.0}), 1)
    assert strategy.entry_gap(pd.Series({"M5_ifvg_retest_bull": 1.0}), 1)
    assert strategy.entry_gap(pd.Series({"fvg_retest_bear": 1.0}), -1)
    assert not strategy.entry_gap(pd.Series({"fvg_retest_bull": 1.0}), 0)


def test_po3_retest_candidate_age_and_structural_targets_are_directional() -> None:
    strategy = PO3IFVGStrategy(entry_mode="confirmed_retest", enforce_gate=False)
    row = pd.Series(
        {
            "po3_distribution_after_ifvg": 1.0,
            "po3_distribution_direction": 1.0,
            "ifvg_retest_bull": 1.0,
            "M5_ifvg_bull_age": 3.0,
            "sweep_high_level": 110.0,
            "sweep_low_level": 90.0,
            "po3_manipulation_high": 110.0,
            "prev_day_high": 112.0,
            "prev_day_low": 88.0,
        }
    )
    assert strategy._candidate_age_ok(row, "bull")
    assert strategy.context_direction(row) == 1
    assert strategy.sl_reference(direction=-1, row=row) == 110.0
    assert strategy.target_candidates(direction=1, row=row) == {
        "buyside_liquidity": 110.0,
        "previous_day_high_low": 112.0,
    }
    assert strategy.target_candidates(direction=-1, row=row)["previous_day_high_low"] == 88.0


def test_po3_rejects_unknown_entry_modes_and_nonpositive_candidate_age() -> None:
    with pytest.raises(ValueError, match="unsupported PO3/IFVG entry mode"):
        PO3IFVGStrategy(entry_mode="unconfirmed_first")
    with pytest.raises(ValueError, match="candidate_max_age_bars must be positive"):
        PO3IFVGStrategy(candidate_max_age_bars=0)


def test_po3_live_gap_and_liquidity_checks_are_side_specific() -> None:
    strategy = PO3IFVGStrategy(require_price_retest=False, enforce_gate=True)
    row = pd.Series(
        {
            "ifvg_bull_active": 1.0,
            "ifvg_bear_active": 0.0,
            "sweep_low": 1.0,
            "sweep_high": 0.0,
            "manipulation_low_distance_atr": 1.1,
            "manipulation_high_distance_atr": 1.1,
            "ob_bull_retest": 0.0,
            "ob_bear_retest": 0.0,
            "standard_deviation_entry_long": 0.0,
            "standard_deviation_entry_short": 0.0,
        }
    )

    assert strategy.entry_gap(row, 1)
    assert not strategy.entry_gap(row, -1)
    assert not strategy.entry_gap(row, 0)
    assert strategy.entry_liquidity(row, 1)
    assert not strategy.entry_liquidity(row, -1)
    assert not strategy.entry_liquidity(row, 0)
    assert strategy.validate_entry(direction=1, row=row)
    assert not strategy.validate_entry(direction=-1, row=row)
    assert not strategy.validate_entry(direction=0, row=row)

    row["ifvg_bull_active"] = 0.0
    row["ifvg_bear_active"] = 1.0
    row["sweep_low"] = 0.0
    row["sweep_high"] = 1.0
    assert strategy.entry_gap(row, -1)
    assert strategy.entry_liquidity(row, -1)
    assert strategy.validate_entry(direction=-1, row=row)
    assert not strategy.validate_entry(direction=1, row=row)


def test_po3_confirmed_retest_requires_a_later_fresh_matching_retest() -> None:
    strategy = PO3IFVGStrategy(entry_mode="confirmed_retest", candidate_max_age_bars=3)
    same_bar = pd.Series(
        {
            "po3_ifvg_confirmed": 1.0,
            "po3_distribution_after_ifvg": 1.0,
            "po3_distribution_direction": 1.0,
            "ifvg_retest_bull": 1.0,
            "M5_ifvg_bull_age": 2.0,
        }
    )
    assert strategy.context_direction(same_bar) == 0

    later_retest = same_bar.astype(object).copy()
    later_retest["po3_ifvg_confirmed"] = 0.0
    assert strategy.context_direction(later_retest) == 1
    assert not strategy._candidate_age_ok(later_retest.drop("M5_ifvg_bull_age"), "bull")
    later_retest["M5_ifvg_bull_age"] = "invalid"
    later_retest["H1_ifvg_bull_age"] = 4.0
    assert not strategy._candidate_age_ok(later_retest, "bull")
    assert strategy.context_direction(later_retest) == 0
    later_retest["H1_ifvg_bull_age"] = 2.0
    later_retest["ifvg_retest_bear"] = 1.0
    later_retest["H1_ifvg_bear_age"] = 2.0
    assert strategy.context_direction(later_retest) == 0
    later_retest["po3_distribution_direction"] = 0.0
    assert strategy.context_direction(later_retest) == 0


def test_po3_multitimeframe_direction_and_stop_ladder_require_live_gap_evidence() -> None:
    legacy = PO3IFVGStrategy(enforce_gate=False)
    strategy = PO3IFVGStrategy(entry_mode="confirmed_retest", enforce_gate=False)
    row = pd.Series(
        {
            "po3_distribution_after_ifvg": 1.0,
            "po3_distribution_direction": "unavailable",
            "M5_po3_distribution_direction": -1.0,
            "ifvg_bear_active": 1.0,
            "M5_ifvg_bear_active": 1.0,
            "M5_ifvg_bear_high": 105.0,
            "M5_ifvg_bear_origin": 106.0,
            "H1_ifvg_bear_high": 110.0,
            "H1_ifvg_bear_origin": 111.0,
            "H1_ifvg_bear_active": 0.0,
            "po3_ifvg_high": 108.0,
            "po3_ifvg_through_zone_extreme": 112.0,
        }
    )

    assert legacy.context_direction(row) == -1
    stops = strategy.sl_candidates(direction=-1, row=row)
    assert stops == [
        ("M5_ifvg_bear_high", 105.0),
        ("M5_ifvg_bear_origin", 106.0),
        ("ifvg_far_edge", 108.0),
        ("ifvg_through_zone_extreme", 112.0),
    ]
    assert strategy.sl_candidates(direction=0, row=row) == []
