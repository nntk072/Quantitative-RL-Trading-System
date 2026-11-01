# Simulation · `backtest.cross_validation.strategies.cross_over`

This page contains 6 public callable records owned by `simulation.backtest.cross_validation.strategies.cross_over`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CrossOverStrategy`

**Kind:** class · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** A Backtrader implementation of the CrossOver strategy.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:4](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L4)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy()
```

**Lifecycle context:** A Backtrader implementation of the CrossOver strategy.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `CrossOverStrategy.log`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** Logging function.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.log` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:46](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L46)

**Inputs and outputs:**

- **Args:**

  ```text
  txt: Text or path value identifying the txt.
  dt: Dt used by the operation described above.
  doprint: Whether to enable or require the doprint.
  ```

**Observed usage:**

1. [production caller: `notify_order`](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

            # Check if an order has been completed
            # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, "
                    f"Comm: {order.executed.comm:.2f}"
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
# … caller assertions omitted …
```

2. [production caller: `notify_trade`](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L101)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def notify_trade(self, trade) -> None:
    if not trade.isclosed:
        return

    self.log(f"OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}")
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `CrossOverStrategy.next`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** Evaluate the latest bar and submit a crossover order when eligible.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.next` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:103](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L103)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy(...)
result = instance.next()
```

**Lifecycle context:** This callable participates in `CrossOverStrategy`: A Backtrader implementation of the CrossOver strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `CrossOverStrategy.notify_order`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** Update strategy state when a broker order changes status.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_order` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:58](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  order: Order used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy(...)
result = instance.notify_order(order=...)
```

**Lifecycle context:** This callable participates in `CrossOverStrategy`: A Backtrader implementation of the CrossOver strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `CrossOverStrategy.notify_trade`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** Record the result when a broker trade closes.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_trade` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:92](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L92)

**Inputs and outputs:**

- **Args:**

  ```text
  trade: Trade used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy(...)
result = instance.notify_trade(trade=...)
```

**Lifecycle context:** This callable participates in `CrossOverStrategy`: A Backtrader implementation of the CrossOver strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `CrossOverStrategy.stop`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.cross_over`

**Purpose:** Report final strategy state after the backtest ends.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.stop` · **Source:** [simulation/backtest/cross_validation/strategies/cross_over.py:125](../../../../simulation/backtest/cross_validation/strategies/cross_over.py#L125)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = CrossOverStrategy(...)
result = instance.stop()
```

**Lifecycle context:** This callable participates in `CrossOverStrategy`: A Backtrader implementation of the CrossOver strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.cross_over.CrossOverStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
