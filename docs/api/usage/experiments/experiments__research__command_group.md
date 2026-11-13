# Experiments · `research.command_group`

This page contains 1 public callable records owned by `experiments.research.command_group`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_command_group_bundle`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.command_group`

**Purpose:** Build reusable commands declared directly by experiment variants.

**Exact API:** {py:obj}`experiments.research.command_group.build_command_group_bundle` · **Source:** [experiments/research/command_group.py:14](../../../../experiments/research/command_group.py#L14)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment: Registered research experiment specification.
  source_commit: Git commit binding the research artifacts.
  output_root: Base directory for generated research artifacts.
  selected_variants: Variant identifiers selected for this operation.
  readiness: Source-bound scientific-readiness record.
  ```

- **Returns:**

  ```text
  Source-bound commands with experiment-scoped artifact paths.
  ```

**Observed usage:**

1. [test fixture: `test_library_implementations_can_be_shared_across_studies`](../../../../tests/unit/experiments/test_research_component_registry.py#L41)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
        catalog.experiment("research_contract"),
        source_commit="a" * 40,
        output_root="outputs/research",
    )
    existing = build_command_group_bundle(
        catalog.experiment("feature_inputs"),
        source_commit="a" * 40,
        output_root="outputs/research",
    )
# … caller assertions omitted …
```

2. [test fixture: `test_selected_component_cannot_discard_its_dependencies`](../../../../tests/unit/experiments/test_research_composition.py#L71)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        for item in experiment.variants
    )
    experiment = replace(experiment, variants=variants)

    with pytest.raises(ValueError, match="requires variants"):
        build_command_group_bundle(
            experiment,
            source_commit="a" * 40,
            output_root="outputs/research",
            selected_variants=("opportunity_census",),
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
