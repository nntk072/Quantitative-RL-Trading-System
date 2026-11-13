# Experiments · `research.readiness`

This page contains 3 public callable records owned by `experiments.research.readiness`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_readiness`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.readiness`

**Purpose:** Build the source-bound authorization record for scientific training.

**Exact API:** {py:obj}`experiments.research.readiness.build_readiness` · **Source:** [experiments/research/readiness.py:235](../../../../experiments/research/readiness.py#L235)

**Inputs and outputs:**

- **Args:**

  ```text
  contract: Scientific-readiness contract.
  execution_manifests: Source-bound prerequisite execution records.
  reviews: Source-bound scientific review records.
  ```

- **Returns:**

  ```text
  Result produced by build_readiness.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L314)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            output=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "readiness":
        result = build_readiness(
            contract=load_readiness_contract(args.contract),
            execution_manifests=_named_json(args.execution),
            reviews=_named_json(args.review),
        )
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_readiness_contract`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.readiness`

**Purpose:** Load the active scientific-readiness contract.

**Exact API:** {py:obj}`experiments.research.readiness.load_readiness_contract` · **Source:** [experiments/research/readiness.py:48](../../../../experiments/research/readiness.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_readiness_contract.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L315)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "readiness":
        result = build_readiness(
            contract=load_readiness_contract(args.contract),
            execution_manifests=_named_json(args.execution),
            reviews=_named_json(args.review),
        )
        from artifacts.atomic import write_json_atomic

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `record_review`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.readiness`

**Purpose:** Record one human scientific review with immutable evidence identities.

**Exact API:** {py:obj}`experiments.research.readiness.record_review` · **Source:** [experiments/research/readiness.py:79](../../../../experiments/research/readiness.py#L79)

**Inputs and outputs:**

- **Args:**

  ```text
  review_id: Stable scientific review identifier.
  status: Recorded review or execution status.
  reviewed_by: Reviewer identity recorded with the evidence.
  note: Human-readable review rationale.
  evidence: Evidence files supporting the recorded review.
  output: Destination path for the generated artifact.
  ```

- **Returns:**

  ```text
  Result produced by record_review.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L303)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    if args.command == "review":
        result = record_review(
            review_id=args.id,
            status=args.status,
            reviewed_by=args.reviewed_by,
            note=args.note,
            evidence=args.evidence,
            output=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "readiness":
        result = build_readiness(
            contract=load_readiness_contract(args.contract),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
