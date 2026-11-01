# Simulation · `backtest.cross_validation.strategies.signal_following`

This page contains 4 public callable records owned by `simulation.backtest.cross_validation.strategies.signal_following`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `SignalFollowingStrategy`

**Kind:** class · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.signal_following`

**Purpose:** Execute precomputed actions (+1 long, -1 short, 2 exit, 0 hold).

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy` · **Source:** [simulation/backtest/cross_validation/strategies/signal_following.py:12](../../../../simulation/backtest/cross_validation/strategies/signal_following.py#L12)

**Inputs and outputs:**

- **Args:**

  ```text
  actions (pd.Series): Precomputed action series aligned to the data feed bars.
  printlog (bool): Enable per-bar logging.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SignalFollowingStrategy()
```

**Lifecycle context:** Execute precomputed actions (+1 long, -1 short, 2 exit, 0 hold).

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `SignalFollowingStrategy.log`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.signal_following`

**Purpose:** Write a timestamped strategy message when logging is enabled.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.log` · **Source:** [simulation/backtest/cross_validation/strategies/signal_following.py:30](../../../../simulation/backtest/cross_validation/strategies/signal_following.py#L30)

**Inputs and outputs:**

- **Args:**

  ```text
  txt: Message to include in the backtest log.
  dt: Optional date or time to display.
  doprint: Emit the message even when normal logging is disabled.
  ```

**Observed usage:**

1. [production caller: `notify_order`](../../../../simulation/backtest/cross_validation/strategies/signal_following.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def notify_order(self, order: bt.Order) -> None:
    if order.status in (order.Submitted, order.Accepted):
        return
    if order.status == order.Completed:
        if order.isbuy():
            self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}")
        else:
            self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}")
    elif order.status in (order.Canceled, order.Margin, order.Rejected):
        self.log("Order Canceled/Margin/Rejected")
    self.order = None
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `SignalFollowingStrategy.next`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.signal_following`

**Purpose:** Apply the precomputed action for the current absolute bar when available.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.next` · **Source:** [simulation/backtest/cross_validation/strategies/signal_following.py:59](../../../../simulation/backtest/cross_validation/strategies/signal_following.py#L59)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SignalFollowingStrategy(...)
result = instance.next()
```

**Lifecycle context:** This callable participates in `SignalFollowingStrategy`: Execute precomputed actions (+1 long, -1 short, 2 exit, 0 hold). Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.next`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `SignalFollowingStrategy.notify_order`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.signal_following`

**Purpose:** Update strategy state and log execution or rejection details for an order.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.notify_order` · **Source:** [simulation/backtest/cross_validation/strategies/signal_following.py:42](../../../../simulation/backtest/cross_validation/strategies/signal_following.py#L42)

**Inputs and outputs:**

- **Args:**

  ```text
  order: Order used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SignalFollowingStrategy(...)
result = instance.notify_order(order=...)
```

**Lifecycle context:** This callable participates in `SignalFollowingStrategy`: Execute precomputed actions (+1 long, -1 short, 2 exit, 0 hold). Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.signal_following.SignalFollowingStrategy.next`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
