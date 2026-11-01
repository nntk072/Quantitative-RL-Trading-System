# Trading · `baselines.cash_hold`

This page contains 3 public callable records owned by `trading.baselines.cash_hold`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `fit_hold_lots`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.cash_hold`

**Purpose:** Lot size whose train path reaches, and does not pass, the loss caps.

**Exact API:** {py:obj}`trading.baselines.cash_hold.fit_hold_lots` · **Source:** [trading/baselines/cash_hold.py:75](../../../../trading/baselines/cash_hold.py#L75)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Training bars. The entry is the first bar after ``obs_window``.
  max_loss_usd: Account loss from the initial balance.
  daily_loss_usd: Loss allowed from the session's starting equity.
  swap_per_lot: Overnight charge per lot. Defaults to the US100 long swap.
  spread: Bid/ask width in price units. Close is the bid.
  obs_window: Bars skipped before the first fill.
  ```

- **Returns:**

  ```text
  Lots and the train moves that set them. The used lot is the tighter
  of the max-loss lot and the daily-loss lot.
  ```

**Observed usage:**

1. [test fixture: `test_fit_uses_the_tighter_of_max_loss_and_daily_loss`](../../../../tests/unit/trading/test_cash_hold.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fit_uses_the_tighter_of_max_loss_and_daily_loss() -> None:
    bars = _bars(
        [
            ("2025-01-06 16:30", 100.0, 100.0),
            ("2025-01-07 16:30", 90.0, 40.0),
        ]
    )
    fitted = fit_hold_lots(bars, swap_per_lot=0.0, spread=0.0, obs_window=0)
    # Adverse from entry is 60 points. The session drop is 50, so $5,000 binds.
    assert fitted["lots_from_max_loss"] == pytest.approx(10_000 / 60)
    assert fitted["lots_from_daily_loss"] == pytest.approx(5_000 / 50)
    assert fitted["lots"] == pytest.approx(5_000 / 50)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `simulate_hold`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.cash_hold`

**Purpose:** Mark a fixed-lot long from the first traded ask to the last bid.

**Exact API:** {py:obj}`trading.baselines.cash_hold.simulate_hold` · **Source:** [trading/baselines/cash_hold.py:123](../../../../trading/baselines/cash_hold.py#L123)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  lots: Numeric value used for the lots.
  initial_balance: Numeric value used for the initial balance.
  max_loss_usd: Numeric value used for the max loss usd.
  daily_loss_usd: Numeric value used for the daily loss usd.
  swap_per_lot: Swap per lot used by the operation described above.
  spread: Numeric value used for the spread.
  obs_window: Numeric value used for the obs window.
  leverage_intraday: Numeric value used for the leverage intraday.
  leverage_swing: Numeric value used for the leverage swing.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_hold_closes_when_the_max_loss_is_reached`](../../../../tests/unit/trading/test_cash_hold.py#L47)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        [
            ("2025-01-06 16:30", 100.0, 100.0),
            ("2025-01-06 16:31", 80.0, 70.0),
        ]
    )
    out = simulate_hold(
        bars,
        lots=1.0,
        max_loss_usd=10.0,
        daily_loss_usd=5_000.0,
        swap_per_lot=0.0,
        spread=0.0,
        obs_window=0,
    )
    assert out["reason"] == "max_loss"
    assert out["total_pnl"] == pytest.approx(-10.0)
    assert out["margin_ok"] is True
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `swap_usd_per_lot`

**Kind:** function · **Status:** stable · **Owner:** `trading.baselines.cash_hold`

**Purpose:** Dollar swap for one lot for one night. Negative is a charge.

**Exact API:** {py:obj}`trading.baselines.cash_hold.swap_usd_per_lot` · **Source:** [trading/baselines/cash_hold.py:30](../../../../trading/baselines/cash_hold.py#L30)

**Inputs and outputs:**

- **Args:**

  ```text
  swap_points: Numeric value used for the swap points.
  point_size: Number specifying the point size for this operation.
  contract_size: Number specifying the contract size for this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``swap_usd_per_lot``.
  ```

**Observed usage:**

1. [test fixture: `test_swap_points_convert_at_one_cent`](../../../../tests/unit/trading/test_cash_hold.py#L21)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_swap_points_convert_at_one_cent() -> None:
    assert swap_usd_per_lot() == pytest.approx(-6.7512)
```

2. [production caller: `fit_hold_lots`](../../../../trading/baselines/cash_hold.py#L99)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    path = _slice_from_warmup(bars, obs_window)
    per_lot = swap_usd_per_lot() if swap_per_lot is None else float(swap_per_lot)
    charge = abs(per_lot)
    ts = pd.DatetimeIndex(path.index).tz_convert("Etc/GMT-3")
    entry = float(path["close"].iloc[0]) + spread
    low = path["low"].astype(float).to_numpy()
    worst_i = int(np.argmin(low))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
