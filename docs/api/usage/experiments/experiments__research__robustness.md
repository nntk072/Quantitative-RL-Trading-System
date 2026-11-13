# Experiments · `research.robustness`

This page contains 3 public callable records owned by `experiments.research.robustness`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_exposed_report_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.robustness`

**Purpose:** Open the exposed interval once, then replay the frozen finalist without selection.

**Exact API:** {py:obj}`experiments.research.robustness.build_exposed_report_bundle` · **Source:** [experiments/research/robustness.py:196](../../../../experiments/research/robustness.py#L196)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment: Registered research experiment specification.
  source_commit: Git commit binding the research artifacts.
  finalist_runs: Mapping from seed to frozen finalist run directory.
  robustness_record: Path to the robustness disposition artifact.
  output_root: Base directory for generated research artifacts.
  exposure_marker: Path recording the one-time exposed-period opening.
  ```

- **Returns:**

  ```text
  Result produced by build_exposed_report_bundle.
  ```

**Observed usage:**

1. [production caller: `freeze_experiment`](../../../../experiments/research/workflow.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if kind == "report_only_replay":
        if finalist_runs is None or robustness_record is None or exposure_marker is None:
            raise ValueError(
                "report-only replay requires finalist runs, robustness evidence, and exposure marker"
            )
        return build_exposed_report_bundle(
            experiment,
            source_commit=source_commit,
            finalist_runs=finalist_runs,
            robustness_record=robustness_record,
            output_root=output_root,
            exposure_marker=exposure_marker,
        )
    raise ValueError(f"unsupported research execution kind: {kind}")
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `build_robustness_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.robustness`

**Purpose:** Build development-only checkpoint replays for registered stress variants.

**Exact API:** {py:obj}`experiments.research.robustness.build_robustness_bundle` · **Source:** [experiments/research/robustness.py:31](../../../../experiments/research/robustness.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment: Registered research experiment specification.
  source_commit: Git commit binding the research artifacts.
  finalist_runs: Mapping from seed to frozen finalist run directory.
  output_root: Base directory for generated research artifacts.
  selected_variants: Variant identifiers selected for this operation.
  ```

- **Returns:**

  ```text
  Result produced by build_robustness_bundle.
  ```

**Observed usage:**

1. [production caller: `freeze_experiment`](../../../../experiments/research/workflow.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            selected_variants=selected_variants,
        )
    if kind == "checkpoint_replay":
        if finalist_runs is None:
            raise ValueError("robustness replay requires finalist runs")
        return build_robustness_bundle(
            experiment,
            source_commit=source_commit,
            finalist_runs=finalist_runs,
            output_root=output_root,
            selected_variants=selected_variants,
        )
    if kind == "report_only_replay":
        if finalist_runs is None or robustness_record is None or exposure_marker is None:
            raise ValueError(
                "report-only replay requires finalist runs, robustness evidence, and exposure marker"
            )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `summarize_robustness`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.robustness`

**Purpose:** Require every recorded development-only robustness replay to be hard-risk safe.

**Exact API:** {py:obj}`experiments.research.robustness.summarize_robustness` · **Source:** [experiments/research/robustness.py:140](../../../../experiments/research/robustness.py#L140)

**Inputs and outputs:**

- **Args:**

  ```text
  execution_manifests: Source-bound prerequisite execution records.
  ```

- **Returns:**

  ```text
  Result produced by summarize_robustness.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L345)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "robustness":
        result = summarize_robustness(args.execution)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
