# Trading · `risk.ftmo_clock`

This page contains 2 public callable records owned by `trading.risk.ftmo_clock`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FTMOMidnightSnapshotUnavailable`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.ftmo_clock`

**Purpose:** Required midnight balance/valuation state cannot be reconstructed.

**Exact API:** {py:obj}`trading.risk.ftmo_clock.FTMOMidnightSnapshotUnavailable` · **Source:** [trading/risk/ftmo_clock.py:16](../../../../trading/risk/ftmo_clock.py#L16)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = FTMOMidnightSnapshotUnavailable(...)
```

**Lifecycle context:** Required midnight balance/valuation state cannot be reconstructed.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `ftmo_trading_day`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.ftmo_clock`

**Purpose:** Return the FTMO CE(S)T calendar date of an aware timestamp.

**Exact API:** {py:obj}`trading.risk.ftmo_clock.ftmo_trading_day` · **Source:** [trading/risk/ftmo_clock.py:20](../../../../trading/risk/ftmo_clock.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  timestamp: A timezone-aware event time (never an unlabelled broker time).
  ```

- **Returns:**

  ```text
  The corresponding Prague local calendar date.
  ```

**Observed usage:**

1. [test fixture: `test_prague_midnight_uses_winter_and_summer_offsets`](../../../../tests/unit/trading/test_ftmo_midnight_fidelity.py#L13)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_prague_midnight_uses_winter_and_summer_offsets() -> None:
    assert str(ftmo_trading_day("2026-01-08T22:59:59Z")) == "2026-01-08"
    assert str(ftmo_trading_day("2026-01-08T23:00:00Z")) == "2026-01-09"
    assert str(ftmo_trading_day("2026-07-08T21:59:59Z")) == "2026-07-08"
    assert str(ftmo_trading_day("2026-07-08T22:00:00Z")) == "2026-07-09"
```

2. [test fixture: `test_prague_midnight_tracks_dst_transition_boundaries`](../../../../tests/unit/trading/test_ftmo_midnight_fidelity.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_prague_midnight_tracks_dst_transition_boundaries() -> None:
    assert str(ftmo_trading_day("2026-03-28T22:59:59Z")) == "2026-03-28"
    assert str(ftmo_trading_day("2026-03-28T23:00:00Z")) == "2026-03-29"
    assert str(ftmo_trading_day("2026-03-29T21:59:59Z")) == "2026-03-29"
    assert str(ftmo_trading_day("2026-03-29T22:00:00Z")) == "2026-03-30"
    assert str(ftmo_trading_day("2026-10-24T21:59:59Z")) == "2026-10-24"
    assert str(ftmo_trading_day("2026-10-24T22:00:00Z")) == "2026-10-25"
    assert str(ftmo_trading_day("2026-10-25T22:59:59Z")) == "2026-10-25"
    assert str(ftmo_trading_day("2026-10-25T23:00:00Z")) == "2026-10-26"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
