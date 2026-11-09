# Evaluation · `metrics.performance`

This page contains 14 public callable records owned by `evaluation.metrics.performance`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PerformanceMetrics`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Aggregate returns, trade statistics, and risk-breach measures for a run.

**Exact API:** {py:obj}`evaluation.metrics.performance.PerformanceMetrics` · **Source:** [evaluation/metrics/performance.py:54](../../../../evaluation/metrics/performance.py#L54)

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L722)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        breach_count=breach_count,
        completed_data_split=completed_data_split,
    )

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
        breach_event_count=breach_event_count,
        breach_event_count_availability=breach_event_count_availability,
        breach_session_count=breach_session_count,
        breach_rate=(
            breach_session_count / n_sessions
            if breach_session_count is not None and n_sessions > 0
            else None
        ),
        breach_rate_availability=breach_rate_availability,
        turnover=float(pnls.size / curve.size) if curve.size else 0.0,
        max_consec_loss=_max_consec_loss(pnls),
        avg_trade=stats["expectancy"],
        **path_metrics,
        periods_per_year=periods_per_year,
        metric_definition_version=METRIC_DEFINITION_VERSION,
        extras=dict(extras or {}),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `account_path_metric_inputs`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return only complete, typed account-path evidence for metric calculation.

**Exact API:** {py:obj}`evaluation.metrics.performance.account_path_metric_inputs` · **Source:** [evaluation/metrics/performance.py:785](../../../../evaluation/metrics/performance.py#L785)

**Inputs and outputs:**

- **Args:**

  ```text
  result: Evaluation result containing account trace and breach evidence.
  ```

- **Returns:**

  ```text
  Validated trace, breach events, and completion flag for metric calculation.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = account_path_metric_inputs(result=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `calculate_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Pandas-friendly adapter matching the legacy ``eval.metrics`` signature.

**Exact API:** {py:obj}`evaluation.metrics.performance.calculate_metrics` · **Source:** [evaluation/metrics/performance.py:814](../../../../evaluation/metrics/performance.py#L814)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Bar-level equity curve (``pd.Series`` or sequence).
  trades: Trade records or lifecycle event ledger (typically a ``pd.DataFrame``), or None.
  n_sessions: Number of trading sessions, for ``breach_rate``.
  n_breach_sessions: Sessions in which a guardrail breach occurred.
  periods_per_year: Bars per year for annualisation.  Defaults to M1
      bars (``252 * 390``) to match the legacy evaluation runs.
  initial_balance: Account balance before the first bar.  When ``None``,
      the first value of the equity curve is used as the initial balance.
  account_state_trace: Complete per-step account snapshot DataFrame or
      sequence, when available.
  breach_events: Ordered hard-breach records from the evaluation.
  completed_data_split: Whether evaluation reached the declared split end.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

**Observed usage:**

1. [test fixture: `test_model_choice_probabilities_survive_rollout_and_artifact_export`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L262)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        trade_setup_actions=True,
    )
    run_dir = save_run(
        run_dir=tmp_path / "model-choice-trace",
        train_result=result,
        train_metrics=calculate_metrics(
            result["equity"],
            trades=result["trades"],
            initial_balance=100_000.0,
        ),
        train_bars=bars,
        save_plots=False,
        save_html=False,
        save_csv=True,
        report_profile="experiment_run_fast",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `compute_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Compute the standard metric set for one evaluation run.

**Exact API:** {py:obj}`evaluation.metrics.performance.compute_metrics` · **Source:** [evaluation/metrics/performance.py:553](../../../../evaluation/metrics/performance.py#L553)

**Inputs and outputs:**

- **Args:**

  ```text
  equity_curve: Equity after each bar, starting at ``initial_balance``.
  initial_balance: Account balance before the first bar.
  trade_pnls: Per-trade PnL of closed trades, if available.
  periods_per_year: Bars per year used to annualise ratios.
  breach_count: Caller-supplied breach count retained for compatibility.
  n_sessions: Number of trading sessions in the run; used for
      ``breach_rate`` (fraction of sessions with a breach).
  n_breach_sessions: Number of distinct sessions containing a breach.
      If omitted, it is derived from ``breach_events`` when available.
  extras: Caller-specific metrics (e.g. sweep delay) merged into output.
  account_state_trace: Complete per-step account snapshots, when retained.
      Supplied session IDs and opening equity define daily returns.
  breach_events: Ordered hard-breach events, used to measure observed
      time-to-ruin or right-censor a surviving path.
  completed_data_split: Whether evaluation reached the declared split end;
      required before including its final partial session return.
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

2. [production caller: `calculate_metrics`](../../../../evaluation/metrics/performance.py#L888)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        elif isinstance(account_state_trace, Sequence) and not isinstance(
            account_state_trace, (str, bytes)
        ):
            trace_records = account_state_trace

    return compute_metrics(
        curve,
        initial_balance=init_bal,
        trade_pnls=trade_pnls,
        periods_per_year=periods_per_year,
        breach_count=n_breach_sessions if n_breach_sessions is not None else 0,
        n_sessions=n_sessions,
        n_breach_sessions=n_breach_sessions,
        account_state_trace=trace_records,
        breach_events=breach_events,
        completed_data_split=completed_data_split,
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

**Exact API:** {py:obj}`evaluation.metrics.performance.evaluation_periods_per_year` · **Source:** [evaluation/metrics/performance.py:759](../../../../evaluation/metrics/performance.py#L759)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``evaluation_periods_per_year``.
  ```

**Observed usage:**

1. [production caller: `_paired_interval_record`](../../../../evaluation/reporting/matched_setup_baseline_bundle.py#L314)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    intervals = paired_equity_metric_differences(
        equity,
        control_equity,
        initial_balance=float(account["initial_balance"]),
        periods_per_year=evaluation_periods_per_year(resolved_cfg),
        n_boot=int(treatment_protocol.get("n_boot", 2000)),
        level=float(treatment_protocol.get("level", 0.95)),
        rng_seed=int(treatment_protocol.get("seed", 42)),
        block_len=int(treatment_protocol.get("block_length_bars", 8)),
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `max_drawdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return peak-to-trough decline as a positive fraction.

**Exact API:** {py:obj}`evaluation.metrics.performance.max_drawdown` · **Source:** [evaluation/metrics/performance.py:450](../../../../evaluation/metrics/performance.py#L450)

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

1. [production caller: `max_drawdown_stat`](../../../../evaluation/metrics/bootstrap.py#L236)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def max_drawdown_stat(equity: NDArray[np.float64]) -> float:
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size == 0:
        return float("nan")
    return max_drawdown(eq)
```

2. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L686)

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

**Exact API:** {py:obj}`evaluation.metrics.performance.sweep_delay_breakdown` · **Source:** [evaluation/metrics/performance.py:217](../../../../evaluation/metrics/performance.py#L217)

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
  entries attributed to London/Asian levels). Delay statistics are
  ``None`` when no finite delay was observed; level percentages are
  ``None`` when no entry was attributed to either level family.
  ```

**Observed usage:**

1. [production caller: `build_run_report`](../../../../evaluation/reporting/run_summary.py#L381)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_run_report(
    metrics: PerformanceMetrics,
    trade_log: Sequence[dict[str, Any]] | None = None,
    **context: Any,
) -> dict[str, Any]:
    report = performance_metrics_payload(metrics)
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

**Exact API:** {py:obj}`evaluation.metrics.performance.PerformanceMetrics` · **Source:** [evaluation/metrics/performance.py:54](../../../../evaluation/metrics/performance.py#L54)

**Observed usage:**

1. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L722)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        breach_count=breach_count,
        completed_data_split=completed_data_split,
    )

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
        breach_event_count=breach_event_count,
        breach_event_count_availability=breach_event_count_availability,
        breach_session_count=breach_session_count,
        breach_rate=(
            breach_session_count / n_sessions
            if breach_session_count is not None and n_sessions > 0
            else None
        ),
        breach_rate_availability=breach_rate_availability,
        turnover=float(pnls.size / curve.size) if curve.size else 0.0,
        max_consec_loss=_max_consec_loss(pnls),
        avg_trade=stats["expectancy"],
        **path_metrics,
        periods_per_year=periods_per_year,
        metric_definition_version=METRIC_DEFINITION_VERSION,
        extras=dict(extras or {}),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `account_path_metric_inputs`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return only complete, typed account-path evidence for metric calculation.

**Exact API:** {py:obj}`evaluation.metrics.performance.account_path_metric_inputs` · **Source:** [evaluation/metrics/performance.py:785](../../../../evaluation/metrics/performance.py#L785)

**Inputs and outputs:**

- **Args:**

  ```text
  result: Evaluation result containing account trace and breach evidence.
  ```

- **Returns:**

  ```text
  Validated trace, breach events, and completion flag for metric calculation.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = account_path_metric_inputs(result=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `calculate_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Pandas-friendly adapter matching the legacy ``eval.metrics`` signature.

**Exact API:** {py:obj}`evaluation.metrics.performance.calculate_metrics` · **Source:** [evaluation/metrics/performance.py:814](../../../../evaluation/metrics/performance.py#L814)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Bar-level equity curve (``pd.Series`` or sequence).
  trades: Trade records or lifecycle event ledger (typically a ``pd.DataFrame``), or None.
  n_sessions: Number of trading sessions, for ``breach_rate``.
  n_breach_sessions: Sessions in which a guardrail breach occurred.
  periods_per_year: Bars per year for annualisation.  Defaults to M1
      bars (``252 * 390``) to match the legacy evaluation runs.
  initial_balance: Account balance before the first bar.  When ``None``,
      the first value of the equity curve is used as the initial balance.
  account_state_trace: Complete per-step account snapshot DataFrame or
      sequence, when available.
  breach_events: Ordered hard-breach records from the evaluation.
  completed_data_split: Whether evaluation reached the declared split end.
  ```

- **Returns:**

  ```text
  A frozen :class:`PerformanceMetrics` instance.
  ```

**Observed usage:**

1. [test fixture: `test_model_choice_probabilities_survive_rollout_and_artifact_export`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L262)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        trade_setup_actions=True,
    )
    run_dir = save_run(
        run_dir=tmp_path / "model-choice-trace",
        train_result=result,
        train_metrics=calculate_metrics(
            result["equity"],
            trades=result["trades"],
            initial_balance=100_000.0,
        ),
        train_bars=bars,
        save_plots=False,
        save_html=False,
        save_csv=True,
        report_profile="experiment_run_fast",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `compute_metrics`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Compute the standard metric set for one evaluation run.

**Exact API:** {py:obj}`evaluation.metrics.performance.compute_metrics` · **Source:** [evaluation/metrics/performance.py:553](../../../../evaluation/metrics/performance.py#L553)

**Inputs and outputs:**

- **Args:**

  ```text
  equity_curve: Equity after each bar, starting at ``initial_balance``.
  initial_balance: Account balance before the first bar.
  trade_pnls: Per-trade PnL of closed trades, if available.
  periods_per_year: Bars per year used to annualise ratios.
  breach_count: Caller-supplied breach count retained for compatibility.
  n_sessions: Number of trading sessions in the run; used for
      ``breach_rate`` (fraction of sessions with a breach).
  n_breach_sessions: Number of distinct sessions containing a breach.
      If omitted, it is derived from ``breach_events`` when available.
  extras: Caller-specific metrics (e.g. sweep delay) merged into output.
  account_state_trace: Complete per-step account snapshots, when retained.
      Supplied session IDs and opening equity define daily returns.
  breach_events: Ordered hard-breach events, used to measure observed
      time-to-ruin or right-censor a surviving path.
  completed_data_split: Whether evaluation reached the declared split end;
      required before including its final partial session return.
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

2. [production caller: `calculate_metrics`](../../../../evaluation/metrics/performance.py#L888)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        elif isinstance(account_state_trace, Sequence) and not isinstance(
            account_state_trace, (str, bytes)
        ):
            trace_records = account_state_trace

    return compute_metrics(
        curve,
        initial_balance=init_bal,
        trade_pnls=trade_pnls,
        periods_per_year=periods_per_year,
        breach_count=n_breach_sessions if n_breach_sessions is not None else 0,
        n_sessions=n_sessions,
        n_breach_sessions=n_breach_sessions,
        account_state_trace=trace_records,
        breach_events=breach_events,
        completed_data_split=completed_data_split,
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

**Exact API:** {py:obj}`evaluation.metrics.performance.evaluation_periods_per_year` · **Source:** [evaluation/metrics/performance.py:759](../../../../evaluation/metrics/performance.py#L759)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``evaluation_periods_per_year``.
  ```

**Observed usage:**

1. [production caller: `_paired_interval_record`](../../../../evaluation/reporting/matched_setup_baseline_bundle.py#L314)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    intervals = paired_equity_metric_differences(
        equity,
        control_equity,
        initial_balance=float(account["initial_balance"]),
        periods_per_year=evaluation_periods_per_year(resolved_cfg),
        n_boot=int(treatment_protocol.get("n_boot", 2000)),
        level=float(treatment_protocol.get("level", 0.95)),
        rng_seed=int(treatment_protocol.get("seed", 42)),
        block_len=int(treatment_protocol.get("block_length_bars", 8)),
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `max_drawdown`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.performance`

**Purpose:** Return peak-to-trough decline as a positive fraction.

**Exact API:** {py:obj}`evaluation.metrics.performance.max_drawdown` · **Source:** [evaluation/metrics/performance.py:450](../../../../evaluation/metrics/performance.py#L450)

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

1. [production caller: `max_drawdown_stat`](../../../../evaluation/metrics/bootstrap.py#L236)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def max_drawdown_stat(equity: NDArray[np.float64]) -> float:
    eq = np.asarray(equity, dtype=np.float64)
    if eq.size == 0:
        return float("nan")
    return max_drawdown(eq)
```

2. [production caller: `compute_metrics`](../../../../evaluation/metrics/performance.py#L686)

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

**Exact API:** {py:obj}`evaluation.metrics.performance.sweep_delay_breakdown` · **Source:** [evaluation/metrics/performance.py:217](../../../../evaluation/metrics/performance.py#L217)

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
  entries attributed to London/Asian levels). Delay statistics are
  ``None`` when no finite delay was observed; level percentages are
  ``None`` when no entry was attributed to either level family.
  ```

**Observed usage:**

1. [production caller: `build_run_report`](../../../../evaluation/reporting/run_summary.py#L381)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_run_report(
    metrics: PerformanceMetrics,
    trade_log: Sequence[dict[str, Any]] | None = None,
    **context: Any,
) -> dict[str, Any]:
    report = performance_metrics_payload(metrics)
    report["sweep_delay"] = sweep_delay_breakdown(trade_log or [])
    report.update(context)
    return report
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
