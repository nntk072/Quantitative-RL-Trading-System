# Trading · `risk.sizing`

This page contains 5 public callable records owned by `trading.risk.sizing`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `compute_lots`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.sizing`

**Purpose:** Compute lot size from risk budget and SL distance.

**Exact API:** {py:obj}`trading.risk.sizing.compute_lots` · **Source:** [trading/risk/sizing.py:93](../../../../trading/risk/sizing.py#L93)

**Inputs and outputs:**

- **Args:**

  ```text
  equity (float): Current account equity. Ignored when ``risk_usd`` is given.
  risk_frac (float): Fraction of equity at risk (e.g. 0.01 for 1%). Ignored when ``risk_usd``
      is given, so a caller asking for a fixed dollar risk cannot have it
      silently scaled to zero by a ``risk_frac`` of 0.
  entry_price (float): Entry price.
  sl_price (float): Stop loss price.
  contract_size (float): Contract multiplier (default 1.0).
  point_value (float): Dollar value per point per contract (default 1.0).
  min_lot (float): Minimum lot size to trade.
  max_lot (float): Maximum lot size to trade.
  max_loss_cap (float | None): If set, cap the USD loss at this amount (e.g. 100 for $100). Ignored when
      ``risk_usd`` is given: that cap is a guard rail for fractional sizing, and
      letting it apply would silently override the caller's explicit request
      (a $500 ask was clamped to the $100 default, so no trade could ever risk
      $500).
  risk_usd (float | None): Explicit dollar risk for this trade. When set it takes precedence over
      ``equity * risk_frac`` and makes 1R a known constant independent of
      account equity and of the agent's chosen fraction.
  ```

- **Returns:**

  ```text
  float: Computed lot size, clipped to [min_lot, max_lot].
  ```

**Observed usage:**

1. [test fixture: `test_wider_stop_returns_fewer_lots`](../../../../tests/integration/backtest/test_entry_levels.py#L665)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_wider_stop_returns_fewer_lots() -> None:
    equity = 100_000.0
    risk = 0.01
    tight = compute_lots(
        equity, risk, 100.0, 98.0, contract_size=1.0, min_lot=0.01, max_lot=10_000.0
    )
    wide = compute_lots(
        equity, risk, 100.0, 90.0, contract_size=1.0, min_lot=0.01, max_lot=10_000.0
    )
    assert wide < tight
```

