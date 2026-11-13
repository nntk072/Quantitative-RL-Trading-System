# Experiments · `research.execution`

This page contains 10 public callable records owned by `experiments.research.execution`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CommandBundle`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Source-bound command graph for one named experiment.

**Exact API:** {py:obj}`experiments.research.execution.CommandBundle` · **Source:** [experiments/research/execution.py:48](../../../../experiments/research/execution.py#L48)

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_explicit_seed_and_result_artifact_survive_consolidation(tmp_path: Path) -> None:
    result = tmp_path / "record.json"
    result.write_text(json.dumps({"metrics": {"quality": {"coverage": 0.95}}}), encoding="utf-8")
    digest = file_sha256(result)
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="data_integrity",
        domain="data",
        commands=(
            CommandSpec(
                command_id="capture",
                argv=("python", "-m", "example"),
                variant_id="capture",
                component="data",
                seed=27,
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        command_id="opportunity_census",
        argv=("python", "-m", "example"),
        variant_id="opportunity_census",
        component="opportunities",
    )
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
    )

    assert bundle_from_payload(bundle_payload(bundle)) == bundle
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `CommandSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** One executable work unit in a research experiment.

**Exact API:** {py:obj}`experiments.research.execution.CommandSpec` · **Source:** [experiments/research/execution.py:29](../../../../experiments/research/execution.py#L29)

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="data_integrity",
        domain="data",
        commands=(
            CommandSpec(
                command_id="capture",
                argv=("python", "-m", "example"),
                variant_id="capture",
                component="data",
                seed=27,
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_command_bundle_preserves_explicit_component_identity() -> None:
    command = CommandSpec(
        command_id="opportunity_census",
        argv=("python", "-m", "example"),
        variant_id="opportunity_census",
        component="opportunities",
    )
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `execute_command_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Execute one source-bound command graph and persist resumable state.

**Exact API:** {py:obj}`experiments.research.execution.execute_command_bundle` · **Source:** [experiments/research/execution.py:332](../../../../experiments/research/execution.py#L332)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle: Frozen source-bound command bundle.
  run_root: Directory containing execution state and command attempts.
  max_workers: Maximum number of concurrently active commands.
  allow_experiments: Whether commands that allocate experimental compute are authorized.
  resume: Whether to resume an existing execution state.
  retry_failed: Whether reviewed failed commands may be retried.
  max_runtime_seconds: Optional execution time budget.
  ```

- **Returns:**

  ```text
  Result produced by execute_command_bundle.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L280)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
            load_bundle(args.bundle),
            run_root=args.run_root,
            max_workers=args.max_workers,
            allow_experiments=args.allow_experiments,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_runtime_seconds=args.max_runtime_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "passed" else 2 if result["status"] == "incomplete" else 1
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `CommandBundle`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Source-bound command graph for one named experiment.

**Exact API:** {py:obj}`experiments.research.execution.CommandBundle` · **Source:** [experiments/research/execution.py:48](../../../../experiments/research/execution.py#L48)

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_explicit_seed_and_result_artifact_survive_consolidation(tmp_path: Path) -> None:
    result = tmp_path / "record.json"
    result.write_text(json.dumps({"metrics": {"quality": {"coverage": 0.95}}}), encoding="utf-8")
    digest = file_sha256(result)
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="data_integrity",
        domain="data",
        commands=(
            CommandSpec(
                command_id="capture",
                argv=("python", "-m", "example"),
                variant_id="capture",
                component="data",
                seed=27,
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        command_id="opportunity_census",
        argv=("python", "-m", "example"),
        variant_id="opportunity_census",
        component="opportunities",
    )
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
    )

    assert bundle_from_payload(bundle_payload(bundle)) == bundle
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `CommandResult`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Persisted result of one command attempt.

**Exact API:** {py:obj}`experiments.research.execution.CommandResult` · **Source:** [experiments/research/execution.py:59](../../../../experiments/research/execution.py#L59)

**Observed usage:**

1. [production caller: `_run_one`](../../../../experiments/research/execution.py#L297)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
    elapsed = time.perf_counter() - started
    artifacts = _artifact_hashes(command.artifact_roots)
    missing = any(key.startswith(("MISSING::", "EMPTY::")) for key in artifacts)
    blocker = "declared artifact root missing or empty" if missing else None
    return CommandResult(
        command_id=command.command_id,
        status=(
            "passed"
            if process.returncode in command.accepted_return_codes and not missing
            else "failed"
        ),
        return_code=int(process.returncode),
        elapsed_seconds=elapsed,
        log_path=str(log_path),
        log_sha256=file_sha256(log_path),
        artifact_sha256=artifacts,
        blocker=blocker,
        variant_id=command.variant_id,
        component=command.component,
        seed=command.seed,
        result_artifact=command.result_artifact,
    )
```

2. [production caller: `execute_command_bundle`](../../../../experiments/research/execution.py#L403)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        for command_id, row in saved.items():
            attempt_dir = run_root / "commands" / command_id
            attempts[command_id] = len(tuple(attempt_dir.glob("attempt_*")))
            status = row.get("status")
            if status == "passed":
                result = CommandResult(**row)
                if result.artifact_sha256 != _artifact_hashes(by_id[command_id].artifact_roots):
                    raise ValueError(f"completed command artifacts changed: {command_id}")
                results[command_id] = result
            elif status == "failed" and not retry_failed:
                raise ValueError(
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `CommandSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** One executable work unit in a research experiment.

**Exact API:** {py:obj}`experiments.research.execution.CommandSpec` · **Source:** [experiments/research/execution.py:29](../../../../experiments/research/execution.py#L29)

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="data_integrity",
        domain="data",
        commands=(
            CommandSpec(
                command_id="capture",
                argv=("python", "-m", "example"),
                variant_id="capture",
                component="data",
                seed=27,
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_command_bundle_preserves_explicit_component_identity() -> None:
    command = CommandSpec(
        command_id="opportunity_census",
        argv=("python", "-m", "example"),
        variant_id="opportunity_census",
        component="opportunities",
    )
    bundle = CommandBundle(
        source_commit="a" * 40,
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `bundle_from_payload`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Validate a JSON-like payload and return the typed command bundle.

**Exact API:** {py:obj}`experiments.research.execution.bundle_from_payload` · **Source:** [experiments/research/execution.py:161](../../../../experiments/research/execution.py#L161)

**Inputs and outputs:**

- **Args:**

  ```text
  value: Value to validate or transform.
  ```

- **Returns:**

  ```text
  Result produced by bundle_from_payload.
  ```

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L100)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L56)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
    )

    assert bundle_from_payload(bundle_payload(bundle)) == bundle
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `bundle_payload`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Return a JSON-serializable command-bundle payload.

**Exact API:** {py:obj}`experiments.research.execution.bundle_payload` · **Source:** [experiments/research/execution.py:126](../../../../experiments/research/execution.py#L126)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle: Frozen source-bound command bundle.
  ```

- **Returns:**

  ```text
  Result produced by bundle_payload.
  ```

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L100)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                result_artifact=str(result),
                artifact_roots=(str(result),),
            ),
        ),
    )
    assert bundle_from_payload(bundle_payload(bundle)) == bundle
    manifest = tmp_path / "execution_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
# … caller assertions omitted …
```

2. [test fixture: `test_command_bundle_preserves_explicit_component_identity`](../../../../tests/unit/experiments/test_research_composition.py#L56)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        experiment_id="feature_inputs",
        domain="features",
        commands=(command,),
    )

    assert bundle_from_payload(bundle_payload(bundle)) == bundle
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `execute_command_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Execute one source-bound command graph and persist resumable state.

**Exact API:** {py:obj}`experiments.research.execution.execute_command_bundle` · **Source:** [experiments/research/execution.py:332](../../../../experiments/research/execution.py#L332)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle: Frozen source-bound command bundle.
  run_root: Directory containing execution state and command attempts.
  max_workers: Maximum number of concurrently active commands.
  allow_experiments: Whether commands that allocate experimental compute are authorized.
  resume: Whether to resume an existing execution state.
  retry_failed: Whether reviewed failed commands may be retried.
  max_runtime_seconds: Optional execution time budget.
  ```

- **Returns:**

  ```text
  Result produced by execute_command_bundle.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L280)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
            load_bundle(args.bundle),
            run_root=args.run_root,
            max_workers=args.max_workers,
            allow_experiments=args.allow_experiments,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_runtime_seconds=args.max_runtime_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "passed" else 2 if result["status"] == "incomplete" else 1
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `execute_command_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.execution`

**Purpose:** Execute one source-bound command graph and persist resumable state.

**Exact API:** {py:obj}`experiments.research.execution.execute_command_bundle` · **Source:** [experiments/research/execution.py:332](../../../../experiments/research/execution.py#L332)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle: Frozen source-bound command bundle.
  run_root: Directory containing execution state and command attempts.
  max_workers: Maximum number of concurrently active commands.
  allow_experiments: Whether commands that allocate experimental compute are authorized.
  resume: Whether to resume an existing execution state.
  retry_failed: Whether reviewed failed commands may be retried.
  max_runtime_seconds: Optional execution time budget.
  ```

- **Returns:**

  ```text
  Result produced by execute_command_bundle.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L280)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
            load_bundle(args.bundle),
            run_root=args.run_root,
            max_workers=args.max_workers,
            allow_experiments=args.allow_experiments,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_runtime_seconds=args.max_runtime_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "passed" else 2 if result["status"] == "incomplete" else 1
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
