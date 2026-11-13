# Experiments · `research.history`

This page contains 3 public callable records owned by `experiments.research.history`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `HistoricalEvidence`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.history`

**Purpose:** One normalized historical evidence collection.

**Exact API:** {py:obj}`experiments.research.history.HistoricalEvidence` · **Source:** [experiments/research/history.py:17](../../../../experiments/research/history.py#L17)

**Observed usage:**

1. [production caller: `load_history`](../../../../experiments/research/history.py#L71)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            raise ValueError(f"historical evidence path escapes repository: {raw_path}")
        source = (ROOT / relative).resolve()
        if not source.is_dir():
            raise FileNotFoundError(source)
        result.append(
            HistoricalEvidence(
                evidence_id=evidence_id,
                domain=domain,
                path=source,
                disposition=disposition,
                summary=summary,
            )
        )
    return tuple(result)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_history`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.history`

**Purpose:** Load historical evidence without modifying source artifacts.

**Exact API:** {py:obj}`experiments.research.history.load_history` · **Source:** [experiments/research/history.py:27](../../../../experiments/research/history.py#L27)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_history.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L296)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "history":
        text = render_markdown(load_history(args.history))
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `render_markdown`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.history`

**Purpose:** Render a concise domain-oriented index while retaining source paths.

**Exact API:** {py:obj}`experiments.research.history.render_markdown` · **Source:** [experiments/research/history.py:82](../../../../experiments/research/history.py#L82)

**Inputs and outputs:**

- **Args:**

  ```text
  entries: Historical evidence records to render.
  ```

- **Returns:**

  ```text
  Result produced by render_markdown.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L296)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "history":
        text = render_markdown(load_history(args.history))
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
