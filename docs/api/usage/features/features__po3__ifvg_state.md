# Features · `po3.ifvg_state`

This page contains 1 public callable records owned by `features.po3.ifvg_state`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_po3_ifvg_state`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.ifvg_state`

**Purpose:** Build the revised causal phase sequence for Idea 1/2.

**Exact API:** {py:obj}`features.po3.ifvg_state.build_po3_ifvg_state` · **Source:** [features/po3/ifvg_state.py:9](../../../../features/po3/ifvg_state.py#L9)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  sweeps: Tabular data used for the sweeps.
  ifvg_zones: Tabular data used for the ifvg zones.
  max_ifvg_age_bars: Market bar or price data used for build the revised causal phase sequence for Idea 1/2.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_po3_ifvg_state``.
  ```

**Observed usage:**

1. [test fixture: `test_reclaim_waits_for_associated_ifvg_then_starts_distribution`](../../../../tests/unit/features/test_po3_ifvg_state.py#L55)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_reclaim_waits_for_associated_ifvg_then_starts_distribution() -> None:
    bars, sweeps, zones = _inputs()
    state = build_po3_ifvg_state(bars, sweeps, zones)

    assert state["po3_manipulation_active"].iloc[2] == 1
    assert state["po3_manipulation_end"].iloc[3] == 1
    assert state["po3_waiting_ifvg"].iloc[3] == 1
    assert state["po3_distribution"].iloc[3] == 0
# … caller assertions omitted …
```

2. [test fixture: `test_same_candle_reclaim_is_allowed_but_distribution_waits_for_ifvg`](../../../../tests/unit/features/test_po3_ifvg_state.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_same_candle_reclaim_is_allowed_but_distribution_waits_for_ifvg() -> None:
    bars, sweeps, zones = _inputs()
    bars.loc[bars.index[2], "close"] = 99.2
    state = build_po3_ifvg_state(bars, sweeps, zones)

    assert state["po3_manipulation_end"].iloc[2] == 1
    assert state["po3_waiting_ifvg"].iloc[2] == 1
    assert state["po3_distribution"].iloc[2:4].sum() == 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
