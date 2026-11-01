# Simulation · `backtest.cross_validation.strategies.macd_strategy`

This page contains 10 public callable records owned by `simulation.backtest.cross_validation.strategies.macd_strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `EMAMACDStrategy`

**Kind:** class · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Backtrader implementation of the MACD + EMA50 baseline strategy.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:130](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L130)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = EMAMACDStrategy()
```

**Lifecycle context:** Backtrader implementation of the MACD + EMA50 baseline strategy.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `MACDStrategy`

**Kind:** class · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Backtrader implementation of the MACD baseline strategy.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:6](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L6)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MACDStrategy()
```

**Lifecycle context:** Backtrader implementation of the MACD baseline strategy.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `EMAMACDStrategy.log`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Logging function.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.log` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:180](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L180)

**Inputs and outputs:**

- **Args:**

  ```text
  txt: Text or path value identifying the txt.
  dt: Dt used by the operation described above.
  doprint: Whether to enable or require the doprint.
  ```

**Observed usage:**

1. [production caller: `notify_order`](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L203)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, "
                    f"Comm: {order.executed.comm:.2f}"
                )
                self.position = 1
            else:  # Sell
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, "
# … caller assertions omitted …
```

2. [production caller: `next`](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L247)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if self.position == 0:
            # Flat: check for entry
            if self.cooldown_counter == 0:
                if self.dataclose[0] > self.ema50[0] and bullish_cross:
                    # Long entry
                    self.log(f"BUY CREATE, {self.dataclose[0]:.2f}")
                    self.order = self.buy()
                    self.position = 1
                elif self.dataclose[0] < self.ema50[0] and bearish_cross:
                    # Short entry
                    self.log(f"SELL CREATE, {self.dataclose[0]:.2f}")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `EMAMACDStrategy.next`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Evaluate the EMA and MACD crossover on the current bar and trade when eligible.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.next` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:222](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L222)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = EMAMACDStrategy(...)
result = instance.next()
```

**Lifecycle context:** This callable participates in `EMAMACDStrategy`: Backtrader implementation of the MACD + EMA50 baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.next`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `EMAMACDStrategy.notify_order`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Update pending-order state when the broker reports an order status.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.notify_order` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:192](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L192)

**Inputs and outputs:**

- **Args:**

  ```text
  order: Order used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = EMAMACDStrategy(...)
result = instance.notify_order(order=...)
```

**Lifecycle context:** This callable participates in `EMAMACDStrategy`: Backtrader implementation of the MACD + EMA50 baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.EMAMACDStrategy.next`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `MACDStrategy.log`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Logging function.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.log` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:45](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L45)

**Inputs and outputs:**

- **Args:**

  ```text
  txt: Text or path value identifying the txt.
  dt: Dt used by the operation described above.
  doprint: Whether to enable or require the doprint.
  ```

**Observed usage:**

1. [production caller: `notify_order`](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        if order.status in [order.Submitted, order.Accepted]:
            return

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

2. [production caller: `notify_trade`](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L96)

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

## `MACDStrategy.next`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Evaluate the current MACD signal and submit an order when eligible.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.next` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:98](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L98)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MACDStrategy(...)
result = instance.next()
```

**Lifecycle context:** This callable participates in `MACDStrategy`: Backtrader implementation of the MACD baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `MACDStrategy.notify_order`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Update pending-order state when the broker reports an order status.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_order` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:57](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L57)

**Inputs and outputs:**

- **Args:**

  ```text
  order: Order used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MACDStrategy(...)
result = instance.notify_order(order=...)
```

**Lifecycle context:** This callable participates in `MACDStrategy`: Backtrader implementation of the MACD baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `MACDStrategy.notify_trade`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Record gross and net results when a trade closes.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_trade` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:87](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L87)

**Inputs and outputs:**

- **Args:**

  ```text
  trade: Trade used by the operation described above.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MACDStrategy(...)
result = instance.notify_trade(trade=...)
```

**Lifecycle context:** This callable participates in `MACDStrategy`: Backtrader implementation of the MACD baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `MACDStrategy.stop`

**Kind:** method · **Status:** stable · **Owner:** `simulation.backtest.cross_validation.strategies.macd_strategy`

**Purpose:** Report strategy state when the backtest finishes.

**Exact API:** {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.stop` · **Source:** [simulation/backtest/cross_validation/strategies/macd_strategy.py:121](../../../../simulation/backtest/cross_validation/strategies/macd_strategy.py#L121)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MACDStrategy(...)
result = instance.stop()
```

**Lifecycle context:** This callable participates in `MACDStrategy`: Backtrader implementation of the MACD baseline strategy. Related public lifecycle methods: {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.log`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_order`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.notify_trade`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.next`, {py:obj}`simulation.backtest.cross_validation.strategies.macd_strategy.MACDStrategy.stop`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
