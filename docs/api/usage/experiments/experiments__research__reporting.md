# Experiments · `research.reporting`

This page contains 5 public callable records owned by `experiments.research.reporting`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ResultRow`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.reporting`

**Purpose:** One normalized research result record.

**Exact API:** {py:obj}`experiments.research.reporting.ResultRow` · **Source:** [experiments/research/reporting.py:27](../../../../experiments/research/reporting.py#L27)

**Observed usage:**

1. [test fixture: `test_consolidation_rejects_conflicting_records`](../../../../tests/unit/experiments/test_research_composition.py#L132)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_consolidation_rejects_conflicting_records(tmp_path: Path) -> None:
    record = ResultRow(
        domain="data",
        experiment="data_integrity",
        variant="denominator_register",
        component="data",
        command_id="denominator_register",
        seed=None,
        source_commit="a" * 40,
        status="passed",
        artifact=str(tmp_path / "data.json"),
        metrics={"rows": 3},
    )
    with pytest.raises(ValueError, match="conflicting results"):
        consolidate_results((record, replace(record, status="failed")), tmp_path / "out")
```

2. [production caller: `read_result_artifact`](../../../../experiments/research/reporting.py#L124)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        elif value.get("completed_data_split") is True or value.get("survived_full_period") is True:
            status = "passed"
        else:
            status = "recorded"
    metrics_source = value.get("metrics") if isinstance(value.get("metrics"), dict) else value
    return ResultRow(
        domain=domain,
        experiment=experiment,
        variant=variant,
        seed=seed,
        status=status,
        artifact=str(path.resolve()),
        metrics=_scalar_metrics(metrics_source),
        component=component,
        command_id=command_id,
        source_commit=source_commit,
        artifact_sha256=artifact_sha256,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `consolidate_execution_manifests`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.reporting`

**Purpose:** Consolidate execution manifests into one domain-oriented result catalog.

**Exact API:** {py:obj}`experiments.research.reporting.consolidate_execution_manifests` · **Source:** [experiments/research/reporting.py:290](../../../../experiments/research/reporting.py#L290)

**Inputs and outputs:**

- **Args:**

  ```text
  manifests: Execution manifests to consolidate.
  output_dir: Directory that receives generated artifacts.
  ```

- **Returns:**

  ```text
  Result produced by consolidate_execution_manifests.
  ```

**Observed usage:**

1. [test fixture: `test_explicit_seed_and_result_artifact_survive_consolidation`](../../../../tests/unit/experiments/test_research_component_registry.py#L125)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "consolidated"
    payload = consolidate_execution_manifests([manifest], output)
    assert payload["results"][0]["seed"] == 27
    assert payload["results"][0]["artifact_sha256"] == digest
    with (output / "metrics.csv").open(encoding="utf-8", newline="") as stream:
        metrics = list(csv.DictReader(stream))
    assert len(metrics) == 1
# … caller assertions omitted …
```

2. [test fixture: `test_consolidation_rejects_modified_result_artifact`](../../../../tests/unit/experiments/test_research_result_integrity.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_consolidation_rejects_modified_result_artifact(tmp_path: Path) -> None:
    result = tmp_path / "metrics.json"
    result.write_text('{"metrics":{"observations":12}}', encoding="utf-8")
    manifest = _manifest(tmp_path / "run.json", result, file_sha256(result))
    result.write_text('{"metrics":{"observations":13}}', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        consolidate_execution_manifests([manifest], tmp_path / "changed")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `consolidate_results`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.reporting`

**Purpose:** Write one JSON catalog and one flat CSV for active research results.

**Exact API:** {py:obj}`experiments.research.reporting.consolidate_results` · **Source:** [experiments/research/reporting.py:311](../../../../experiments/research/reporting.py#L311)

**Inputs and outputs:**

- **Args:**

  ```text
  rows: Normalized result rows to consolidate.
  output_dir: Directory that receives generated artifacts.
  ```

- **Returns:**

  ```text
  Structured result catalog also written as wide and long-form CSV datasets.
  ```

**Observed usage:**

1. [test fixture: `test_results_retain_command_and_source_identity`](../../../../tests/unit/experiments/test_research_composition.py#L114)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert rows[0].command_id == "opportunity_census"
    assert rows[0].source_commit == "a" * 40
    assert rows[0].metrics["eligible_events"] == 12

    output = tmp_path / "results"
    payload = consolidate_results((*rows, *rows), output)
    assert len(payload["results"]) == 1
    with (output / "results.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert csv_rows[0]["component"] == "opportunities"
    assert csv_rows[0]["source_commit"] == "a" * 40
# … caller assertions omitted …
```

2. [test fixture: `test_consolidation_rejects_conflicting_records`](../../../../tests/unit/experiments/test_research_composition.py#L145)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        status="passed",
        artifact=str(tmp_path / "data.json"),
        metrics={"rows": 3},
    )
    with pytest.raises(ValueError, match="conflicting results"):
        consolidate_results((record, replace(record, status="failed")), tmp_path / "out")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `read_result_artifact`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.reporting`

**Purpose:** Normalize one JSON result artifact without experiment-specific parsing code.

**Exact API:** {py:obj}`experiments.research.reporting.read_result_artifact` · **Source:** [experiments/research/reporting.py:80](../../../../experiments/research/reporting.py#L80)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  domain: Research domain identifier.
  experiment: Registered research experiment specification.
  variant: Value used for variant.
  seed: Random seed used for deterministic sampling.
  component: Reusable research component that produced the artifact.
  command_id: Exact command identity in the execution manifest.
  source_commit: Source revision used to produce the result.
  artifact_sha256: Recorded content digest of the selected result artifact.
  ```

- **Returns:**

  ```text
  Structured observation with verified artifact identity when a digest is supplied.
  ```

**Observed usage:**

1. [production caller: `rows_from_execution_manifest`](../../../../experiments/research/reporting.py#L246)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                )
        if artifact is not None and artifact.is_file():
            recorded_digest = artifacts.get(str(artifact))
            if status == "passed" and not isinstance(recorded_digest, str):
                raise ValueError(f"{command_id}: result artifact has no recorded SHA-256")
            row = read_result_artifact(
                artifact,
                domain=domain,
                experiment=experiment,
                variant=variant,
                seed=seed,
                component=component,
                command_id=command_id,
                source_commit=source_commit,
                artifact_sha256=recorded_digest if isinstance(recorded_digest, str) else None,
            )
            rows.append(
                ResultRow(
                    domain=row.domain,
                    experiment=row.experiment,
                    variant=row.variant,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `rows_from_execution_manifest`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.reporting`

**Purpose:** Convert one command execution manifest into normalized result rows.

**Exact API:** {py:obj}`experiments.research.reporting.rows_from_execution_manifest` · **Source:** [experiments/research/reporting.py:176](../../../../experiments/research/reporting.py#L176)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Observations that retain execution status, seed, and source provenance.
  ```

**Observed usage:**

1. [test fixture: `test_results_retain_command_and_source_identity`](../../../../tests/unit/experiments/test_research_composition.py#L106)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = rows_from_execution_manifest(manifest)
    assert len(rows) == 1
    assert rows[0].component == "opportunities"
    assert rows[0].command_id == "opportunity_census"
    assert rows[0].source_commit == "a" * 40
    assert rows[0].metrics["eligible_events"] == 12
# … caller assertions omitted …
```

2. [production caller: `consolidate_execution_manifests`](../../../../experiments/research/reporting.py#L306)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def consolidate_execution_manifests(
    manifests: Iterable[Path],
    output_dir: Path,
) -> dict[str, Any]:
    rows = [
        row
        for manifest in manifests
        for row in rows_from_execution_manifest(manifest.expanduser().resolve())
    ]
    return consolidate_results(rows, output_dir)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
