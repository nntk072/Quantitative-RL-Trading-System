# Experiments · `research.reporting_tables`

This page contains 1 public callable records owned by `experiments.research.reporting_tables`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_research_tables`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.reporting_tables`

**Purpose:** Write compact domain/experiment summaries without inventing missing outcomes.

**Exact API:** {py:obj}`experiments.research.reporting_tables.build_research_tables` · **Source:** [experiments/research/reporting_tables.py:26](../../../../experiments/research/reporting_tables.py#L26)

**Inputs and outputs:**

- **Args:**

  ```text
  results_path: Path to consolidated research results.
  output_dir: Directory that receives generated artifacts.
  ```

- **Returns:**

  ```text
  Result produced by build_research_tables.
  ```

**Observed usage:**

1. [test fixture: `test_results_retain_command_and_source_identity`](../../../../tests/unit/experiments/test_research_composition.py#L121)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    with (output / "results.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert csv_rows[0]["component"] == "opportunities"
    assert csv_rows[0]["source_commit"] == "a" * 40

    table = build_research_tables(output / "results.json", output / "tables")
    assert table["row_count"] == 1
    with (output / "tables" / "research_result_inventory.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        summary = list(csv.DictReader(stream))
# … caller assertions omitted …
```

2. [production caller: `main`](../../../../experiments/research/cli.py#L364)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        write_json_atomic(args.payload, payload)
        write_json_atomic(args.analysis, analysis)
        print(json.dumps(analysis, indent=2, sort_keys=True))
        return 0
    if args.command == "tables":
        result = build_research_tables(args.results, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "compute-budget":
        fps: dict[int, float] = {}
        for raw in args.fps:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
