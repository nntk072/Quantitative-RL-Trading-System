# Artifacts · `layout`

This page contains 32 public callable records owned by `artifacts.layout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ArtifactLayout`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve canonical paths for run, evaluation, research, and report artifacts.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout` · **Source:** [artifacts/layout.py:27](../../../../artifacts/layout.py#L27)

**Observed usage:**

1. [test fixture: `test_timestamped_run_path_keeps_existing_layout_without_creating_directory`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timestamped_run_path_keeps_existing_layout_without_creating_directory(
    tmp_path: Path,
) -> None:
    layout = ArtifactLayout(tmp_path)
    timestamp = datetime(2026, 10, 30, 12, 31, 44, 123456)

    run_path = layout.timestamped_run("rl_train_seed42_tcn", timestamp=timestamp)

    assert run_path == tmp_path / "20261030_123144_123456_rl_train_seed42_tcn"
    assert not run_path.exists()
```

2. [test fixture: `test_artifact_layout_rejects_path_components`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L64)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_artifact_layout_rejects_path_components(
    tmp_path: Path, builder: str, value: str, label: str
) -> None:
    layout = ArtifactLayout(tmp_path)

    with pytest.raises(ValueError, match=f"unsafe {label}"):
        getattr(layout, builder)(value)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Named artifact paths for an experiment run, preserving its established on-disk layout.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout` · **Source:** [artifacts/layout.py:129](../../../../artifacts/layout.py#L129)

**Observed usage:**

1. [production caller: `gpu_experiment_run`](../../../../artifacts/layout.py#L98)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def gpu_experiment_run(self, experiment_run_id: str) -> ExperimentRunArtifactLayout:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", experiment_run_id):
        raise ValueError(f"unsafe experiment run id: {experiment_run_id!r}")
    return ExperimentRunArtifactLayout(self.root / "gpu_experiment_runs" / experiment_run_id)
```

