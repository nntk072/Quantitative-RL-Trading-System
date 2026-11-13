# Experiments · `research.release`

This page contains 1 public callable records owned by `experiments.research.release`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `assemble_release`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.release`

**Purpose:** Create a source-bound immutable evidence packet from execution outputs.

**Exact API:** {py:obj}`experiments.research.release.assemble_release` · **Source:** [experiments/research/release.py:44](../../../../experiments/research/release.py#L44)

**Inputs and outputs:**

- **Args:**

  ```text
  consolidated_results: Value used for consolidated results.
  protocol: Value used for protocol.
  catalog: Value used for catalog.
  output_dir: Directory that receives generated artifacts.
  extra_artifacts: Value used for extra artifacts.
  ```

- **Returns:**

  ```text
  Result produced by assemble_release.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L390)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    manifest = assemble_release(
        consolidated_results=args.results,
        protocol=args.protocol,
        catalog=args.catalog,
        output_dir=args.output,
        extra_artifacts=tuple(args.extra),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
