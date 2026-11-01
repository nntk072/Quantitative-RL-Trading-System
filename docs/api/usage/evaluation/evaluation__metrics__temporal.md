# Evaluation · `metrics.temporal`

This page contains 4 public callable records owned by `evaluation.metrics.temporal`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `conditional_pnl_distributions`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.temporal`

**Purpose:** Compute PnL distributions grouped by strategy regime.

**Exact API:** {py:obj}`evaluation.metrics.temporal.conditional_pnl_distributions` · **Source:** [evaluation/metrics/temporal.py:157](../../../../evaluation/metrics/temporal.py#L157)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: Environment trade log.
  ```

- **Returns:**

  ```text
  Mapping from group name to its PnL distribution metrics.
  ```

**Observed usage:**

1. [production caller: `write_distribution_artifacts`](../../../../evaluation/plotting/distribution_plots.py#L202)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    split_dir = Path(split_dir)
    split_dir.mkdir(parents=True, exist_ok=True)

    groups = conditional_pnl_groups(trades)
    group_metrics = conditional_pnl_distributions(trades)
    overall = group_metrics["overall"]
    hold = holding_time_distribution(trades)
    sweep = sweep_delay_distribution(trades)

    payload: dict[str, Any] = {
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `conditional_pnl_groups`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.temporal`

**Purpose:** Return raw PnL lists grouped by regime for box plots.

**Exact API:** {py:obj}`evaluation.metrics.temporal.conditional_pnl_groups` · **Source:** [evaluation/metrics/temporal.py:136](../../../../evaluation/metrics/temporal.py#L136)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: Tabular data used for the trade log.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``list[float]`` values.
  ```

**Observed usage:**

1. [production caller: `conditional_pnl_distributions`](../../../../evaluation/metrics/temporal.py#L171)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def conditional_pnl_distributions(
    trade_log: list[dict[str, Any]] | pd.DataFrame,
) -> dict[str, DistributionMetrics]:
    groups = conditional_pnl_groups(trade_log)
    return {name: compute_distribution_metrics(vals) for name, vals in groups.items()}
```

2. [production caller: `write_distribution_artifacts`](../../../../evaluation/plotting/distribution_plots.py#L201)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    split_dir = Path(split_dir)
    split_dir.mkdir(parents=True, exist_ok=True)

    groups = conditional_pnl_groups(trades)
    group_metrics = conditional_pnl_distributions(trades)
    overall = group_metrics["overall"]
    hold = holding_time_distribution(trades)
    sweep = sweep_delay_distribution(trades)

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `holding_time_distribution`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.temporal`

**Purpose:** Compute the distribution of per-trade holding times in seconds.

**Exact API:** {py:obj}`evaluation.metrics.temporal.holding_time_distribution` · **Source:** [evaluation/metrics/temporal.py:63](../../../../evaluation/metrics/temporal.py#L63)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: Environment trade log with ``time`` and ``type`` keys.
  ```

- **Returns:**

  ```text
  Distribution metrics over holding seconds; count=0 / NaN fields
  when no completed trades are paired.
  ```

**Observed usage:**

1. [production caller: `write_distribution_artifacts`](../../../../evaluation/plotting/distribution_plots.py#L204)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    split_dir.mkdir(parents=True, exist_ok=True)

    groups = conditional_pnl_groups(trades)
    group_metrics = conditional_pnl_distributions(trades)
    overall = group_metrics["overall"]
    hold = holding_time_distribution(trades)
    sweep = sweep_delay_distribution(trades)

    payload: dict[str, Any] = {
        "pnl": {k: asdict(v) for k, v in group_metrics.items()},
        "holding_time_s": asdict(hold),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `sweep_delay_distribution`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.metrics.temporal`

**Purpose:** Compute the distribution of entry sweep delays in seconds.

**Exact API:** {py:obj}`evaluation.metrics.temporal.sweep_delay_distribution` · **Source:** [evaluation/metrics/temporal.py:88](../../../../evaluation/metrics/temporal.py#L88)

**Inputs and outputs:**

- **Args:**

  ```text
  trade_log: Environment trade log with ``sweep_delay_s`` on opens.
  ```

- **Returns:**

  ```text
  Distribution over finite ``sweep_delay_s`` values.
  ```

**Observed usage:**

1. [production caller: `write_distribution_artifacts`](../../../../evaluation/plotting/distribution_plots.py#L205)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    groups = conditional_pnl_groups(trades)
    group_metrics = conditional_pnl_distributions(trades)
    overall = group_metrics["overall"]
    hold = holding_time_distribution(trades)
    sweep = sweep_delay_distribution(trades)

    payload: dict[str, Any] = {
        "pnl": {k: asdict(v) for k, v in group_metrics.items()},
        "holding_time_s": asdict(hold),
        "sweep_delay_s": asdict(sweep),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
