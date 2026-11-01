# Evaluation · `metrics.performance`

This page contains 12 public callable records owned by `evaluation.metrics.performance`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PerformanceMetrics`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Aggregate returns, trade statistics, and risk-breach measures for a run.

**Exact API:** {py:obj}`evaluation.metrics.performance.PerformanceMetrics` · **Source:** [evaluation/metrics/performance.py:21](../../../../evaluation/metrics/performance.py#L21)

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L365)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    pnls = np.asarray(trade_pnls if trade_pnls is not None else [], dtype=float)
    stats = _trade_stats(pnls)

    calmar = float(annualised / mdd) if mdd > 0 else 0.0
    return PerformanceMetrics(
        sharpe=_sharpe(returns, periods_per_year),
        sortino=_sortino(returns, periods_per_year),
        calmar=calmar,
        max_drawdown=mdd,
        total_return_pct=float(total_pnl / initial_balance * 100.0),
        total_pnl=total_pnl,
        profit_factor=stats["profit_factor"],
        win_rate=stats["win_rate"],
        expectancy=stats["expectancy"],
        n_trades=int(pnls.size),
        breach_count=breach_count,
        breach_rate=(breach_count / n_sessions) if n_sessions > 0 else 0.0,
        turnover=float(pnls.size / curve.size) if curve.size else 0.0,
        max_consec_loss=_max_consec_loss(pnls),
        avg_trade=stats["expectancy"],
        extras=dict(extras or {}),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `calculate_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Pandas-friendly adapter matching the legacy ``eval.metrics`` signature.

