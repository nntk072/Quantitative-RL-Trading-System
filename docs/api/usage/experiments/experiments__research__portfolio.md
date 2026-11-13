# Experiments · `research.portfolio`

This page contains 3 public callable records owned by `experiments.research.portfolio`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_portfolio_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.portfolio`

**Purpose:** Continue qualified checkpoints and build matched no-trade controls.

**Exact API:** {py:obj}`experiments.research.portfolio.build_portfolio_bundle` · **Source:** [experiments/research/portfolio.py:77](../../../../experiments/research/portfolio.py#L77)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment: Registered research experiment specification.
  source_commit: Git commit binding the research artifacts.
  gate_path: Path to the survival qualification artifact.
  canonical_config: Repository path to the canonical policy configuration.
  output_root: Base directory for generated research artifacts.
  selected_variants: Variant identifiers selected for this operation.
  ```

- **Returns:**

  ```text
  Result produced by build_portfolio_bundle.
  ```

**Observed usage:**

1. [production caller: `freeze_experiment`](../../../../experiments/research/workflow.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if survival_gate is None:
            raise ValueError("portfolio continuation requires a survival qualification artifact")
        canonical = catalog.experiment("survival_policy").variant("setup_conditioned")
        if canonical.config is None:
            raise ValueError("canonical survival policy has no config")
        return build_portfolio_bundle(
            experiment,
            source_commit=source_commit,
            gate_path=survival_gate,
            canonical_config=canonical.config,
            output_root=output_root,
            selected_variants=selected_variants,
        )
    if kind == "checkpoint_replay":
        if finalist_runs is None:
            raise ValueError("robustness replay requires finalist runs")
        return build_robustness_bundle(
            experiment,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `find_completed_run`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.portfolio`

**Purpose:** Resolve exactly one completed run beneath a variant/seed output root.

**Exact API:** {py:obj}`experiments.research.portfolio.find_completed_run` · **Source:** [experiments/research/portfolio.py:196](../../../../experiments/research/portfolio.py#L196)

**Inputs and outputs:**

- **Args:**

  ```text
  root: Value used for root.
  ```

- **Returns:**

  ```text
  Result produced by find_completed_run.
  ```

**Observed usage:**

1. [production caller: `summarize_portfolio_safety`](../../../../experiments/research/portfolio.py#L229)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    if set(runs) != {42, 43, 44, 45, 46, 47}:
        raise ValueError("portfolio safety requires seeds 42..47")
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for seed, raw_root in sorted(runs.items()):
        run = find_completed_run(raw_root)
        equity_gate = _object(run / "train_equity_gate.json")
        outcome = _object(run / "train_path_outcome.json")
        safe = (
            equity_gate.get("hard_risk_ok") is True
            and equity_gate.get("breached") is False
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `summarize_portfolio_safety`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.portfolio`

**Purpose:** Require every portfolio treatment path to complete without hard-risk breach.

**Exact API:** {py:obj}`experiments.research.portfolio.summarize_portfolio_safety` · **Source:** [experiments/research/portfolio.py:215](../../../../experiments/research/portfolio.py#L215)

**Inputs and outputs:**

- **Args:**

  ```text
  runs: Mapping from seed to run-output root.
  ```

- **Returns:**

  ```text
  Result produced by summarize_portfolio_safety.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L337)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        return 0 if result["status"] == "pass" else 1
    if args.command == "portfolio-safety":
        runs = _finalist_runs(args.run)
        if runs is None:
            raise ValueError("portfolio-safety requires seed paths")
        result = summarize_portfolio_safety(runs)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
