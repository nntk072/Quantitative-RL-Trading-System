"""Native parity with the SEMANTIC-ORACLE fixture expectations (cents scale).

The fixture file stores USD. Here the same hand-calculated cases are expressed in cents
(USD x 100), matching the native API. Fractional lots are not representable in the native
API (lots are integers), so fixture AC-B (0.4-lot partial closes) is not replayed here; that
gap is recorded in the ledger entry. The run must report zero skips: a skip would mean the
extension is missing, which is a failure of the evidence.
"""

from __future__ import annotations

import pytest

qrl_native = pytest.importorskip("qrl_native")


def test_daily_loss_matches_fixture_ac_e() -> None:
    # AC-E: session 10000, equity 9400 -> loss 600 USD = 60000 cents.
    assert qrl_native.canonical_daily_loss_cents(1_000_000, 940_000) == 60_000


def test_daily_loss_is_zero_on_a_gain() -> None:
    # AC-A: equity above the session start is floored at zero.
    assert qrl_native.canonical_daily_loss_cents(973_600, 1_000_000) == 0


def test_daily_floor_matches_fixture_ac_e() -> None:
    # AC-E: 10000 - 500 = 9500 USD.
    assert qrl_native.daily_floor_cents(1_000_000, 50_000) == 950_000


def test_remaining_capacity_is_zero_once_breached_matches_ac_e() -> None:
    # AC-E: floor 9500, equity 9400 -> remaining 0.
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 940_000, 50_000) == 0


def test_remaining_capacity_boundary_matches_ac_f() -> None:
    # AC-F: equity exactly at the floor (9500) gives 0; one cent above gives 1 cent.
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 950_000, 50_000) == 0
    assert qrl_native.remaining_daily_capacity_cents(1_000_000, 950_001, 50_000) == 1


def test_session_start_capacity_matches_ac_a() -> None:
    # AC-A after the gap-stop: session 9736, limit 500 -> floor 9236, remaining 500 at equity 9736.
    assert qrl_native.daily_floor_cents(973_600, 50_000) == 923_600
    assert qrl_native.remaining_daily_capacity_cents(973_600, 973_600, 50_000) == 50_000


def test_round_trip_gross_and_fees_match_fixture_ac_c_at_integer_lots() -> None:
    # One lot buy at 100.60 (10060 ticks of 0.01), sell at 101.00 (10100 ticks).
    # Each side costs 100 cents (commission 1 USD per lot). cents per tick per lot = 100
    # (contract 100 x point 0.01 x 100 cents per USD). Gross = 40 ticks x 100 = 4000 cents.
    position = qrl_native.Position()
    position.apply_fill(True, 10_060, 1, 100, 100)
    position.apply_fill(False, 10_100, 1, 100, 100)
    assert position.lots == 0
    assert position.fees_cents == 200
    assert position.realized_pnl_cents == 4_000


def test_refused_fill_leaves_the_position_unchanged() -> None:
    position = qrl_native.Position()
    position.apply_fill(True, 10_060, 1, 0, 100)
    with pytest.raises(Exception):  # noqa: B017 - the binding maps every domain error to a Python error
        position.apply_fill(True, 0, 1, 0, 100)  # zero price is refused
    assert position.lots == 1
