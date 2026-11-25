"""Parity of the native Position and notional with hand calculations (NATIVE-DOMAIN).

The expected values are the same hand calculations as the Rust unit tests in
native/domain/src/position.rs, with a tick value of 100 cents per tick per lot.
"""

import pytest

qrl_native = pytest.importorskip("qrl_native")

TICK_VALUE = 100


def test_notional_matches_hand_calculation() -> None:
    # 1000 ticks * 2 lots * 100 cents = 200000 cents (2000.00)
    assert qrl_native.notional_cents(1000, 2, TICK_VALUE) == 200_000


def test_notional_overflow_raises_instead_of_wrapping() -> None:
    with pytest.raises(OverflowError):
        qrl_native.notional_cents(2**63 - 1, 2, 1)


def test_notional_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError):
        qrl_native.notional_cents(1000, 0, TICK_VALUE)
    with pytest.raises(ValueError):
        qrl_native.notional_cents(0, 1, TICK_VALUE)
    with pytest.raises(ValueError):
        qrl_native.notional_cents(1000, 1, 0)


def test_increase_averages_by_hand_and_realizes_nothing() -> None:
    # Long 2 at 1000, then 1 at 1010: average (2*1000 + 1010) / 3 = 1003.33 -> 1003 ticks.
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 2, 0, TICK_VALUE)
    position.apply_fill(True, 1010, 1, 0, TICK_VALUE)
    assert position.lots == 3
    assert position.average_entry_ticks == 1003
    assert position.realized_pnl_cents == 0


def test_reduce_round_trip_nets_zero_by_hand() -> None:
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 2, 0, TICK_VALUE)
    position.apply_fill(True, 1010, 1, 0, TICK_VALUE)
    # Sell 1 at 1010 against 1003.33: 6.67 ticks = 666.67 cents -> 667.
    position.apply_fill(False, 1010, 1, 0, TICK_VALUE)
    assert position.lots == 2
    assert position.realized_pnl_cents == 667
    # Sell 2 at 1000: -6.67 ticks = -666.67 cents -> -667. Net 0, flat.
    position.apply_fill(False, 1000, 2, 0, TICK_VALUE)
    assert position.lots == 0
    assert position.average_entry_ticks is None
    assert position.realized_pnl_cents == 0


def test_crossing_zero_opens_remainder_at_fill_price() -> None:
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 1, 0, TICK_VALUE)
    position.apply_fill(False, 1010, 3, 0, TICK_VALUE)
    assert position.lots == -2
    assert position.average_entry_ticks == 1010
    assert position.realized_pnl_cents == 1000


def test_fees_are_kept_separate_from_realized_pnl() -> None:
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 1, 250, TICK_VALUE)
    position.apply_fill(True, 1000, 1, 250, TICK_VALUE)
    assert position.fees_cents == 500
    assert position.realized_pnl_cents == 0


def test_refused_fill_leaves_position_unchanged() -> None:
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 1, 0, TICK_VALUE)
    with pytest.raises(ValueError):
        position.apply_fill(True, 1000, 0, 0, TICK_VALUE)  # nonpositive quantity
    with pytest.raises(ValueError):
        position.apply_fill(True, 1000, 1, -1, TICK_VALUE)  # negative fee
    assert position.lots == 1
    assert position.fees_cents == 0


def test_overflowing_fill_raises_and_position_is_unchanged() -> None:
    position = qrl_native.Position()
    with pytest.raises(OverflowError):
        position.apply_fill(True, 2**63 - 1, 1, 0, TICK_VALUE)
    assert position.lots == 0
    assert position.average_entry_ticks is None


def test_changed_tick_value_is_refused_and_position_unchanged() -> None:
    # The tick value is fixed by the first fill; a different value would change the cost basis.
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 1, 0, TICK_VALUE)
    with pytest.raises(ValueError):
        position.apply_fill(True, 1000, 1, 0, 50)
    assert position.lots == 1
    assert position.realized_pnl_cents == 0


def test_round_trip_at_a_loss_realizes_by_hand() -> None:
    # Long 1 at 1000, sell 1 at 990: exit 99000 - basis 100000 = -1000 cents.
    position = qrl_native.Position()
    position.apply_fill(True, 1000, 1, 0, TICK_VALUE)
    position.apply_fill(False, 990, 1, 0, TICK_VALUE)
    assert position.lots == 0
    assert position.realized_pnl_cents == -1000
