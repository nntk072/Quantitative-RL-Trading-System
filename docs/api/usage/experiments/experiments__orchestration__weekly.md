# Experiments · `orchestration.weekly`

This page contains 6 public callable records owned by `experiments.orchestration.weekly`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `BatchSpec`

**Kind:** class · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Configuration shared by every run in one batch.

**Exact API:** {py:obj}`experiments.orchestration.weekly.BatchSpec` · **Source:** [experiments/orchestration/weekly.py:21](../../../../experiments/orchestration/weekly.py#L21)

**Observed usage:**

1. [test fixture: `test_weekly_layout_and_reports`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    def runner(run):
        (run.run_dir / "metrics.json").write_text('{"sharpe": 1.0}\n')
        return {"status": "completed", "metrics": {"sharpe": 1.0}}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        3, [BatchSpec(seeds=(1, 2), steps=8)]
    )
    assert (week / "batches/batch_1/report.md").is_file()
    assert (week / "report.md").is_file()
    manifest = json.loads((week / "manifest.json").read_text())
    runs = manifest["batches"][0]["runs"]
# … caller assertions omitted …
```

2. [test fixture: `test_failures_are_preserved_and_retried`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if attempts[run.strategy] == 1:
            raise RuntimeError("synthetic failure")
        return {"status": "completed"}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        4, [BatchSpec(strategies=("baseline",), seeds=(7,))], retries=1
    )
    runs = json.loads((week / "batches/batch_1/manifest.json").read_text())["runs"]
    assert [run["status"] for run in runs] == ["failed", "completed"]
    assert runs[1]["retry_of"] == runs[0]["run_id"]
    assert "failed" in (week / "batches/batch_1/report.md").read_text()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `RunSpec`

**Kind:** class · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Resolved run identity and comparability metadata.

**Exact API:** {py:obj}`experiments.orchestration.weekly.RunSpec` · **Source:** [experiments/orchestration/weekly.py:36](../../../../experiments/orchestration/weekly.py#L36)

**Observed usage:**

1. [production caller: `_run_batch`](../../../../experiments/orchestration/weekly.py#L230)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                previous: str | None = None
                for attempt in range(retries + 1):
                    run_id = self._run_id(strategy, seed, attempt, batch_dir)
                    run_dir = batch_dir / run_id
                    run_dir.mkdir()
                    run = RunSpec(
                        week,
                        number,
                        run_id,
                        strategy,
                        seed,
                        spec.steps,
                        run_dir,
                        comparable,
                        previous,
                        spec.config,
                    )
                    record = {**asdict(run), "run_dir": str(run_dir), "status": "running"}
                    record["comparability_key"] = manifest["comparability_key"]
                    _json_dump(run_dir / "metadata.json", record)
                    try:
                        result = (self.runner or self._default_runner)(run)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `WeeklyOrchestrator`

**Kind:** class · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Execute a matrix while preserving evidence for failures and retries.

**Exact API:** {py:obj}`experiments.orchestration.weekly.WeeklyOrchestrator` · **Source:** [experiments/orchestration/weekly.py:167](../../../../experiments/orchestration/weekly.py#L167)

**Observed usage:**

1. [test fixture: `test_weekly_layout_and_reports`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_weekly_layout_and_reports(tmp_path: Path) -> None:
    def runner(run):
        (run.run_dir / "metrics.json").write_text('{"sharpe": 1.0}\n')
        return {"status": "completed", "metrics": {"sharpe": 1.0}}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        3, [BatchSpec(seeds=(1, 2), steps=8)]
    )
    assert (week / "batches/batch_1/report.md").is_file()
    assert (week / "report.md").is_file()
    manifest = json.loads((week / "manifest.json").read_text())
# … caller assertions omitted …
```

2. [test fixture: `test_failures_are_preserved_and_retried`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        attempts[run.strategy] = attempts.get(run.strategy, 0) + 1
        if attempts[run.strategy] == 1:
            raise RuntimeError("synthetic failure")
        return {"status": "completed"}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        4, [BatchSpec(strategies=("baseline",), seeds=(7,))], retries=1
    )
    runs = json.loads((week / "batches/batch_1/manifest.json").read_text())["runs"]
    assert [run["status"] for run in runs] == ["failed", "completed"]
    assert runs[1]["retry_of"] == runs[0]["run_id"]
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `render_batch_report`

**Kind:** function · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Render a Markdown report retaining successful and failed runs.

**Exact API:** {py:obj}`experiments.orchestration.weekly.render_batch_report` · **Source:** [experiments/orchestration/weekly.py:105](../../../../experiments/orchestration/weekly.py#L105)

**Inputs and outputs:**

- **Args:**

  ```text
  batch_dir: Text or path value identifying the batch dir.
  manifest: Key-value data used for the manifest.
  ```

- **Returns:**

  ```text
  Text returned by ``render_batch_report``.
  ```

**Observed usage:**

1. [production caller: `_run_batch`](../../../../experiments/orchestration/weekly.py#L258)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    previous = run_id
                    if record["status"] != "failed":
                        break
        manifest["incomparable_reasons"] = self._incomparable_reasons(manifest["runs"])
        _json_dump(batch_dir / "manifest.json", manifest)
        (batch_dir / "report.md").write_text(render_batch_report(batch_dir, manifest))
        self._batches.append(manifest)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `render_weekly_report`

**Kind:** function · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Render a weekly index linking every batch and run.

**Exact API:** {py:obj}`experiments.orchestration.weekly.render_weekly_report` · **Source:** [experiments/orchestration/weekly.py:130](../../../../experiments/orchestration/weekly.py#L130)

**Inputs and outputs:**

- **Args:**

  ```text
  week_dir: Text or path value identifying the week dir.
  batches: Batches to process, in order.
  ```

- **Returns:**

  ```text
  Text returned by ``render_weekly_report``.
  ```

**Observed usage:**

1. [production caller: `run_week`](../../../../experiments/orchestration/weekly.py#L192)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def run_week(self, week: int, batches: Iterable[BatchSpec], *, retries: int = 0) -> Path:
    week_dir = self.output_root / f"week_{week}"
    (week_dir / "batches").mkdir(parents=True, exist_ok=True)
    self._batches = []
    for batch_number, spec in enumerate(batches, start=1):
        self._run_batch(week, batch_number, spec, week_dir, retries)
    _json_dump(week_dir / "manifest.json", {"week": week, "batches": self._batches})
    (week_dir / "report.md").write_text(render_weekly_report(week_dir, self._batches))
    return week_dir
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `WeeklyOrchestrator.run_week`

**Kind:** method · **Status:** stable · **Owner:** `experiments.orchestration.weekly`

**Purpose:** Execute all batches and write weekly and batch manifests.

**Exact API:** {py:obj}`experiments.orchestration.weekly.WeeklyOrchestrator.run_week` · **Source:** [experiments/orchestration/weekly.py:175](../../../../experiments/orchestration/weekly.py#L175)

**Inputs and outputs:**

- **Args:**

  ```text
  week: Numeric value used for the week.
  batches: Batches to process, in order.
  retries: Numeric value used for the retries.
  ```

- **Returns:**

  ```text
  Path returned by ``run_week``.
  ```

**Observed usage:**

1. [test fixture: `test_weekly_layout_and_reports`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_weekly_layout_and_reports(tmp_path: Path) -> None:
    def runner(run):
        (run.run_dir / "metrics.json").write_text('{"sharpe": 1.0}\n')
        return {"status": "completed", "metrics": {"sharpe": 1.0}}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        3, [BatchSpec(seeds=(1, 2), steps=8)]
    )
    assert (week / "batches/batch_1/report.md").is_file()
    assert (week / "report.md").is_file()
    manifest = json.loads((week / "manifest.json").read_text())
    runs = manifest["batches"][0]["runs"]
    assert len(runs) == 6
# … caller assertions omitted …
```

2. [test fixture: `test_failures_are_preserved_and_retried`](../../../../tests/unit/experiments/test_orchestration_weekly.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        attempts[run.strategy] = attempts.get(run.strategy, 0) + 1
        if attempts[run.strategy] == 1:
            raise RuntimeError("synthetic failure")
        return {"status": "completed"}

    week = WeeklyOrchestrator(tmp_path, runner=runner).run_week(
        4, [BatchSpec(strategies=("baseline",), seeds=(7,))], retries=1
    )
    runs = json.loads((week / "batches/batch_1/manifest.json").read_text())["runs"]
    assert [run["status"] for run in runs] == ["failed", "completed"]
    assert runs[1]["retry_of"] == runs[0]["run_id"]
    assert "failed" in (week / "batches/batch_1/report.md").read_text()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
