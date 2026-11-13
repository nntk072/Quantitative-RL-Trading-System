# Experiments · `research.repeatability`

This page contains 2 public callable records owned by `experiments.research.repeatability`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_repeatability_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.repeatability`

**Purpose:** Replay every qualified checkpoint twice and compare complete train-only ledgers.

**Exact API:** {py:obj}`experiments.research.repeatability.build_repeatability_bundle` · **Source:** [experiments/research/repeatability.py:32](../../../../experiments/research/repeatability.py#L32)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment: Registered research experiment specification.
  source_commit: Git commit binding the research artifacts.
  gate_path: Path to the survival qualification artifact.
  output_root: Base directory for generated research artifacts.
  ```

- **Returns:**

  ```text
  Result produced by build_repeatability_bundle.
  ```

**Observed usage:**

1. [production caller: `freeze_experiment`](../../../../experiments/research/workflow.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            selected_variants=selected_variants,
        )
    if kind == "checkpoint_repeatability":
        if survival_gate is None:
            raise ValueError("checkpoint repeatability requires a survival qualification artifact")
        return build_repeatability_bundle(
            experiment,
            source_commit=source_commit,
            gate_path=survival_gate,
            output_root=output_root,
        )
    if kind == "checkpoint_continuation":
        if survival_gate is None:
            raise ValueError("portfolio continuation requires a survival qualification artifact")
        canonical = catalog.experiment("survival_policy").variant("setup_conditioned")
        if canonical.config is None:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `summarize_repeatability`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.repeatability`

**Purpose:** Require every per-seed comparison produced by the execution to pass.

**Exact API:** {py:obj}`experiments.research.repeatability.summarize_repeatability` · **Source:** [experiments/research/repeatability.py:134](../../../../experiments/research/repeatability.py#L134)

**Inputs and outputs:**

- **Args:**

  ```text
  execution_manifest: Value used for execution manifest.
  ```

- **Returns:**

  ```text
  Result produced by summarize_repeatability.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L326)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "repeatability":
        result = summarize_repeatability(args.execution)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
