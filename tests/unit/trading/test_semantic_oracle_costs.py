"""Hand-calculated semantic oracle for transaction costs (SEMANTIC-ORACLE, costs).

Scope is what ``trading/execution/costs.py`` defines: commission, bar spread, fill side,
the slippage parameter, and the spread and slippage cost of ``TradingCostModel``. The
module defines no rounding, lot or tick step, and no fill ordering, so those are not
covered here. Every expected value is worked out in the comment above its assertion and
does not reuse the production formula.

Former candidate defect C1 (invalid fill side) is fixed and asserted as a positive case.
The slippage candidate (C2) remains a strict xfail; see semantic_contracts.md section 5.
"""

from __future__ import annotations

import pytest

from trading.execution.costs import CostModel, TradingCostModel

# --- commission (total_cost = commission_per_lot * lots) ------------------------------


def test_commission_is_rate_times_lots() -> None:
    # 2.5 per lot * 4.0 lots = 10.0; the direction argument does not change the fee.
    model = CostModel(commission_per_lot=2.5)
    assert model.total_cost(lots=4.0) == pytest.approx(10.0)
    assert model.total_cost(lots=4.0, direction=-1) == pytest.approx(10.0)


def test_commission_rate_cannot_be_negative_adverse() -> None:
    # A negative fee would be a silent rebate, so construction must reject it.
    with pytest.raises(ValueError, match="commission_per_lot must be finite and non-negative"):
        CostModel(commission_per_lot=-2.5)


def test_no_position_pays_no_commission_adverse() -> None:
    # 2.5 * 0.0 lots = 0.0; a no-trade bar must not carry a phantom fee.
    assert CostModel(commission_per_lot=2.5).total_cost(lots=0.0) == 0.0


# --- bar spread (bar_quote: bid = close, ask = close + spread) ------------------------


def test_bar_quote_uses_default_then_per_bar_spread() -> None:
    # Default: ask = 20000.0 + 0.6 = 20000.6. Explicit bar_spread 1.5: ask = 20000.0 + 1.5 = 20001.5.
    model = CostModel(spread_points=0.6)
    bid, ask = model.bar_quote(close=20000.0)
    assert bid == pytest.approx(20000.0)
    assert ask == pytest.approx(20000.6)
    bid, ask = model.bar_quote(close=20000.0, bar_spread=1.5)
    assert bid == pytest.approx(20000.0)
    assert ask == pytest.approx(20001.5)


def test_explicit_zero_bar_spread_is_honored_adverse() -> None:
    # bar_spread 0.0 means a zero-spread bar: ask = 20000.0 + 0.0 = 20000.0.
    # It must not be replaced by the default spread_points 0.6 (a falsy-value bug would do that).
    bid, ask = CostModel(spread_points=0.6).bar_quote(close=20000.0, bar_spread=0.0)
    assert bid == pytest.approx(20000.0)
    assert ask == pytest.approx(20000.0)


# --- fill side (long buys at ask, short sells at bid) ---------------------------------


@pytest.mark.parametrize(
    ("direction", "expected_fill"),
    [
        # bid 99.5, ask 100.5: long pays the ask 100.5, short receives the bid 99.5.
        (1, 100.5),
        (-1, 99.5),
    ],
)
def test_fill_side_is_ask_for_long_and_bid_for_short(direction: int, expected_fill: float) -> None:
    assert CostModel().fill_price(bid=99.5, ask=100.5, direction=direction) == pytest.approx(
        expected_fill
    )


def test_invalid_fill_direction_is_rejected_adverse() -> None:
    # Expected by the docstring contract: direction must be +1 or -1, so 0 must raise.
    with pytest.raises(ValueError):
        CostModel().fill_price(bid=99.5, ask=100.5, direction=0)


# --- slippage parameter -----------------------------------------------------------------


def test_zero_slippage_leaves_bar_fill_at_quote_side() -> None:
    # slippage_points 0.0 adds nothing: long fill = ask 100.5, short fill = bid 99.5.
    model = CostModel(slippage_points=0.0)
    assert model.fill_price(bid=99.5, ask=100.5, direction=1) == pytest.approx(100.5)
    assert model.fill_price(bid=99.5, ask=100.5, direction=-1) == pytest.approx(99.5)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CANDIDATE SOURCE DEFECT (or docstring defect, owner decision): total_cost's docstring "
        "says 'Spread/slippage are modeled in fill_price', but fill_price ignores slippage_points. "
        "slippage_points is applied only by the tick-quote path (trading/execution/quotes.py). "
        "Reproducer: CostModel(slippage_points=0.5).fill_price(99.5, 100.5, 1) returns 100.5, "
        "not 101.0."
    ),
)
def test_nonzero_slippage_worsens_bar_fill_per_docstring_adverse() -> None:
    # Documented intent: long pays ask + slippage = 100.5 + 0.5 = 101.0;
    # short receives bid - slippage = 99.5 - 0.5 = 99.0.
    model = CostModel(slippage_points=0.5)
    assert model.fill_price(bid=99.5, ask=100.5, direction=1) == pytest.approx(101.0)
    assert model.fill_price(bid=99.5, ask=100.5, direction=-1) == pytest.approx(99.0)


# --- TradingCostModel (unused in the repository; covered as defined in the module) ----


def test_trading_cost_is_spread_plus_slippage_times_absolute_size() -> None:
    # per unit: spread 1.5 + 1.5 * 0.1 = 1.65; size 2.0 -> 1.65 * 2.0 = 3.3.
    model = TradingCostModel(spread=1.5, slippage_frac=0.1)
    assert model.compute_cost(position_size=2.0, price=100.0) == pytest.approx(3.3)
    # A short of the same size costs the same: abs(-2.0) = 2.0 -> 3.3.
    assert model.compute_cost(position_size=-2.0, price=100.0) == pytest.approx(3.3)


def test_trading_cost_is_zero_without_position_adverse() -> None:
    # Size 0 returns 0.0 before any spread is charged.
    assert TradingCostModel(spread=1.5, slippage_frac=0.1).compute_cost(0.0, 100.0) == 0.0


def test_trading_effective_spread_includes_slippage_fraction() -> None:
    # 1.5 * (1 + 0.1) = 1.65.
    assert TradingCostModel(spread=1.5, slippage_frac=0.1).compute_spread() == pytest.approx(1.65)


def test_zero_slippage_fraction_charges_spread_only_adverse() -> None:
    # 1.5 * (1 + 0.0) = 1.5 with no phantom slippage; cost for 2 units = 1.5 * 2 = 3.0.
    model = TradingCostModel(spread=1.5, slippage_frac=0.0)
    assert model.compute_spread() == pytest.approx(1.5)
    assert model.compute_cost(position_size=2.0, price=100.0) == pytest.approx(3.0)
