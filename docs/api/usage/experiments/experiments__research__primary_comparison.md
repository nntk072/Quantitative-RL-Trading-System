# Experiments · `research.primary_comparison`

This page contains 2 public callable records owned by `experiments.research.primary_comparison`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `analyze_primary_payload`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.primary_comparison`

**Purpose:** Apply the registered exact sign-flip and paired-seed bootstrap.

**Exact API:** {py:obj}`experiments.research.primary_comparison.analyze_primary_payload` · **Source:** [experiments/research/primary_comparison.py:154](../../../../experiments/research/primary_comparison.py#L154)

**Inputs and outputs:**

- **Args:**

  ```text
  payload: Normalized comparison payload.
  ```

- **Returns:**

  ```text
  Result produced by analyze_primary_payload.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L354)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "primary":
        payload = build_primary_payload(_json_object(args.source))
        analysis = analyze_primary_payload(payload)
        from artifacts.atomic import write_json_atomic

        args.payload.parent.mkdir(parents=True, exist_ok=True)
        args.analysis.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.payload, payload)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `build_primary_payload`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.primary_comparison`

**Purpose:** Validate the exact six paired development paths and matched provenance.

**Exact API:** {py:obj}`experiments.research.primary_comparison.build_primary_payload` · **Source:** [experiments/research/primary_comparison.py:105](../../../../experiments/research/primary_comparison.py#L105)

**Inputs and outputs:**

- **Args:**

  ```text
  spec: Source specification to validate.
  ```

- **Returns:**

  ```text
  Result produced by build_primary_payload.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L353)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "primary":
        payload = build_primary_payload(_json_object(args.source))
        analysis = analyze_primary_payload(payload)
        from artifacts.atomic import write_json_atomic

        args.payload.parent.mkdir(parents=True, exist_ok=True)
        args.analysis.parent.mkdir(parents=True, exist_ok=True)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