2. [production caller: `resolve_handoff`](../../../../compute/slurm/continuation.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        not isinstance(handoff, dict)
        or handoff.get("schema") != "aalto.experiment_run_continuation_handoff.v1"
    ):
        raise ValueError("unsupported experiment run continuation handoff schema")
    source_manifest = json.loads(
        ExperimentRunArtifactLayout(source_experiment_run).manifest.read_text(encoding="utf-8")
    )
    if handoff.get("source_experiment_run_id") != source_experiment_run.name or handoff.get(
        "source_experiment_run_fingerprint"
    ) != source_manifest.get("fingerprint"):
        raise ValueError(
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.evaluation`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the directory for one evaluation result.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.evaluation` · **Source:** [artifacts/layout.py:100](../../../../artifacts/layout.py#L100)

**Inputs and outputs:**

- **Args:**

  ```text
  evaluation_id: Safe evaluation identifier.
  ```

- **Returns:**

  ```text
  The evaluation artifact directory.
  ```

**Observed usage:**

1. [test fixture: `test_artifact_layout_keeps_safe_run_namespaces`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_artifact_layout_keeps_safe_run_namespaces(tmp_path: Path) -> None:
    layout = ArtifactLayout(tmp_path)

    assert layout.run("run_seed42_tcn") == tmp_path / "runs" / "run_seed42_tcn"
    assert layout.experiment_run("experiment-run-20261030") == (
        tmp_path / "experiment_runs" / "experiment-run-20261030"
    )
    assert layout.evaluation("checkpoint-replay.v1") == (
        tmp_path / "evaluation" / "checkpoint-replay.v1"
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.experiment_run`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve one named experiment-run directory.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.experiment_run` · **Source:** [artifacts/layout.py:74](../../../../artifacts/layout.py#L74)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment_run_id: Safe identifier assigned to the experiment run.
  ```

- **Returns:**

  ```text
  The directory holding that experiment run.
  ```

**Observed usage:**

1. [test fixture: `test_artifact_layout_keeps_safe_run_namespaces`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_artifact_layout_keeps_safe_run_namespaces(tmp_path: Path) -> None:
    layout = ArtifactLayout(tmp_path)

    assert layout.run("run_seed42_tcn") == tmp_path / "runs" / "run_seed42_tcn"
    assert layout.experiment_run("experiment-run-20261030") == (
        tmp_path / "experiment_runs" / "experiment-run-20261030"
    )
    assert layout.evaluation("checkpoint-replay.v1") == (
        tmp_path / "evaluation" / "checkpoint-replay.v1"
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.experiment_runs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the root directory for experiment-run artifacts.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.experiment_runs` · **Source:** [artifacts/layout.py:66](../../../../artifacts/layout.py#L66)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``experiment_runs``.
  ```

**Observed usage:**

1. [production caller: `experiment_run`](../../../../artifacts/layout.py#L83)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def experiment_run(self, experiment_run_id: str) -> Path:
    return self.experiment_runs() / _validate_layout_component(
        experiment_run_id, "experiment run id"
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.gpu_experiment_run`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the established GPU experiment run path through the artifact layout.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.gpu_experiment_run` · **Source:** [artifacts/layout.py:87](../../../../artifacts/layout.py#L87)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment_run_id: Text or path value identifying the experiment run id.
  ```

- **Returns:**

  ```text
  Result of resolve the established GPU experiment run path through the artifact layout.
  ```

**Observed usage:**

1. [test fixture: `test_gpu_experiment_run_layout_preserves_existing_paths_and_names_artifact_roles`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L85)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_gpu_experiment_run_layout_preserves_existing_paths_and_names_artifact_roles(
    tmp_path: Path,
) -> None:
    artifacts = ArtifactLayout(tmp_path).gpu_experiment_run("matrix-20261030")

    assert artifacts.root == tmp_path / "gpu_experiment_runs" / "matrix-20261030"
    assert artifacts.manifest == artifacts.root / "experiment_run.json"
    assert artifacts.worker_log("variant__seed42", 2) == (
        artifacts.root / "logs" / "workers" / "variant__seed42__attempt2.log"
# … caller assertions omitted …
```

2. [test fixture: `test_experiment_run_layout_rejects_unsafe_experiment_run_ids`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L115)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_experiment_run_layout_rejects_unsafe_experiment_run_ids(
    tmp_path: Path, experiment_run_id: str
) -> None:
    with pytest.raises(ValueError, match="unsafe experiment run id"):
        ArtifactLayout(tmp_path).gpu_experiment_run(experiment_run_id)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.reports`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory reserved for generated reports.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.reports` · **Source:** [artifacts/layout.py:119](../../../../artifacts/layout.py#L119)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``reports``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ArtifactLayout(...)
result = instance.reports()
```

**Lifecycle context:** This callable participates in `ArtifactLayout`: Resolve canonical paths for run, evaluation, research, and report artifacts. Related public lifecycle methods: {py:obj}`artifacts.layout.ArtifactLayout.runs`, {py:obj}`artifacts.layout.ArtifactLayout.run`, {py:obj}`artifacts.layout.ArtifactLayout.timestamped_run`, {py:obj}`artifacts.layout.ArtifactLayout.experiment_runs`, {py:obj}`artifacts.layout.ArtifactLayout.experiment_run`, {py:obj}`artifacts.layout.ArtifactLayout.gpu_experiment_run`, {py:obj}`artifacts.layout.ArtifactLayout.evaluation`, {py:obj}`artifacts.layout.ArtifactLayout.research`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.research`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory reserved for research artifacts.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.research` · **Source:** [artifacts/layout.py:111](../../../../artifacts/layout.py#L111)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``research``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ArtifactLayout(...)
result = instance.research()
```

**Lifecycle context:** This callable participates in `ArtifactLayout`: Resolve canonical paths for run, evaluation, research, and report artifacts. Related public lifecycle methods: {py:obj}`artifacts.layout.ArtifactLayout.runs`, {py:obj}`artifacts.layout.ArtifactLayout.run`, {py:obj}`artifacts.layout.ArtifactLayout.timestamped_run`, {py:obj}`artifacts.layout.ArtifactLayout.experiment_runs`, {py:obj}`artifacts.layout.ArtifactLayout.experiment_run`, {py:obj}`artifacts.layout.ArtifactLayout.gpu_experiment_run`, {py:obj}`artifacts.layout.ArtifactLayout.evaluation`, {py:obj}`artifacts.layout.ArtifactLayout.research`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.run`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the directory for one run without creating it.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.run` · **Source:** [artifacts/layout.py:40](../../../../artifacts/layout.py#L40)

**Inputs and outputs:**

- **Args:**

  ```text
  run_id: Safe path component identifying the run.
  ```

- **Returns:**

  ```text
  The run artifact directory.
  ```

**Observed usage:**

1. [test fixture: `test_artifact_layout_keeps_safe_run_namespaces`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_artifact_layout_keeps_safe_run_namespaces(tmp_path: Path) -> None:
    layout = ArtifactLayout(tmp_path)

    assert layout.run("run_seed42_tcn") == tmp_path / "runs" / "run_seed42_tcn"
    assert layout.experiment_run("experiment-run-20261030") == (
        tmp_path / "experiment_runs" / "experiment-run-20261030"
    )
    assert layout.evaluation("checkpoint-replay.v1") == (
        tmp_path / "evaluation" / "checkpoint-replay.v1"
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.runs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing ordinary run artifacts.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.runs` · **Source:** [artifacts/layout.py:32](../../../../artifacts/layout.py#L32)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``runs``.
  ```

**Observed usage:**

1. [production caller: `run`](../../../../artifacts/layout.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def run(self, run_id: str) -> Path:
    return self.runs() / _validate_layout_component(run_id, "run id")
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactLayout.timestamped_run`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Build the established timestamped run path without creating it.

**Exact API:** {py:obj}`artifacts.layout.ArtifactLayout.timestamped_run` · **Source:** [artifacts/layout.py:51](../../../../artifacts/layout.py#L51)

**Inputs and outputs:**

- **Args:**

  ```text
  name: Name used to identify the requested file, artifact, or item.
  timestamp: Timestamp used by the operation described above.
  ```

- **Returns:**

  ```text
  Path returned by ``timestamped_run``.
  ```

**Observed usage:**

1. [test fixture: `test_timestamped_run_path_keeps_existing_layout_without_creating_directory`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L46)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timestamped_run_path_keeps_existing_layout_without_creating_directory(
    tmp_path: Path,
) -> None:
    layout = ArtifactLayout(tmp_path)
    timestamp = datetime(2026, 10, 30, 12, 31, 44, 123456)

    run_path = layout.timestamped_run("rl_train_seed42_tcn", timestamp=timestamp)

    assert run_path == tmp_path / "20261030_123144_123456_rl_train_seed42_tcn"
    assert not run_path.exists()
```

2. [production caller: `save_run`](../../../../evaluation/reporting/run_artifact_writer.py#L900)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    if run_dir is None:
        run_dir = ArtifactLayout(Path(out_dir)).timestamped_run(name)
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("Saving run artifacts to %s", run_dir)

    daily_loss_limit, max_loss_limit, profit_target = _extract_ftmo_limits(cfg)
    evaluation_cfg = getattr(cfg, "evaluation", None)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.attempt`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the artifact directory for one run attempt.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.attempt` · **Source:** [artifacts/layout.py:271](../../../../artifacts/layout.py#L271)

**Inputs and outputs:**

- **Args:**

  ```text
  run_key: Stable key for the work item.
  attempt: Positive attempt number.
  ```

- **Returns:**

  ```text
  The attempt directory.
  ```

**Observed usage:**

1. [production caller: `prepare_experiment_run_resume`](../../../../experiments/runs/cache_failure_recovery.py#L110)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            continue
        key = str(job.get("key", ""))
        attempt_number = int(job.get("attempts", 0))
        if not key or attempt_number < 1:
            raise ValueError("failed experiment run identity has invalid key/attempt")
        attempt_dir = artifacts.attempt(key, attempt_number)
        log_path = artifacts.worker_log(key, attempt_number)
        provenance_path = attempt_dir / "attempt_provenance.json"
        if not log_path.is_file() or not provenance_path.is_file():
            raise ValueError(f"missing failed-attempt evidence for {key}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
# … caller assertions omitted …
```

2. [production caller: `latest_resumable_checkpoint`](../../../../experiments/runs/checkpoint_lineage.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    attempt_out = ExperimentRunArtifactLayout(experiment_run_out).attempt(key, previous_attempt)
    try:
        provenance = json.loads(
            (attempt_out / "attempt_provenance.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.bootstrap_checkpoint`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the bootstrap checkpoint path for one work item.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.bootstrap_checkpoint` · **Source:** [artifacts/layout.py:309](../../../../artifacts/layout.py#L309)

**Inputs and outputs:**

- **Args:**

  ```text
  run_key: Stable key for the work item.
  ```

- **Returns:**

  ```text
  The checkpoint archive path.
  ```

**Observed usage:**

1. [production caller: `archive_initial_checkpoints`](../../../../experiments/runs/checkpoint_lineage.py#L330)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    archived: dict[str, pathlib.Path] = {}
    for key, checkpoint in checkpoints.items():
        destination = ExperimentRunArtifactLayout(experiment_run_out).bootstrap_checkpoint(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected_sha = str(checkpoint["checkpoint_sha256"])
        if destination.is_file():
            if sha256_file(destination) != expected_sha:
                raise RuntimeError(f"archived bootstrap checkpoint changed for {key}")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.completion_marker`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the completion marker for one work item.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.completion_marker` · **Source:** [artifacts/layout.py:297](../../../../artifacts/layout.py#L297)

**Inputs and outputs:**

- **Args:**

  ```text
  run_key: Stable key for the work item.
  ```

- **Returns:**

  ```text
  The completion marker path.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentRunArtifactLayout(...)
result = instance.completion_marker(run_key=...)
```

**Lifecycle context:** This callable participates in `ExperimentRunArtifactLayout`: Named artifact paths for an experiment run, preserving its established on-disk layout. Related public lifecycle methods: {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.controller_lock`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the controller lock-file path.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock` · **Source:** [artifacts/layout.py:144](../../../../artifacts/layout.py#L144)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``controller_lock``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentRunArtifactLayout(...)
value = instance.controller_lock
```

**Lifecycle context:** This callable participates in `ExperimentRunArtifactLayout`: Named artifact paths for an experiment run, preserving its established on-disk layout. Related public lifecycle methods: {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.ensure_controller_directories`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Create the directories required by the experiment-run controller.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.ensure_controller_directories` · **Source:** [artifacts/layout.py:355](../../../../artifacts/layout.py#L355)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentRunArtifactLayout(...)
result = instance.ensure_controller_directories()
```

**Lifecycle context:** This callable participates in `ExperimentRunArtifactLayout`: Named artifact paths for an experiment run, preserving its established on-disk layout. Related public lifecycle methods: {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.failure_logs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing failed-attempt logs.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs` · **Source:** [artifacts/layout.py:171](../../../../artifacts/layout.py#L171)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``failure_logs``.
  ```

**Observed usage:**

1. [production caller: `ensure_controller_directories`](../../../../artifacts/layout.py#L359)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ensure_controller_directories(self) -> None:
    for directory in (
        self.worker_logs,
        self.failure_logs,
        self.runs,
        self.markers,
        self.reports,
    ):
        directory.mkdir(parents=True, exist_ok=True)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.log`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve a named controller log below the logs directory.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.log` · **Source:** [artifacts/layout.py:246](../../../../artifacts/layout.py#L246)

**Inputs and outputs:**

- **Args:**

  ```text
  name: Safe log filename.
  ```

- **Returns:**

  ```text
  The log path.
  ```

**Observed usage:**

1. [production caller: `render`](../../../../experiments/runs/status.py#L568)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        alloc_tres = data.get("AllocTRES", "")
        gpu_type_match = re.search(r"gpu:([^:,]+)", gres)
        gpu_type = gpu_type_match.group(1) if gpu_type_match else "GPU"
        gpu_total = parse_gres_count(gres)
        gpu_alloc = parse_gres_count(alloc_tres, gpu_type) or parse_gres_count(alloc_tres)
        sample = latest_resource_sample(experiment_run_artifacts.log(f"resources_{node}.csv"))
        if sample:
            sampled_at = dt.datetime.fromisoformat(
                sample["timestamp_utc"].replace("Z", "+00:00")
            ).astimezone(timezone)
            age = max(0, int((now - sampled_at).total_seconds()))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.logs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing controller and worker logs.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs` · **Source:** [artifacts/layout.py:153](../../../../artifacts/layout.py#L153)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``logs``.
  ```

**Observed usage:**

1. [production caller: `worker_logs`](../../../../artifacts/layout.py#L168)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def worker_logs(self) -> Path:
    return self.logs / "workers"
```

2. [production caller: `failure_logs`](../../../../artifacts/layout.py#L177)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def failure_logs(self) -> Path:
    return self.logs / "failures"
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.manifest`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the path to the experiment-run manifest.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest` · **Source:** [artifacts/layout.py:135](../../../../artifacts/layout.py#L135)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``manifest``.
  ```

**Observed usage:**

1. [production caller: `resolve_handoff`](../../../../compute/slurm/continuation.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        not isinstance(handoff, dict)
        or handoff.get("schema") != "aalto.experiment_run_continuation_handoff.v1"
    ):
        raise ValueError("unsupported experiment run continuation handoff schema")
    source_manifest = json.loads(
        ExperimentRunArtifactLayout(source_experiment_run).manifest.read_text(encoding="utf-8")
    )
    if handoff.get("source_experiment_run_id") != source_experiment_run.name or handoff.get(
        "source_experiment_run_fingerprint"
    ) != source_manifest.get("fingerprint"):
        raise ValueError(
# … caller assertions omitted …
```

2. [production caller: `prepare_experiment_run_resume`](../../../../experiments/runs/cache_failure_recovery.py#L82)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    artifacts = ExperimentRunArtifactLayout(experiment_run_dir)
    manifest_path = artifacts.manifest
    original_bytes = manifest_path.read_bytes()
    manifest = json.loads(original_bytes)
    fingerprint = manifest.get("fingerprint")
    jobs = manifest.get("jobs")
    if (
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.markers`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing completion markers.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers` · **Source:** [artifacts/layout.py:189](../../../../artifacts/layout.py#L189)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``markers``.
  ```

**Observed usage:**

1. [production caller: `completion_marker`](../../../../artifacts/layout.py#L307)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def completion_marker(self, run_key: str) -> Path:
    self._validate_run_key(run_key)
    return self.markers / f"{run_key}.done"
```

2. [production caller: `ensure_controller_directories`](../../../../artifacts/layout.py#L361)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ensure_controller_directories(self) -> None:
    for directory in (
        self.worker_logs,
        self.failure_logs,
        self.runs,
        self.markers,
        self.reports,
    ):
        directory.mkdir(parents=True, exist_ok=True)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.queue`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the path to the append-only work queue.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.queue` · **Source:** [artifacts/layout.py:216](../../../../artifacts/layout.py#L216)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``queue``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentRunArtifactLayout(...)
value = instance.queue
```

**Lifecycle context:** This callable participates in `ExperimentRunArtifactLayout`: Named artifact paths for an experiment run, preserving its established on-disk layout. Related public lifecycle methods: {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.recovery_checkpoint`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve a recorded checkpoint only when it remains inside this experiment run.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.recovery_checkpoint` · **Source:** [artifacts/layout.py:339](../../../../artifacts/layout.py#L339)

**Inputs and outputs:**

- **Args:**

  ```text
  value: Value to process.
  ```

- **Returns:**

  ```text
  Path returned by ``recovery_checkpoint``.
  ```

**Observed usage:**

1. [production caller: `prepare_experiment_run_resume`](../../../../experiments/runs/cache_failure_recovery.py#L140)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            raise ValueError(f"attempt fingerprint mismatch for {key}")
        checkpoint_raw = provenance.get("resume_checkpoint")
        checkpoint_hash = provenance.get("resume_checkpoint_sha256")
        if not checkpoint_raw or not checkpoint_hash:
            raise ValueError(f"no verified resume checkpoint recorded for {key}")
        checkpoint = artifacts.recovery_checkpoint(checkpoint_raw)
        if not checkpoint.is_file() or file_sha256(checkpoint) != checkpoint_hash:
            raise ValueError(f"resume checkpoint is missing or changed for {key}")
        checkpoint_attempt = _checkpoint_attempt(checkpoint, experiment_run_dir)
        if checkpoint_attempt >= attempt_number:
            raise ValueError(f"resume checkpoint is not earlier than failed attempt for {key}")
# … caller assertions omitted …
```

2. [production caller: `build_initial_checkpoint_map`](../../../../experiments/runs/checkpoint_lineage.py#L244)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        source_artifacts = ExperimentRunArtifactLayout(source_dir)
        manifest = read_manifest(source_artifacts.manifest)
        snapshot = manifest.get("source_snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("path"), str):
            raise ValueError(f"source experiment run snapshot is missing: {source_dir}")
        snapshot_path = source_artifacts.recovery_checkpoint(snapshot["path"])
        if snapshot_path.parent != source_dir:
            raise ValueError(f"source snapshot path escapes experiment run: {source_dir}")
        valid, reason = verify_experiment_run_source_snapshot(snapshot_path, snapshot)
        if not valid:
            raise ValueError(f"source experiment run snapshot is invalid: {reason}")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.report`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve a named report file below the reports directory.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.report` · **Source:** [artifacts/layout.py:224](../../../../artifacts/layout.py#L224)

**Inputs and outputs:**

- **Args:**

  ```text
  name: Safe report filename.
  ```

- **Returns:**

  ```text
  The report path.
  ```

**Observed usage:**

1. [production caller: `prepare_experiment_run_resume`](../../../../experiments/runs/cache_failure_recovery.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                "resume_checkpoint_attempt": checkpoint_attempt,
            }
        )

    if not failed:
        recovery_path = artifacts.report("cache_recovery.json")
        if not recovery_path.is_file():
            return {
                "experiment_run_fingerprint": fingerprint,
                "requeued": 0,
                "already_resumable": True,
# … caller assertions omitted …
```

2. [production caller: `build_summary`](../../../../experiments/runs/reporting.py#L408)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    artifacts = ExperimentRunArtifactLayout(experiment_run_dir)
    experiment_run = _read_json(artifacts.manifest)
    status = _read_json(artifacts.report("experiment_run_status.json"))
    if experiment_run is None or status is None:
        raise ValueError("experiment_run.json and reports/experiment_run_status.json are required")

    jobs: list[dict[str, Any]] = []
    for job in experiment_run.get("jobs", []):
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.reports`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing experiment reports.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports` · **Source:** [artifacts/layout.py:198](../../../../artifacts/layout.py#L198)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``reports``.
  ```

**Observed usage:**

1. [production caller: `report`](../../../../artifacts/layout.py#L233)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def report(self, name: str) -> Path:
    return self._named_file(self.reports, name, "report")
```

2. [production caller: `ensure_controller_directories`](../../../../artifacts/layout.py#L362)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ensure_controller_directories(self) -> None:
    for directory in (
        self.worker_logs,
        self.failure_logs,
        self.runs,
        self.markers,
        self.reports,
    ):
        directory.mkdir(parents=True, exist_ok=True)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.resolve_recorded_path`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve a manifest path without allowing it to escape the experiment run root.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.resolve_recorded_path` · **Source:** [artifacts/layout.py:321](../../../../artifacts/layout.py#L321)

**Inputs and outputs:**

- **Args:**

  ```text
  value: Value to process.
  ```

- **Returns:**

  ```text
  Path returned by ``resolve_recorded_path``.
  ```

**Observed usage:**

1. [production caller: `recovery_checkpoint`](../../../../artifacts/layout.py#L349)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def recovery_checkpoint(self, value: str | Path) -> Path:
    try:
        return self.resolve_recorded_path(value)
    except ValueError:
        raise ValueError(
            "experiment run checkpoint path escapes its experiment run directory"
        ) from None
```

2. [production caller: `build_summary`](../../../../experiments/runs/reporting.py#L468)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        train_metrics = _read_json(train_path) if run_dir else None
        test_metrics = _read_json(test_path) if run_dir else None
        gate = _read_json(gate_path) if run_dir else None
        account_currency, initial_balance = _account_config(run_dir)
        try:
            log_path = artifacts.resolve_recorded_path(str(job.get("log", "")))
        except ValueError:
            log_path = artifacts.worker_log(run_key, attempt_number)
        if not log_path.is_file():
            log_path = artifacts.logs / "workers" / f"{run_key}.log"
        job_report = {
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.root_file`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve a named artifact file directly below the run root.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.root_file` · **Source:** [artifacts/layout.py:235](../../../../artifacts/layout.py#L235)

**Inputs and outputs:**

- **Args:**

  ```text
  name: Safe artifact filename.
  ```

- **Returns:**

  ```text
  The artifact path.
  ```

**Observed usage:**

1. [production caller: `_manager`](../../../../compute/slurm/worker_dispatch.py#L390)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    experiment_run_out = Path(os.environ["EXPERIMENT_RUN_OUT_DIR"])
    done_marker = Path(
        os.environ.get(
            "EXPERIMENT_RUN_ALLOCATION_DONE_MARKER",
            str(
                ExperimentRunArtifactLayout(experiment_run_out).root_file(
                    "allocation_controller.exit"
                )
            ),
        )
    )
    cancelled = claimed.parent / "cancelled"
    cancelled.mkdir(parents=True, exist_ok=True)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.run_attempts`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing attempts for one work item.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.run_attempts` · **Source:** [artifacts/layout.py:285](../../../../artifacts/layout.py#L285)

**Inputs and outputs:**

- **Args:**

  ```text
  run_key: Stable key for the work item.
  ```

- **Returns:**

  ```text
  The work item's attempt directory.
  ```

**Observed usage:**

1. [production caller: `latest_checkpoint`](../../../../experiments/runs/status.py#L334)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def latest_checkpoint(experiment_run_dir: pathlib.Path, key: str, now: dt.datetime) -> str:
    try:
        attempt_root = ExperimentRunArtifactLayout(experiment_run_dir).run_attempts(key)
    except ValueError:
        return "none found"
    files = [
        path for path in attempt_root.glob("**/*.zip") if path.is_file() and "model" in path.parts
    ]
    if not files:
        return "none found"
    path = max(files, key=lambda item: item.stat().st_mtime)
    saved = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo)
    return f"{path.name} ({saved:%Y-%m-%d %H:%M})"
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.runs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing run-level outputs.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs` · **Source:** [artifacts/layout.py:180](../../../../artifacts/layout.py#L180)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``runs``.
  ```

**Observed usage:**

1. [production caller: `attempt`](../../../../artifacts/layout.py#L283)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def attempt(self, run_key: str, attempt: int) -> Path:
    self._validate_run_key(run_key)
    self._validate_attempt(attempt)
    return self.runs / "attempts" / run_key / f"attempt{attempt}"
```

2. [production caller: `run_attempts`](../../../../artifacts/layout.py#L295)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def run_attempts(self, run_key: str) -> Path:
    self._validate_run_key(run_key)
    return self.runs / "attempts" / run_key
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.source_snapshot`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the path to the archived source snapshot.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.source_snapshot` · **Source:** [artifacts/layout.py:207](../../../../artifacts/layout.py#L207)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``source_snapshot``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentRunArtifactLayout(...)
value = instance.source_snapshot
```

**Lifecycle context:** This callable participates in `ExperimentRunArtifactLayout`: Named artifact paths for an experiment run, preserving its established on-disk layout. Related public lifecycle methods: {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.manifest`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.controller_lock`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.failure_logs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.runs`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.markers`, {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.reports`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.worker_log`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Resolve the log for one worker attempt.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_log` · **Source:** [artifacts/layout.py:257](../../../../artifacts/layout.py#L257)

**Inputs and outputs:**

- **Args:**

  ```text
  run_key: Stable key for the work item.
  attempt: Positive attempt number.
  ```

- **Returns:**

  ```text
  The worker log path.
  ```

**Observed usage:**

1. [production caller: `prepare_experiment_run_resume`](../../../../experiments/runs/cache_failure_recovery.py#L111)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        key = str(job.get("key", ""))
        attempt_number = int(job.get("attempts", 0))
        if not key or attempt_number < 1:
            raise ValueError("failed experiment run identity has invalid key/attempt")
        attempt_dir = artifacts.attempt(key, attempt_number)
        log_path = artifacts.worker_log(key, attempt_number)
        provenance_path = attempt_dir / "attempt_provenance.json"
        if not log_path.is_file() or not provenance_path.is_file():
            raise ValueError(f"missing failed-attempt evidence for {key}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if (
# … caller assertions omitted …
```

2. [production caller: `build_summary`](../../../../experiments/runs/reporting.py#L470)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        gate = _read_json(gate_path) if run_dir else None
        account_currency, initial_balance = _account_config(run_dir)
        try:
            log_path = artifacts.resolve_recorded_path(str(job.get("log", "")))
        except ValueError:
            log_path = artifacts.worker_log(run_key, attempt_number)
        if not log_path.is_file():
            log_path = artifacts.logs / "workers" / f"{run_key}.log"
        job_report = {
            "run_key": run_key,
            "variant": job.get("variant"),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ExperimentRunArtifactLayout.worker_logs`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.layout`

**Purpose:** Return the directory containing per-worker logs.

**Exact API:** {py:obj}`artifacts.layout.ExperimentRunArtifactLayout.worker_logs` · **Source:** [artifacts/layout.py:162](../../../../artifacts/layout.py#L162)

**Inputs and outputs:**

- **Returns:**

  ```text
  Path returned by ``worker_logs``.
  ```

**Observed usage:**

1. [production caller: `worker_log`](../../../../artifacts/layout.py#L269)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def worker_log(self, run_key: str, attempt: int) -> Path:
    self._validate_run_key(run_key)
    self._validate_attempt(attempt)
    return self.worker_logs / f"{run_key}__attempt{attempt}.log"
```

2. [production caller: `ensure_controller_directories`](../../../../artifacts/layout.py#L358)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ensure_controller_directories(self) -> None:
    for directory in (
        self.worker_logs,
        self.failure_logs,
        self.runs,
        self.markers,
        self.reports,
    ):
        directory.mkdir(parents=True, exist_ok=True)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
