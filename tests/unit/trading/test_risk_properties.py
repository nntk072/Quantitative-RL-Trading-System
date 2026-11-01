from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from trading.risk.sizing import compute_lots


@given(
    risk_budget=st.floats(
        min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
    ),
    near_stop=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    extra_distance=st.floats(
        min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    contract_size=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200, derandomize=True, database=None, deadline=None)
def test_wider_stop_never_increases_lots_for_the_same_dollar_risk(
    risk_budget: float,
    near_stop: float,
    extra_distance: float,
    contract_size: float,
) -> None:
    near = compute_lots(
        equity=0.0,
        risk_frac=0.0,
        risk_usd=risk_budget,
        entry_price=100.0,
        sl_price=100.0 - near_stop,
        contract_size=contract_size,
        min_lot=0.001,
        max_lot=1_000_000.0,
    )
    wide = compute_lots(
        equity=0.0,
        risk_frac=0.0,
        risk_usd=risk_budget,
        entry_price=100.0,
        sl_price=100.0 - near_stop - extra_distance,
        contract_size=contract_size,
        min_lot=0.001,
        max_lot=1_000_000.0,
    )

    assert 0.001 <= wide <= near <= 1_000_000.0
