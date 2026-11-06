# Trading · `baselines.step_indexed_strategy`

This page contains 5 public callable records owned by `trading.baselines.step_indexed_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `BaseStrategy`

**Kind:** class · **Status:** stable · **Owner:** `trading.baselines.step_indexed_strategy`

**Purpose:** Common interface for all non-learned and learned baselines.

**Exact API:** {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy` · **Source:** [trading/baselines/step_indexed_strategy.py:16](../../../../trading/baselines/step_indexed_strategy.py#L16)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaseStrategy(n_bars=...)
```

**Lifecycle context:** Common interface for all non-learned and learned baselines.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaseStrategy.act`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.step_indexed_strategy`

**Purpose:** Return the action for the current bar.

**Exact API:** {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act` · **Source:** [trading/baselines/step_indexed_strategy.py:51](../../../../trading/baselines/step_indexed_strategy.py#L51)

**Inputs and outputs:**

- **Args:**

  ```text
  obs: Environment observation (ignored by signal-based
      strategies; kept for interface compatibility).
  ```

- **Returns:**

  ```text
  Continuous action in ``[-1.0, 1.0]``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaseStrategy(...)
result = instance.act(obs=...)
```

**Lifecycle context:** This callable participates in `BaseStrategy`: Common interface for all non-learned and learned baselines. Related public lifecycle methods: {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.reset`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.fast_forward`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act_at`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaseStrategy.act_at`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.step_indexed_strategy`

**Purpose:** Return the action for an absolute bar without advancing strategy state.

**Exact API:** {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act_at` · **Source:** [trading/baselines/step_indexed_strategy.py:65](../../../../trading/baselines/step_indexed_strategy.py#L65)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_index: Absolute row index in the bars used to build the strategy.
  ```

- **Returns:**

  ```text
  The signal at ``bar_index``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaseStrategy(...)
result = instance.act_at(bar_index=...)
```

**Lifecycle context:** This callable participates in `BaseStrategy`: Common interface for all non-learned and learned baselines. Related public lifecycle methods: {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.reset`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.fast_forward`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act_at`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaseStrategy.fast_forward`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.step_indexed_strategy`

**Purpose:** Advance the step counter by ``n_bars`` without emitting actions.

**Exact API:** {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.fast_forward` · **Source:** [trading/baselines/step_indexed_strategy.py:38](../../../../trading/baselines/step_indexed_strategy.py#L38)

**Inputs and outputs:**

- **Args:**

  ```text
  n_bars: Market bar or price data used for advance the step counter by ``n_bars`` without emitting actions.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaseStrategy(...)
result = instance.fast_forward(n_bars=...)
```

**Lifecycle context:** This callable participates in `BaseStrategy`: Common interface for all non-learned and learned baselines. Related public lifecycle methods: {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.reset`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.fast_forward`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act_at`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `BaseStrategy.reset`

**Kind:** method · **Status:** stable · **Owner:** `trading.baselines.step_indexed_strategy`

**Purpose:** Reset the internal step counter for a new episode.

**Exact API:** {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.reset` · **Source:** [trading/baselines/step_indexed_strategy.py:34](../../../../trading/baselines/step_indexed_strategy.py#L34)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaseStrategy(...)
result = instance.reset()
```

**Lifecycle context:** This callable participates in `BaseStrategy`: Common interface for all non-learned and learned baselines. Related public lifecycle methods: {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.reset`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.fast_forward`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act`, {py:obj}`trading.baselines.step_indexed_strategy.BaseStrategy.act_at`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
