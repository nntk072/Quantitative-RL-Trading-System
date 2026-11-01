# Trading · `strategies.po3_ifvg`

This page contains 10 public callable records owned by `trading.strategies.po3_ifvg`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PO3IFVGStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy` · **Source:** [trading/strategies/po3_ifvg.py:14](../../../../trading/strategies/po3_ifvg.py#L14)

**Observed usage:**

1. [test fixture: `test_dynamic_rr_scales_with_reachable_reward`](../../../../tests/unit/evaluation/test_order_chart.py#L779)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    env = TradingEnv(
        bars,
        feats,
        strategy_actions=True,
        strategy=PO3IFVGStrategy(enforce_gate=False),
        obs_window=5,
        rr_ratio_range=(1.5, 5.0),
    )
    # Stop distance is 10. A tight bar (12 points of room) stays near 1R.
    tight = env._resolve_trader_tp(
# … caller assertions omitted …
```

2. [test fixture: `test_sell_side_sweep_alone_does_not_set_the_long`](../../../../tests/unit/simulation/test_environment/test_merged_overlay.py#L13)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sell_side_sweep_alone_does_not_set_the_long() -> None:
    strategy = PO3IFVGStrategy(enforce_gate=False)
    row = pd.Series({"sweep_low": 1.0, "htf_day_bias": -1.0})
    assert strategy.context_direction(row) == 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.bind_columns`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Resolve sweep and swing columns once for the step loop.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns` · **Source:** [trading/strategies/po3_ifvg.py:111](../../../../trading/strategies/po3_ifvg.py#L111)

**Inputs and outputs:**

- **Args:**

  ```text
  columns: Items supplied for the columns, in input order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.bind_columns(columns=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.context_direction`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Long on a sell-side sweep or a confirmed swing low. Short mirrors it.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction` · **Source:** [trading/strategies/po3_ifvg.py:228](../../../../trading/strategies/po3_ifvg.py#L228)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``context_direction``.
  ```

**Observed usage:**

1. [test fixture: `test_sell_side_sweep_alone_does_not_set_the_long`](../../../../tests/unit/simulation/test_environment/test_merged_overlay.py#L15)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sell_side_sweep_alone_does_not_set_the_long() -> None:
    strategy = PO3IFVGStrategy(enforce_gate=False)
    row = pd.Series({"sweep_low": 1.0, "htf_day_bias": -1.0})
    assert strategy.context_direction(row) == 0
```

2. [test fixture: `test_buy_side_sweep_on_a_higher_timeframe_sets_the_short`](../../../../tests/unit/simulation/test_environment/test_merged_overlay.py#L21)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_buy_side_sweep_on_a_higher_timeframe_sets_the_short() -> None:
    strategy = PO3IFVGStrategy(enforce_gate=False)
    row = pd.Series({"H1_sweep_high": 1.0, "ifvg_retest_bear": 1.0})
    assert strategy.context_direction(row) == -1
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.entry_gap`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** A live gap on any timeframe.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap` · **Source:** [trading/strategies/po3_ifvg.py:204](../../../../trading/strategies/po3_ifvg.py#L204)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Whether entry gap meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.entry_gap(row=..., direction=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.entry_liquidity`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Swept, or within one ATR of the sweep or manipulation level.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity` · **Source:** [trading/strategies/po3_ifvg.py:188](../../../../trading/strategies/po3_ifvg.py#L188)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Whether entry liquidity meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.entry_liquidity(row=..., direction=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.entry_setup`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** True when a qualified PO3 or independent idea matches the side.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup` · **Source:** [trading/strategies/po3_ifvg.py:253](../../../../trading/strategies/po3_ifvg.py#L253)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Whether entry setup meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `validate_entry`](../../../../trading/strategies/po3_ifvg.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
    if not self.enforce_gate:
        return True
    return self.entry_setup(row, direction)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.sl_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Structural SL ladder for trader ``sl_anchor`` selection.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_candidates` · **Source:** [trading/strategies/po3_ifvg.py:406](../../../../trading/strategies/po3_ifvg.py#L406)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Values returned by ``sl_candidates``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_stop_ladder_includes_the_swept_extreme`](../../../../tests/unit/simulation/test_environment/test_merged_overlay.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "sweep_low_level": 12.0,
            "asian_low": 13.0,
            "london_low": 14.0,
        }
    )
    names = [name for name, _ in strategy.sl_candidates(direction=1, row=row)]
    assert names == [
        "last_swing_low",
        "po3_manipulation_low",
        "sweep_low_level",
        "asian_low",
# … caller assertions omitted …
```

2. [test fixture: `test_stop_can_sit_under_the_gap_or_the_first_candle`](../../../../tests/unit/simulation/test_environment/test_merged_overlay.py#L123)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "M15_fvg_bull_low": 8.0,
            "M15_fvg_bull_origin": 7.5,
            "H1_fvg_bull_low": 6.0,
        }
    )
    names = [name for name, _ in strategy.sl_candidates(direction=1, row=row)]
    assert names == [
        "ifvg_bull_low",
        "ifvg_bull_origin",
        "M15_fvg_bull_low",
        "M15_fvg_bull_origin",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.sl_reference`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Long -> manipulation low, short -> manipulation high (Agent.md §14).

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference` · **Source:** [trading/strategies/po3_ifvg.py:138](../../../../trading/strategies/po3_ifvg.py#L138)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Result of long -> manipulation low, short -> manipulation high (Agent.md §14).
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.sl_reference(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.target_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Named structural targets; the TP resolver validates each side.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates` · **Source:** [trading/strategies/po3_ifvg.py:155](../../../../trading/strategies/po3_ifvg.py#L155)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``float`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.target_candidates(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `PO3IFVGStrategy.validate_entry`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.po3_ifvg`

**Purpose:** Sweep or protected swing on this side when the gate is enforced.

**Exact API:** {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry` · **Source:** [trading/strategies/po3_ifvg.py:124](../../../../trading/strategies/po3_ifvg.py#L124)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Whether validate entry meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = PO3IFVGStrategy(...)
result = instance.validate_entry(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `PO3IFVGStrategy`: Require a post-sweep IFVG for PO3, with OB/SD/FVG ideas independent. Related public lifecycle methods: {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.bind_columns`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.validate_entry`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.sl_reference`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.target_candidates`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_liquidity`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_gap`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.context_direction`, {py:obj}`trading.strategies.po3_ifvg.PO3IFVGStrategy.entry_setup`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
