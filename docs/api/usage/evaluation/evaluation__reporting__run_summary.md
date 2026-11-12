# Evaluation · `reporting.run_summary`

This page contains 12 public callable records owned by `evaluation.reporting.run_summary`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `aggregate_seeds`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Aggregate per-seed :class:`PerformanceMetrics` into a summary DataFrame.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.aggregate_seeds` · **Source:** [evaluation/reporting/run_summary.py:60](../../../../evaluation/reporting/run_summary.py#L60)

**Inputs and outputs:**

- **Args:**

  ```text
  results: One ``PerformanceMetrics`` instance per seed/run.
  ```

- **Returns:**

  ```text
  DataFrame with one row per seed and one column per metric.
  ```

- **Raises:**

  ```text
  ValueError: If *results* is empty or contains a non-metrics object.
  ```

**Observed usage:**

1. [test fixture: `test_one_row_per_seed`](../../../../tests/unit/evaluation/test_run_summary.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_one_row_per_seed(self) -> None:
    # Arrange
    results = [_metrics(100.0, 2), _metrics(-50.0, 3), _metrics(0.0, 0)]

    # Act
    df = aggregate_seeds(results)

    # Assert
    assert len(df) == 3
    assert list(df["seed"]) == [0, 1, 2]
    assert list(df["activity_status"]) == ["ACTIVE", "ACTIVE", "INACTIVE"]
    assert {"sharpe", "max_drawdown", "n_trades", "breach_rate"} <= set(df.columns)
```