**Exact API:** {py:obj}`evaluation.metrics.performance.calculate_metrics` · **Source:** [evaluation/metrics/performance.py:417](../../../../evaluation/metrics/performance.py#L417)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Bar-level equity curve (``pd.Series`` or sequence).
  trades: Trade records (``pd.DataFrame`` with a ``pnl`` column) or None.
  n_sessions: Number of trading sessions, for ``breach_rate``.
  n_breach_sessions: Sessions in which a guardrail breach occurred.
  periods_per_year: Bars per year for annualisation.  Defaults to M1
      bars (``252 * 390``) to match the legacy evaluation runs.
  initial_balance: Account balance before the first bar.  When ``None``,
      the first value of the equity curve is used as the initial balance.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = calculate_metrics(equity=..., trades=..., n_sessions=..., n_breach_sessions=..., periods_per_year=..., initial_balance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `compute_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Compute the standard metric set for one evaluation run.

**Exact API:** {py:obj}`evaluation.metrics.performance.compute_metrics` · **Source:** [evaluation/metrics/performance.py:308](../../../../evaluation/metrics/performance.py#L308)

**Inputs and outputs:**

- **Args:**

  ```text
  equity_curve: Equity after each bar, starting at ``initial_balance``.
  initial_balance: Account balance before the first bar.
  trade_pnls: Per-trade PnL of closed trades, if available.
  periods_per_year: Bars per year used to annualise ratios.
  breach_count: Risk-limit breach events recorded during the run.
  n_sessions: Number of trading sessions in the run; used for
      ``breach_rate`` (fraction of sessions with a breach).
  extras: Caller-specific metrics (e.g. sweep delay) merged into output.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

- **Raises:**

  ```text
  ValueError: If the equity curve is empty or the initial balance is
      not strictly positive.
  ```

**Observed usage:**

1. [tutorial example: `05_evaluation · code cell 2`](../../../../docs/learn/tutorials/05_evaluation.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import matplotlib.pyplot as plt
import numpy as np

from evaluation.metrics.performance import compute_metrics

equity = np.array([10_000, 10_120, 10_060, 10_240, 10_190, 10_360], dtype=float)
trade_pnls = [120.0, -60.0, 180.0, -50.0, 170.0]
metrics = compute_metrics(
    equity, initial_balance=equity[0], trade_pnls=trade_pnls, periods_per_year=5
)
print(
    {
        "return_pct": round(metrics.total_return_pct, 2),
        "max_drawdown": round(metrics.max_drawdown, 4),
        "profit_factor": round(metrics.profit_factor, 2),
        "win_rate": round(metrics.win_rate, 2),
        "trades": metrics.n_trades,
    }
)
```

2. [production caller: `calculate_metrics`](../../../../evaluation/metrics/performance.py#L473)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            pnl = pnl.dropna() if hasattr(pnl, "dropna") else pnl
            trade_pnls = [float(v) for v in pnl]

    init_bal = float(curve[0]) if initial_balance is None else float(initial_balance)

    return compute_metrics(
        curve,
        initial_balance=init_bal,
        trade_pnls=trade_pnls,
        periods_per_year=periods_per_year,
        breach_count=int(n_breach_sessions),
        n_sessions=n_sessions,
        extras={
            "fill_count": float(fill_count),
            "incomplete_positions": float(incomplete_positions),
            "entry_active": float(bool(trade_pnls)),
        },
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `evaluation_periods_per_year`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Resolve annualization basis, preserving legacy M1 values for old configs.

**Exact API:** {py:obj}`evaluation.metrics.performance.evaluation_periods_per_year` · **Source:** [evaluation/metrics/performance.py:391](../../../../evaluation/metrics/performance.py#L391)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``evaluation_periods_per_year``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = evaluation_periods_per_year(config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `max_drawdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return peak-to-trough decline as a positive fraction.

**Exact API:** {py:obj}`evaluation.metrics.performance.max_drawdown` · **Source:** [evaluation/metrics/performance.py:209](../../../../evaluation/metrics/performance.py#L209)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Equity values ordered in time.
  ```

- **Returns:**

  ```text
  Largest relative decline from a running peak, in ``[0, 1]``.
  ```

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L353)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        # Callers may supply end-of-bar valuations without the opening capital.
        # Preserve an explicitly included opening balance, otherwise count the
        # first valuation's profit or loss in the return path and drawdown.
    path = curve if curve[0] == initial_balance else np.concatenate(([initial_balance], curve))
    returns = _bar_returns(path)
    mdd = max_drawdown(path)
    total_pnl = float(curve[-1] - initial_balance)
    # ``curve`` may either include the initial balance or contain only
    # end-of-bar valuations. ``returns`` always counts elapsed bar intervals,
    # so use it as the annualisation duration in both representations.
    years = returns.size / periods_per_year
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `sweep_delay_breakdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Summarise Sweep Delay and Asian-vs-London targeting from open trades.

**Exact API:** {py:obj}`evaluation.metrics.performance.sweep_delay_breakdown` · **Source:** [evaluation/metrics/performance.py:151](../../../../evaluation/metrics/performance.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: The environment's ``trade_log`` list.
  delay_key: Trade-log key holding the delay in seconds.
  level_key: Trade-log key holding the swept level name.
  ```

- **Returns:**

  ```text
  Dict with ``sweep_delay_mean_s``, ``sweep_delay_median_s``,
  ``n_entries``, ``london_pct`` and ``asian_pct`` (percent of
  entries attributed to London/Asian levels).
  ```

**Observed usage:**

1. [production caller: `build_run_report`](../../../../evaluation/reporting/run_summary.py#L226)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_run_report(
    metrics: PerformanceMetrics,
    trade_log: Sequence[dict[str, Any]] | None = None,
    **context: Any,
) -> dict[str, Any]:
    report: dict[str, Any] = asdict(metrics)
    report["activity_status"] = activity_status(metrics)
    report["sweep_delay"] = sweep_delay_breakdown(trade_log or [])
    report.update(context)
    return report
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `PerformanceMetrics`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Aggregate returns, trade statistics, and risk-breach measures for a run.

**Exact API:** {py:obj}`evaluation.metrics.performance.PerformanceMetrics` · **Source:** [evaluation/metrics/performance.py:21](../../../../evaluation/metrics/performance.py#L21)

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L365)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    pnls = np.asarray(trade_pnls if trade_pnls is not None else [], dtype=float)
    stats = _trade_stats(pnls)

    calmar = float(annualised / mdd) if mdd > 0 else 0.0
    return PerformanceMetrics(
        sharpe=_sharpe(returns, periods_per_year),
        sortino=_sortino(returns, periods_per_year),
        calmar=calmar,
        max_drawdown=mdd,
        total_return_pct=float(total_pnl / initial_balance * 100.0),
        total_pnl=total_pnl,
        profit_factor=stats["profit_factor"],
        win_rate=stats["win_rate"],
        expectancy=stats["expectancy"],
        n_trades=int(pnls.size),
        breach_count=breach_count,
        breach_rate=(breach_count / n_sessions) if n_sessions > 0 else 0.0,
        turnover=float(pnls.size / curve.size) if curve.size else 0.0,
        max_consec_loss=_max_consec_loss(pnls),
        avg_trade=stats["expectancy"],
        extras=dict(extras or {}),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `calculate_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Pandas-friendly adapter matching the legacy ``eval.metrics`` signature.

**Exact API:** {py:obj}`evaluation.metrics.performance.calculate_metrics` · **Source:** [evaluation/metrics/performance.py:417](../../../../evaluation/metrics/performance.py#L417)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Bar-level equity curve (``pd.Series`` or sequence).
  trades: Trade records (``pd.DataFrame`` with a ``pnl`` column) or None.
  n_sessions: Number of trading sessions, for ``breach_rate``.
  n_breach_sessions: Sessions in which a guardrail breach occurred.
  periods_per_year: Bars per year for annualisation.  Defaults to M1
      bars (``252 * 390``) to match the legacy evaluation runs.
  initial_balance: Account balance before the first bar.  When ``None``,
      the first value of the equity curve is used as the initial balance.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = calculate_metrics(equity=..., trades=..., n_sessions=..., n_breach_sessions=..., periods_per_year=..., initial_balance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `compute_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Compute the standard metric set for one evaluation run.

**Exact API:** {py:obj}`evaluation.metrics.performance.compute_metrics` · **Source:** [evaluation/metrics/performance.py:308](../../../../evaluation/metrics/performance.py#L308)

**Inputs and outputs:**

- **Args:**

  ```text
  equity_curve: Equity after each bar, starting at ``initial_balance``.
  initial_balance: Account balance before the first bar.
  trade_pnls: Per-trade PnL of closed trades, if available.
  periods_per_year: Bars per year used to annualise ratios.
  breach_count: Risk-limit breach events recorded during the run.
  n_sessions: Number of trading sessions in the run; used for
      ``breach_rate`` (fraction of sessions with a breach).
  extras: Caller-specific metrics (e.g. sweep delay) merged into output.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

- **Raises:**

  ```text
  ValueError: If the equity curve is empty or the initial balance is
      not strictly positive.
  ```

**Observed usage:**

1. [tutorial example: `05_evaluation · code cell 2`](../../../../docs/learn/tutorials/05_evaluation.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import matplotlib.pyplot as plt
import numpy as np

from evaluation.metrics.performance import compute_metrics

equity = np.array([10_000, 10_120, 10_060, 10_240, 10_190, 10_360], dtype=float)
trade_pnls = [120.0, -60.0, 180.0, -50.0, 170.0]
metrics = compute_metrics(
    equity, initial_balance=equity[0], trade_pnls=trade_pnls, periods_per_year=5
)
print(
    {
        "return_pct": round(metrics.total_return_pct, 2),
        "max_drawdown": round(metrics.max_drawdown, 4),
        "profit_factor": round(metrics.profit_factor, 2),
        "win_rate": round(metrics.win_rate, 2),
        "trades": metrics.n_trades,
    }
)
```

2. [production caller: `calculate_metrics`](../../../../evaluation/metrics/performance.py#L473)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            pnl = pnl.dropna() if hasattr(pnl, "dropna") else pnl
            trade_pnls = [float(v) for v in pnl]

    init_bal = float(curve[0]) if initial_balance is None else float(initial_balance)

    return compute_metrics(
        curve,
        initial_balance=init_bal,
        trade_pnls=trade_pnls,
        periods_per_year=periods_per_year,
        breach_count=int(n_breach_sessions),
        n_sessions=n_sessions,
        extras={
            "fill_count": float(fill_count),
            "incomplete_positions": float(incomplete_positions),
            "entry_active": float(bool(trade_pnls)),
        },
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `evaluation_periods_per_year`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Resolve annualization basis, preserving legacy M1 values for old configs.

**Exact API:** {py:obj}`evaluation.metrics.performance.evaluation_periods_per_year` · **Source:** [evaluation/metrics/performance.py:391](../../../../evaluation/metrics/performance.py#L391)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``evaluation_periods_per_year``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = evaluation_periods_per_year(config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `max_drawdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return peak-to-trough decline as a positive fraction.

**Exact API:** {py:obj}`evaluation.metrics.performance.max_drawdown` · **Source:** [evaluation/metrics/performance.py:209](../../../../evaluation/metrics/performance.py#L209)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Equity values ordered in time.
  ```

- **Returns:**

  ```text
  Largest relative decline from a running peak, in ``[0, 1]``.
  ```

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L353)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        # Callers may supply end-of-bar valuations without the opening capital.
        # Preserve an explicitly included opening balance, otherwise count the
        # first valuation's profit or loss in the return path and drawdown.
    path = curve if curve[0] == initial_balance else np.concatenate(([initial_balance], curve))
    returns = _bar_returns(path)
    mdd = max_drawdown(path)
    total_pnl = float(curve[-1] - initial_balance)
    # ``curve`` may either include the initial balance or contain only
    # end-of-bar valuations. ``returns`` always counts elapsed bar intervals,
    # so use it as the annualisation duration in both representations.
    years = returns.size / periods_per_year
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `sweep_delay_breakdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Summarise Sweep Delay and Asian-vs-London targeting from open trades.

**Exact API:** {py:obj}`evaluation.metrics.performance.sweep_delay_breakdown` · **Source:** [evaluation/metrics/performance.py:151](../../../../evaluation/metrics/performance.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: The environment's ``trade_log`` list.
  delay_key: Trade-log key holding the delay in seconds.
  level_key: Trade-log key holding the swept level name.
  ```

- **Returns:**

  ```text
  Dict with ``sweep_delay_mean_s``, ``sweep_delay_median_s``,
  ``n_entries``, ``london_pct`` and ``asian_pct`` (percent of
  entries attributed to London/Asian levels).
  ```

**Observed usage:**

1. [production caller: `build_run_report`](../../../../evaluation/reporting/run_summary.py#L226)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_run_report(
    metrics: PerformanceMetrics,
    trade_log: Sequence[dict[str, Any]] | None = None,
    **context: Any,
) -> dict[str, Any]:
    report: dict[str, Any] = asdict(metrics)
    report["activity_status"] = activity_status(metrics)
    report["sweep_delay"] = sweep_delay_breakdown(trade_log or [])
    report.update(context)
    return report
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
