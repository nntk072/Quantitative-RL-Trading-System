# Experiments · `research.workflow`

This page contains 4 public callable records owned by `experiments.research.workflow`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `current_source_commit`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.workflow`

**Purpose:** Return the Git commit used to bind frozen research commands.

**Exact API:** {py:obj}`experiments.research.workflow.current_source_commit` · **Source:** [experiments/research/workflow.py:24](../../../../experiments/research/workflow.py#L24)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result produced by current_source_commit.
  ```

**Observed usage:**

1. [production caller: `freeze_experiment`](../../../../experiments/research/workflow.py#L81)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    experiment = catalog.experiment(experiment_id)
    unknown = set(selected_variants) - {variant.variant_id for variant in experiment.variants}
    if unknown:
        raise ValueError(f"{experiment_id} has no variants named {sorted(unknown)}")
    source_commit = current_source_commit()
    kind = experiment.execution.kind
    if kind == "command_group":
        return build_command_group_bundle(
            experiment,
            source_commit=source_commit,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `freeze_experiment`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.workflow`

**Purpose:** Freeze one registered experiment into source-bound commands.

**Exact API:** {py:obj}`experiments.research.workflow.freeze_experiment` · **Source:** [experiments/research/workflow.py:49](../../../../experiments/research/workflow.py#L49)

**Inputs and outputs:**

- **Args:**

  ```text
  catalog: Value used for catalog.
  experiment_id: Registered research experiment identifier.
  output_root: Base directory for generated research artifacts.
  readiness: Source-bound scientific-readiness record.
  survival_gate: Value used for survival gate.
  finalist_runs: Mapping from seed to frozen finalist run directory.
  robustness_record: Path to the robustness disposition artifact.
  exposure_marker: Path recording the one-time exposed-period opening.
  selected_variants: Variant identifiers selected for this operation.
  ```

- **Returns:**

  ```text
  Result produced by freeze_experiment.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L265)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                item.variant_id for item in experiment.variants if item.component in args.component
            }
            selected = selected & matching if selected else matching
            if not selected:
                raise ValueError(f"{args.experiment} has no matching component variants")
        bundle = freeze_experiment(
            catalog,
            args.experiment,
            output_root=args.output_root,
            readiness=args.readiness,
            survival_gate=args.survival_gate,
            finalist_runs=_finalist_runs(args.finalist_run),
            robustness_record=args.robustness_record,
            exposure_marker=args.exposure_marker,
            selected_variants=tuple(sorted(selected)),
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.workflow`

**Purpose:** Load a frozen command bundle.

**Exact API:** {py:obj}`experiments.research.workflow.load_bundle` · **Source:** [experiments/research/workflow.py:161](../../../../experiments/research/workflow.py#L161)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_bundle.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L281)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
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
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `write_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.workflow`

**Purpose:** Write a frozen command bundle.

**Exact API:** {py:obj}`experiments.research.workflow.write_bundle` · **Source:** [experiments/research/workflow.py:150](../../../../experiments/research/workflow.py#L150)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle: Frozen source-bound command bundle.
  path: Path to the input or output artifact.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L276)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            finalist_runs=_finalist_runs(args.finalist_run),
            robustness_record=args.robustness_record,
            exposure_marker=args.exposure_marker,
            selected_variants=tuple(sorted(selected)),
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
            load_bundle(args.bundle),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
