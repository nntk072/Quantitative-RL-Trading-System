# Integrations · `mt5.domain.mt5_connection`

This page contains 1 public callable records owned by `integrations.mt5.domain.mt5_connection`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ensure_mt5_logged_in`

**Kind:** function · **Status:** stable · **Owner:** `integrations.mt5.domain.mt5_connection`

**Purpose:** Initialize the MT5 terminal and login once per process.

**Exact API:** {py:obj}`integrations.mt5.domain.mt5_connection.ensure_mt5_logged_in` · **Source:** [integrations/mt5/domain/mt5_connection.py:8](../../../../integrations/mt5/domain/mt5_connection.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  login: Login used by the operation described above.
  password: Text or path value identifying the password.
  server: Text or path value identifying the server.
  terminal_path: Path or filename identifying the terminal.
  ```

**Observed usage:**

1. [production caller: `get_robot`](../../../../integrations/mt5/cli/single_symbol_demo.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if not paper_trading:
            raise RuntimeError(
                "single-symbol crossover demo is paper-only until training-equivalent "
                "account-loss guardrails are available"
            )
        ensure_mt5_logged_in(
            login=login,
            password=password,
            server=server,
            terminal_path=terminal_path,
        )

        # Initialize components
        eurusd_h1_data = MT5Data(symbol, mt5.TIMEFRAME_H1)
        cross_over_strategy = CrossOverStrategy(eurusd_h1_data)
        mt5_trader = MT5Trader()
# … caller assertions omitted …
```

2. [production caller: `__init__`](../../../../integrations/mt5/domain/multi_symbol_manager.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        self.terminal_path = terminal_path
        self.symbols = symbols
        self.timeframe = timeframe

        # Initialize/login once per process (safe to call multiple times)
        ensure_mt5_logged_in(
            login=login,
            password=password,
            server=server,
            terminal_path=terminal_path,
        )

        # Initialize data sources for each symbol
        self.data_sources: dict[str, MT5Data] = {}
        self.volatility_metrics: dict[str, dict[str, Any]] = {}

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
