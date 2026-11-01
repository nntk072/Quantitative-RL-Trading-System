# Trading · `strategies.distribution`

This page contains 10 public callable records owned by `trading.strategies.distribution`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `DistributionStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Distribution is caught after an opposing fair-value gap fails.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy` · **Source:** [trading/strategies/distribution.py:69](../../../../trading/strategies/distribution.py#L69)

**Observed usage:**

1. [test fixture: `test_distribution_after_the_gap_fails_sets_the_side`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L113)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_distribution_after_the_gap_fails_sets_the_side() -> None:
    strategy = DistributionStrategy(enforce_gate=False)
    assert strategy.context_direction(_long_leg(bos_up=1.0)) == 1
    short_row = pd.Series(
        {
            "po3_distribution": 1.0,
            "po3_distribution_direction": -1.0,
            "htf_day_bias": -1.0,
            "po3_distribution_after_ifvg": 1.0,
        }
    )
    assert strategy.context_direction(short_row) == -1
```

2. [test fixture: `test_failure_bar_and_a_bias_mismatch_hold`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_failure_bar_and_a_bias_mismatch_hold() -> None:
    strategy = DistributionStrategy(enforce_gate=True)
    before = _long_leg(po3_distribution_after_ifvg=0.0, bos_up=1.0)
    assert strategy.context_direction(before) == 0
    assert strategy.validate_entry(direction=1, row=before) is False
    against = _long_leg(htf_day_bias=-1.0)
    assert strategy.context_direction(against) == 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.bind_columns`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Resolve inverse-gap stop columns once for the step loop.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.bind_columns` · **Source:** [trading/strategies/distribution.py:141](../../../../trading/strategies/distribution.py#L141)

**Inputs and outputs:**

- **Args:**

  ```text
  columns: Items supplied for the columns, in input order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = DistributionStrategy(...)
result = instance.bind_columns(columns=...)
```

**Lifecycle context:** This callable participates in `DistributionStrategy`: Distribution is caught after an opposing fair-value gap fails. Related public lifecycle methods: {py:obj}`trading.strategies.distribution.DistributionStrategy.bind_columns`, {py:obj}`trading.strategies.distribution.DistributionStrategy.validate_entry`, {py:obj}`trading.strategies.distribution.DistributionStrategy.entry_rejection_reason`, {py:obj}`trading.strategies.distribution.DistributionStrategy.previous_session_pd_eligible`, {py:obj}`trading.strategies.distribution.DistributionStrategy.sl_reference`, {py:obj}`trading.strategies.distribution.DistributionStrategy.target_candidates`, {py:obj}`trading.strategies.distribution.DistributionStrategy.context_direction`, {py:obj}`trading.strategies.distribution.DistributionStrategy.distribution_ready`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.context_direction`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Long when the up bias and the long distribution leg are both on.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.context_direction` · **Source:** [trading/strategies/distribution.py:259](../../../../trading/strategies/distribution.py#L259)

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

1. [test fixture: `test_distribution_after_the_gap_fails_sets_the_side`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L114)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_distribution_after_the_gap_fails_sets_the_side() -> None:
    strategy = DistributionStrategy(enforce_gate=False)
    assert strategy.context_direction(_long_leg(bos_up=1.0)) == 1
    short_row = pd.Series(
        {
            "po3_distribution": 1.0,
            "po3_distribution_direction": -1.0,
            "htf_day_bias": -1.0,
            "po3_distribution_after_ifvg": 1.0,
        }
    )
    assert strategy.context_direction(short_row) == -1
```

2. [test fixture: `test_failure_bar_and_a_bias_mismatch_hold`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L129)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_failure_bar_and_a_bias_mismatch_hold() -> None:
    strategy = DistributionStrategy(enforce_gate=True)
    before = _long_leg(po3_distribution_after_ifvg=0.0, bos_up=1.0)
    assert strategy.context_direction(before) == 0
    assert strategy.validate_entry(direction=1, row=before) is False
    against = _long_leg(htf_day_bias=-1.0)
    assert strategy.context_direction(against) == 0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.distribution_ready`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** True on a distribution bar after the matching inverse gap printed.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.distribution_ready` · **Source:** [trading/strategies/distribution.py:277](../../../../trading/strategies/distribution.py#L277)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Whether distribution ready meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `validate_entry`](../../../../trading/strategies/distribution.py#L164)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
    if self.enforce_gate and not self.distribution_ready(row, direction):
        return False
    return self.previous_session_pd_eligible(row, direction)
```

2. [production caller: `context_direction`](../../../../trading/strategies/distribution.py#L273)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def context_direction(self, row: pd.Series) -> int:
    return (
        1
        if self.distribution_ready(row, 1)
        else (-1 if self.distribution_ready(row, -1) else 0)
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.entry_rejection_reason`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Return the explicit Idea 2 premium/discount rejection label.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.entry_rejection_reason` · **Source:** [trading/strategies/distribution.py:168](../../../../trading/strategies/distribution.py#L168)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Text returned by ``entry_rejection_reason``.
  ```

**Observed usage:**

1. [test fixture: `test_previous_session_pd_gate_is_strict_per_entry_and_reports_reasons`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L180)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    premium["decision_close"] = 112.0
    assert not strategy.validate_entry(direction=1, row=premium)
    # Context still proposes the setup direction; validate_entry rejects that
    # specific new order and preserves the explicit premium_block reason.
    assert strategy.context_direction(premium) == 1
    assert strategy.entry_rejection_reason(direction=1, row=premium) == "premium_block"

    equality = long_discount.copy()
    equality["decision_close"] = 108.0
    assert not strategy.validate_entry(direction=1, row=equality)
    assert strategy.entry_rejection_reason(direction=1, row=equality) == "premium_block"
# … caller assertions omitted …
```

2. [test fixture: `test_previous_session_pd_gate_mirrors_short_and_can_be_disabled`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L209)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        entry_mode="confirmed_first_eligible", previous_session_pd_gate=True
    )
    assert strategy.validate_entry(direction=-1, row=short)
    short["decision_close"] = 108.0
    assert not strategy.validate_entry(direction=-1, row=short)
    assert strategy.entry_rejection_reason(direction=-1, row=short) == "discount_block"

    baseline = DistributionStrategy(entry_mode="confirmed_first_eligible")
    assert baseline.validate_entry(direction=-1, row=short)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.previous_session_pd_eligible`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Per-entry strict discount/premium check; equality is ineligible.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.previous_session_pd_eligible` · **Source:** [trading/strategies/distribution.py:189](../../../../trading/strategies/distribution.py#L189)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Whether previous session pd eligible meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `validate_entry`](../../../../trading/strategies/distribution.py#L166)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
    if self.enforce_gate and not self.distribution_ready(row, direction):
        return False
    return self.previous_session_pd_eligible(row, direction)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.sl_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Structural SL ladder (sweep extremes instead of manip).

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.sl_candidates` · **Source:** [trading/strategies/distribution.py:314](../../../../trading/strategies/distribution.py#L314)

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

1. [test fixture: `test_stop_uses_a_respected_lower_gap_and_an_aligned_higher_one`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L267)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "H1_ifvg_bull_active": 1.0,
            "H1_ifvg_bull_low": 7.0,
            "H1_ifvg_bull_origin": 6.5,
        }
    )
    names = [name for name, _ in strategy.sl_candidates(direction=1, row=row)]
    assert names == [
        "last_swing_low",
        "sweep_low_level",
        "asian_low",
        "london_low",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.sl_reference`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Long -> swept low, short -> swept high (Agent.md §14).

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.sl_reference` · **Source:** [trading/strategies/distribution.py:209](../../../../trading/strategies/distribution.py#L209)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Result of long -> swept low, short -> swept high (Agent.md §14).
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = DistributionStrategy(...)
result = instance.sl_reference(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `DistributionStrategy`: Distribution is caught after an opposing fair-value gap fails. Related public lifecycle methods: {py:obj}`trading.strategies.distribution.DistributionStrategy.bind_columns`, {py:obj}`trading.strategies.distribution.DistributionStrategy.validate_entry`, {py:obj}`trading.strategies.distribution.DistributionStrategy.entry_rejection_reason`, {py:obj}`trading.strategies.distribution.DistributionStrategy.previous_session_pd_eligible`, {py:obj}`trading.strategies.distribution.DistributionStrategy.sl_reference`, {py:obj}`trading.strategies.distribution.DistributionStrategy.target_candidates`, {py:obj}`trading.strategies.distribution.DistributionStrategy.context_direction`, {py:obj}`trading.strategies.distribution.DistributionStrategy.distribution_ready`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.target_candidates`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Named structural targets; the TP resolver validates each side.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.target_candidates` · **Source:** [trading/strategies/distribution.py:226](../../../../trading/strategies/distribution.py#L226)

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
instance = DistributionStrategy(...)
result = instance.target_candidates(direction=..., row=...)
```

**Lifecycle context:** This callable participates in `DistributionStrategy`: Distribution is caught after an opposing fair-value gap fails. Related public lifecycle methods: {py:obj}`trading.strategies.distribution.DistributionStrategy.bind_columns`, {py:obj}`trading.strategies.distribution.DistributionStrategy.validate_entry`, {py:obj}`trading.strategies.distribution.DistributionStrategy.entry_rejection_reason`, {py:obj}`trading.strategies.distribution.DistributionStrategy.previous_session_pd_eligible`, {py:obj}`trading.strategies.distribution.DistributionStrategy.sl_reference`, {py:obj}`trading.strategies.distribution.DistributionStrategy.target_candidates`, {py:obj}`trading.strategies.distribution.DistributionStrategy.context_direction`, {py:obj}`trading.strategies.distribution.DistributionStrategy.distribution_ready`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `DistributionStrategy.validate_entry`

**Kind:** method · **Status:** stable · **Owner:** `trading.strategies.distribution`

**Purpose:** Distribution after the opposing gap fails, when the gate is enforced.

**Exact API:** {py:obj}`trading.strategies.distribution.DistributionStrategy.validate_entry` · **Source:** [trading/strategies/distribution.py:154](../../../../trading/strategies/distribution.py#L154)

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

**Observed usage:**

1. [test fixture: `test_failure_bar_and_a_bias_mismatch_hold`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L130)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_failure_bar_and_a_bias_mismatch_hold() -> None:
    strategy = DistributionStrategy(enforce_gate=True)
    before = _long_leg(po3_distribution_after_ifvg=0.0, bos_up=1.0)
    assert strategy.context_direction(before) == 0
    assert strategy.validate_entry(direction=1, row=before) is False
    against = _long_leg(htf_day_bias=-1.0)
    assert strategy.context_direction(against) == 0
```

2. [test fixture: `test_idea2_accepts_post_confirmation_distribution_without_retest`](../../../../tests/unit/simulation/test_environment/test_distribution_reward.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_idea2_accepts_post_confirmation_distribution_without_retest() -> None:
    strategy = DistributionStrategy(enforce_gate=True)
    row = _long_leg()
    assert "ifvg_retest_bull" not in row.index
    assert strategy.validate_entry(direction=1, row=row)
    assert not strategy.validate_entry(direction=-1, row=row)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