2. [test fixture: `test_rejects_non_metrics`](../../../../tests/unit/evaluation/test_run_summary.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rejects_non_metrics(self) -> None:
    with pytest.raises(ValueError, match="PerformanceMetrics"):
        aggregate_seeds([{"sharpe": 1.0}])  # type: ignore[list-item]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_comparison_table`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Return a two-column Train vs Test comparison table.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_comparison_table` · **Source:** [evaluation/reporting/run_summary.py:294](../../../../evaluation/reporting/run_summary.py#L294)

**Inputs and outputs:**

- **Args:**

  ```text
  train_m: Train m used by the operation described above.
  test_m: Test m used by the operation described above.
  ```

- **Returns:**

  ```text
  Text returned by ``build_comparison_table``.
  ```

**Observed usage:**

1. [test fixture: `test_build_comparison_table`](../../../../tests/unit/evaluation/test_plots_export.py#L146)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_build_comparison_table(metrics):
    table = build_comparison_table(metrics, metrics)
    assert "Train" in table
    assert "Test" in table
    assert "Sharpe" in table
```

2. [test fixture: `test_comparison_table_train_and_test_columns`](../../../../tests/unit/evaluation/test_run_summary.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_comparison_table_train_and_test_columns(self) -> None:
    # Act
    table = build_comparison_table(_metrics(100.0, 2), _metrics(-30.0, 1))

    # Assert
    assert "Train" in table
    assert "Test" in table
    assert "Sharpe" in table
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_run_report`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Build the JSON-serialisable report block for one evaluation run.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_run_report` · **Source:** [evaluation/reporting/run_summary.py:359](../../../../evaluation/reporting/run_summary.py#L359)

**Inputs and outputs:**

- **Args:**

  ```text
  metrics: Metrics returned by :func:`run_episode`.
  trade_log: The environment's ``trade_log`` list, if available.
  **context: Extra key/value pairs merged into the report.
  ```

- **Returns:**

  ```text
  A dict safe to pass to ``json.dumps``.
  ```

**Observed usage:**

1. [test fixture: `test_zero_trade_metrics_are_labeled_inactive`](../../../../tests/unit/evaluation/test_run_summary.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_zero_trade_metrics_are_labeled_inactive(self, tmp_path: Path) -> None:
        metrics = _metrics(0.0, 0)
        table = build_summary_table(metrics)
        path = tmp_path / "inactive_metrics.json"
        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved_metrics = json.loads(path.read_text())

        assert "INACTIVE" in table
        assert saved_metrics["activity_status"] == "INACTIVE"
        assert report["activity_status"] == "INACTIVE"
# … caller assertions omitted …
```

2. [test fixture: `test_unbounded_profit_factor_uses_json_null_and_reason`](../../../../tests/unit/evaluation/test_run_summary.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_unbounded_profit_factor_uses_json_null_and_reason(self, tmp_path: Path) -> None:
        metrics = _metrics(100.0, 1)
        path = tmp_path / "unbounded_profit_factor.json"

        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved = json.loads(path.read_text())

        assert metrics.profit_factor == float("inf")
        assert saved["profit_factor"] is None
        assert saved["metric_availability"]["profit_factor"] == (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_summary_table`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Return a human-readable text table of a single PerformanceMetrics.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_summary_table` · **Source:** [evaluation/reporting/run_summary.py:273](../../../../evaluation/reporting/run_summary.py#L273)

**Inputs and outputs:**

- **Args:**

  ```text
  m: M used by the operation described above.
  ```

- **Returns:**

  ```text
  Text returned by ``build_summary_table``.
  ```

**Observed usage:**

1. [test fixture: `test_build_summary_table`](../../../../tests/unit/evaluation/test_plots_export.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_build_summary_table(metrics):
    table = build_summary_table(metrics)
    assert "Sharpe" in table
    assert "Max Drawdown" in table
    assert "Breached Session Rate" in table
```

2. [test fixture: `test_summary_table_contains_key_rows`](../../../../tests/unit/evaluation/test_run_summary.py#L55)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_summary_table_contains_key_rows(self) -> None:
        # Act
        table = build_summary_table(_metrics(150.0, 2))

        # Assert
        for label in (
            "Sharpe",
            "Max Drawdown",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `print_report`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Print a describe()-style summary of an aggregated seed DataFrame.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.print_report` · **Source:** [evaluation/reporting/run_summary.py:88](../../../../evaluation/reporting/run_summary.py#L88)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = print_report(df=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `save_metrics_json`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Persist metrics plus account endpoints when supplied by the evaluator.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.save_metrics_json` · **Source:** [evaluation/reporting/run_summary.py:336](../../../../evaluation/reporting/run_summary.py#L336)

**Inputs and outputs:**

- **Args:**

  ```text
  m: M used by the operation described above.
  path: Path to the input file or directory.
  initial_balance: Initial balance used by the operation described above.
  final_equity: Final equity used by the operation described above.
  ```

**Observed usage:**

1. [test fixture: `test_save_metrics_json`](../../../../tests/unit/evaluation/test_plots_export.py#L154)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_save_metrics_json(metrics, tmp_path):
    path = tmp_path / "metrics.json"
    save_metrics_json(metrics, path)
    data = json.loads(path.read_text())
    assert "sharpe" in data
    assert "total_pnl" in data
```

2. [test fixture: `test_save_metrics_json_roundtrip`](../../../../tests/unit/evaluation/test_run_summary.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_save_metrics_json_roundtrip(self, tmp_path: Path) -> None:
        # Arrange
        path = tmp_path / "metrics.json"

        # Act
        save_metrics_json(
            _metrics(120.0, 2),
            path,
            initial_balance=100_000.0,
            final_equity=100_120.0,
        )
        data = json.loads(path.read_text())

        # Assert
        assert data["n_trades"] == 2
        assert data["periods_per_year"] == 6048
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `aggregate_seeds`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Aggregate per-seed :class:`PerformanceMetrics` into a summary DataFrame.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.aggregate_seeds` · **Source:** [evaluation/reporting/run_summary.py:60](../../../../evaluation/reporting/run_summary.py#L60)

**Inputs and outputs:**

- **Args:**

  ```text
  results: One ``PerformanceMetrics`` instance per seed/run.
  ```

- **Returns:**

  ```text
  DataFrame with one row per seed and one column per metric.
  ```

- **Raises:**

  ```text
  ValueError: If *results* is empty or contains a non-metrics object.
  ```

**Observed usage:**

1. [test fixture: `test_one_row_per_seed`](../../../../tests/unit/evaluation/test_run_summary.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_one_row_per_seed(self) -> None:
    # Arrange
    results = [_metrics(100.0, 2), _metrics(-50.0, 3), _metrics(0.0, 0)]

    # Act
    df = aggregate_seeds(results)

    # Assert
    assert len(df) == 3
    assert list(df["seed"]) == [0, 1, 2]
    assert list(df["activity_status"]) == ["ACTIVE", "ACTIVE", "INACTIVE"]
    assert {"sharpe", "max_drawdown", "n_trades", "breach_rate"} <= set(df.columns)
```

2. [test fixture: `test_rejects_non_metrics`](../../../../tests/unit/evaluation/test_run_summary.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rejects_non_metrics(self) -> None:
    with pytest.raises(ValueError, match="PerformanceMetrics"):
        aggregate_seeds([{"sharpe": 1.0}])  # type: ignore[list-item]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_comparison_table`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Return a two-column Train vs Test comparison table.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_comparison_table` · **Source:** [evaluation/reporting/run_summary.py:294](../../../../evaluation/reporting/run_summary.py#L294)

**Inputs and outputs:**

- **Args:**

  ```text
  train_m: Train m used by the operation described above.
  test_m: Test m used by the operation described above.
  ```

- **Returns:**

  ```text
  Text returned by ``build_comparison_table``.
  ```

**Observed usage:**

1. [test fixture: `test_build_comparison_table`](../../../../tests/unit/evaluation/test_plots_export.py#L146)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_build_comparison_table(metrics):
    table = build_comparison_table(metrics, metrics)
    assert "Train" in table
    assert "Test" in table
    assert "Sharpe" in table
```

2. [test fixture: `test_comparison_table_train_and_test_columns`](../../../../tests/unit/evaluation/test_run_summary.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_comparison_table_train_and_test_columns(self) -> None:
    # Act
    table = build_comparison_table(_metrics(100.0, 2), _metrics(-30.0, 1))

    # Assert
    assert "Train" in table
    assert "Test" in table
    assert "Sharpe" in table
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_run_report`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Build the JSON-serialisable report block for one evaluation run.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_run_report` · **Source:** [evaluation/reporting/run_summary.py:359](../../../../evaluation/reporting/run_summary.py#L359)

**Inputs and outputs:**

- **Args:**

  ```text
  metrics: Metrics returned by :func:`run_episode`.
  trade_log: The environment's ``trade_log`` list, if available.
  **context: Extra key/value pairs merged into the report.
  ```

- **Returns:**

  ```text
  A dict safe to pass to ``json.dumps``.
  ```

**Observed usage:**

1. [test fixture: `test_zero_trade_metrics_are_labeled_inactive`](../../../../tests/unit/evaluation/test_run_summary.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_zero_trade_metrics_are_labeled_inactive(self, tmp_path: Path) -> None:
        metrics = _metrics(0.0, 0)
        table = build_summary_table(metrics)
        path = tmp_path / "inactive_metrics.json"
        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved_metrics = json.loads(path.read_text())

        assert "INACTIVE" in table
        assert saved_metrics["activity_status"] == "INACTIVE"
        assert report["activity_status"] == "INACTIVE"
# … caller assertions omitted …
```

2. [test fixture: `test_unbounded_profit_factor_uses_json_null_and_reason`](../../../../tests/unit/evaluation/test_run_summary.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_unbounded_profit_factor_uses_json_null_and_reason(self, tmp_path: Path) -> None:
        metrics = _metrics(100.0, 1)
        path = tmp_path / "unbounded_profit_factor.json"

        save_metrics_json(metrics, path)
        report = build_run_report(metrics)
        saved = json.loads(path.read_text())

        assert metrics.profit_factor == float("inf")
        assert saved["profit_factor"] is None
        assert saved["metric_availability"]["profit_factor"] == (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `build_summary_table`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Return a human-readable text table of a single PerformanceMetrics.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.build_summary_table` · **Source:** [evaluation/reporting/run_summary.py:273](../../../../evaluation/reporting/run_summary.py#L273)

**Inputs and outputs:**

- **Args:**

  ```text
  m: M used by the operation described above.
  ```

- **Returns:**

  ```text
  Text returned by ``build_summary_table``.
  ```

**Observed usage:**

1. [test fixture: `test_build_summary_table`](../../../../tests/unit/evaluation/test_plots_export.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_build_summary_table(metrics):
    table = build_summary_table(metrics)
    assert "Sharpe" in table
    assert "Max Drawdown" in table
    assert "Breached Session Rate" in table
```

2. [test fixture: `test_summary_table_contains_key_rows`](../../../../tests/unit/evaluation/test_run_summary.py#L55)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_summary_table_contains_key_rows(self) -> None:
        # Act
        table = build_summary_table(_metrics(150.0, 2))

        # Assert
        for label in (
            "Sharpe",
            "Max Drawdown",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `print_report`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Print a describe()-style summary of an aggregated seed DataFrame.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.print_report` · **Source:** [evaluation/reporting/run_summary.py:88](../../../../evaluation/reporting/run_summary.py#L88)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = print_report(df=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `save_metrics_json`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.run_summary`

**Purpose:** Persist metrics plus account endpoints when supplied by the evaluator.

**Exact API:** {py:obj}`evaluation.reporting.run_summary.save_metrics_json` · **Source:** [evaluation/reporting/run_summary.py:336](../../../../evaluation/reporting/run_summary.py#L336)

**Inputs and outputs:**

- **Args:**

  ```text
  m: M used by the operation described above.
  path: Path to the input file or directory.
  initial_balance: Initial balance used by the operation described above.
  final_equity: Final equity used by the operation described above.
  ```

**Observed usage:**

1. [test fixture: `test_save_metrics_json`](../../../../tests/unit/evaluation/test_plots_export.py#L154)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_save_metrics_json(metrics, tmp_path):
    path = tmp_path / "metrics.json"
    save_metrics_json(metrics, path)
    data = json.loads(path.read_text())
    assert "sharpe" in data
    assert "total_pnl" in data
```

2. [test fixture: `test_save_metrics_json_roundtrip`](../../../../tests/unit/evaluation/test_run_summary.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_save_metrics_json_roundtrip(self, tmp_path: Path) -> None:
        # Arrange
        path = tmp_path / "metrics.json"

        # Act
        save_metrics_json(
            _metrics(120.0, 2),
            path,
            initial_balance=100_000.0,
            final_equity=100_120.0,
        )
        data = json.loads(path.read_text())

        # Assert
        assert data["n_trades"] == 2
        assert data["periods_per_year"] == 6048
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