2. [test fixture: `test_explicit_risk_usd_overrides_zero_risk_frac`](../../../../tests/unit/simulation/test_environment/test_fixed_risk_sizing.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_explicit_risk_usd_overrides_zero_risk_frac() -> None:
    lots = compute_lots(
        equity=50_000.0,
        risk_frac=0.0,  # what the agent actually emitted on 579/650 opens
        entry_price=25_454.2,
        sl_price=25_536.54,
        min_lot=0.01,
        max_lot=100.0,
        max_loss_cap=None,
        risk_usd=500.0,
    )
    assert lots == pytest.approx(500.0 / 82.34, rel=1e-9)
    assert lots * 82.34 == pytest.approx(500.0, rel=1e-9)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `compute_lots_with_execution_reserve`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.sizing`

**Purpose:** Size the stop exposure so stop risk plus per-lot costs fit the budget.

**Exact API:** {py:obj}`trading.risk.sizing.compute_lots_with_execution_reserve` · **Source:** [trading/risk/sizing.py:151](../../../../trading/risk/sizing.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  total_risk_budget_usd: Numeric value used for the total risk budget usd.
  equity: Current account equity in account currency.
  risk_frac: Numeric value used for the risk frac.
  entry_price: Price at which the position was opened.
  sl_price: Numeric value used for the sl price.
  contract_size: Number specifying the contract size for this operation.
  execution_reserve_per_lot: Numeric value used for the execution reserve per lot.
  min_lot: Numeric value used for the min lot.
  max_lot: Numeric value used for the max lot.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``compute_lots_with_execution_reserve``.
  ```

**Observed usage:**

1. [test fixture: `test_trading_risk_primitives_share_risk_and_reserve_sizing`](../../../../tests/unit/trading/test_risk.py#L23)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_risk_primitives_share_risk_and_reserve_sizing() -> None:
    assert stop_loss_risk_usd(10.0, 2.0, 1.5, 2.0) == 60.0
    assert risk_budget_from_equity(100_000.0, 0.01) == 1_000.0
    assert risk_budget_from_equity(-100.0, 0.01) == 0.0
    assert compute_lots_with_execution_reserve(
        total_risk_budget_usd=100.0,
        equity=100_000.0,
        risk_frac=0.01,
        entry_price=100.0,
        sl_price=90.0,
        contract_size=1.0,
        execution_reserve_per_lot=2.0,
        min_lot=0.01,
        max_lot=20.0,
    ) == pytest.approx(100.0 / 12.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `compute_sl_tp_long`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.sizing`

**Purpose:** Compute SL and TP for a long trade.

**Exact API:** {py:obj}`trading.risk.sizing.compute_sl_tp_long` · **Source:** [trading/risk/sizing.py:33](../../../../trading/risk/sizing.py#L33)

**Inputs and outputs:**

- **Args:**

  ```text
  entry_price (float): Entry fill price.
  last_swing_low (float): Most recent confirmed swing low price.
  buffer_pts (float): Buffer below swing low for SL placement (in price points).
  rr_ratio (float): Risk:reward ratio (e.g. 2.0 means TP distance = 2 × SL distance).
  ```

- **Returns:**

  ```text
  tuple[float, float]: (sl_price, tp_price)
  ```

- **Raises:**

  ```text
  ValueError: If ``last_swing_low`` is not strictly below ``entry_price``.
  ```

**Observed usage:**

1. [test fixture: `test_compute_sl_tp_long`](../../../../tests/unit/trading/test_risk.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_compute_sl_tp_long() -> None:
    sl, tp = compute_sl_tp_long(
        entry_price=100.0,
        last_swing_low=95.0,
        buffer_pts=1.0,
        rr_ratio=2.0,
    )
    assert sl == 94.0  # 95.0 - 1.0
    # R = entry - SL = 100 - 94 = 6
    # TP = entry + rr * R = 100 + 2*6 = 112
    assert tp == 112.0
```

2. [tutorial example: `03_trading_and_risk · code cell 2`](../../../../docs/learn/tutorials/03_trading_and_risk.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import matplotlib.pyplot as plt

from trading.risk.sizing import compute_lots, compute_sl_tp_long, stop_loss_risk_usd

entry = 100.0
stop, target = compute_sl_tp_long(entry, last_swing_low=96.0, buffer_pts=0.5, rr_ratio=2.0)
requested_risk_usd = 200.0
lots = compute_lots(
    equity=10_000.0,
    risk_frac=0.02,
    entry_price=entry,
    sl_price=stop,
    min_lot=0.01,
    max_lot=100.0,
    risk_usd=requested_risk_usd,
)
actual_risk = stop_loss_risk_usd(entry - stop, lots, contract_size=1.0)
print(
    {
        "entry": entry,
        "stop": stop,
        "target": target,
        "lots": round(lots, 3),
        "risk_usd": round(actual_risk, 2),
        "reward_risk": (target - entry) / (entry - stop),
    }
)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `compute_sl_tp_short`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.sizing`

**Purpose:** Compute SL and TP for a short trade.

**Exact API:** {py:obj}`trading.risk.sizing.compute_sl_tp_short` · **Source:** [trading/risk/sizing.py:63](../../../../trading/risk/sizing.py#L63)

**Inputs and outputs:**

- **Args:**

  ```text
  entry_price (float): Entry fill price.
  last_swing_high (float): Most recent confirmed swing high price.
  buffer_pts (float): Buffer above swing high for SL placement (in price points).
  rr_ratio (float): Risk:reward ratio.
  ```

- **Returns:**

  ```text
  tuple[float, float]: (sl_price, tp_price)
  ```

- **Raises:**

  ```text
  ValueError: If ``last_swing_high`` is not strictly above ``entry_price``.
  ```

**Observed usage:**

1. [test fixture: `test_compute_sl_tp_short`](../../../../tests/unit/trading/test_risk.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_compute_sl_tp_short() -> None:
    sl, tp = compute_sl_tp_short(
        entry_price=100.0,
        last_swing_high=105.0,
        buffer_pts=1.0,
        rr_ratio=2.0,
    )
    assert sl == 106.0  # 105.0 + 1.0
    assert tp == 88.0  # 100 - 2*(106-100)
```

2. [production caller: `compute_sl_tp_from_structure`](../../../../trading/risk/sizing.py#L236)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def compute_sl_tp_from_structure(
    *,
    direction: int,
    entry_price: float,
    structure_level: float,
    rr_ratio: float,
    buffer_pts: float = 0.0,
) -> tuple[float, float]:
    if direction == 1:
        return compute_sl_tp_long(entry_price, structure_level, buffer_pts, rr_ratio)
    if direction == -1:
        return compute_sl_tp_short(entry_price, structure_level, buffer_pts, rr_ratio)
    raise ValueError(f"direction must be +1 or -1, got {direction}")
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `stop_loss_risk_usd`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.sizing`

**Purpose:** Return the account-currency loss at a stop for the requested position.

**Exact API:** {py:obj}`trading.risk.sizing.stop_loss_risk_usd` · **Source:** [trading/risk/sizing.py:13](../../../../trading/risk/sizing.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  stop_distance: Entry-to-stop distance in price units.
  lots: Numeric value used for the lots.
  contract_size: Number specifying the contract size for this operation.
  point_value: Numeric value used for the point value.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``stop_loss_risk_usd``.
  ```

**Observed usage:**

1. [test fixture: `test_trading_risk_primitives_share_risk_and_reserve_sizing`](../../../../tests/unit/trading/test_risk.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_risk_primitives_share_risk_and_reserve_sizing() -> None:
    assert stop_loss_risk_usd(10.0, 2.0, 1.5, 2.0) == 60.0
    assert risk_budget_from_equity(100_000.0, 0.01) == 1_000.0
    assert risk_budget_from_equity(-100.0, 0.01) == 0.0
    assert compute_lots_with_execution_reserve(
        total_risk_budget_usd=100.0,
        equity=100_000.0,
# … caller assertions omitted …
```

2. [tutorial example: `03_trading_and_risk · code cell 2`](../../../../docs/learn/tutorials/03_trading_and_risk.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import matplotlib.pyplot as plt

from trading.risk.sizing import compute_lots, compute_sl_tp_long, stop_loss_risk_usd

entry = 100.0
stop, target = compute_sl_tp_long(entry, last_swing_low=96.0, buffer_pts=0.5, rr_ratio=2.0)
requested_risk_usd = 200.0
lots = compute_lots(
    equity=10_000.0,
    risk_frac=0.02,
    entry_price=entry,
    sl_price=stop,
    min_lot=0.01,
    max_lot=100.0,
    risk_usd=requested_risk_usd,
)
actual_risk = stop_loss_risk_usd(entry - stop, lots, contract_size=1.0)
print(
    {
        "entry": entry,
        "stop": stop,
        "target": target,
        "lots": round(lots, 3),
        "risk_usd": round(actual_risk, 2),
        "reward_risk": (target - entry) / (entry - stop),
    }
)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
