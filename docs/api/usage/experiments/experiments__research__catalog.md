# Experiments · `research.catalog`

This page contains 14 public callable records owned by `experiments.research.catalog`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ExperimentSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** A scientific question with a reusable set of variants.

**Exact API:** {py:obj}`experiments.research.catalog.ExperimentSpec` · **Source:** [experiments/research/catalog.py:52](../../../../experiments/research/catalog.py#L52)

**Observed usage:**

1. [production caller: `load_research_catalog`](../../../../experiments/research/catalog.py#L428)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            for variant in chosen:
                if set(variant.depends_on) - set(members):
                    raise ValueError(f"{experiment_id}/{assembly_id} omits a required dependency")
            assemblies[assembly_id] = members
        experiments.append(
            ExperimentSpec(
                experiment_id=experiment_id,
                domain=domain,
                summary=_string(row.get("summary"), f"experiments.{experiment_id}.summary"),
                selection_role=_string(
                    row.get("selection_role"),
                    f"experiments.{experiment_id}.selection_role",
                ),
                variants=variants,
                assemblies=assemblies,
                execution=_execution(row.get("execution"), experiment_id=experiment_id),
            )
        )
    if not experiments:
        raise ValueError("research catalog requires at least one experiment")
    return ResearchCatalog(
        schema_version=schema,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ResearchCatalog`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Validated active research catalog.

**Exact API:** {py:obj}`experiments.research.catalog.ResearchCatalog` · **Source:** [experiments/research/catalog.py:94](../../../../experiments/research/catalog.py#L94)

**Observed usage:**

1. [production caller: `load_research_catalog`](../../../../experiments/research/catalog.py#L443)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                execution=_execution(row.get("execution"), experiment_id=experiment_id),
            )
        )
    if not experiments:
        raise ValueError("research catalog requires at least one experiment")
    return ResearchCatalog(
        schema_version=schema,
        protocol=protocol,
        domains=domains,
        experiments=tuple(experiments),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `VariantSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** One intervention inside a named research experiment.

**Exact API:** {py:obj}`experiments.research.catalog.VariantSpec` · **Source:** [experiments/research/catalog.py:23](../../../../experiments/research/catalog.py#L23)

**Observed usage:**

1. [production caller: `_variant`](../../../../experiments/research/catalog.py#L256)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ):
            raise ValueError(
                f"experiments.{experiment_id}.variants.{variant_id}.{label} "
                "must be a list of non-empty strings"
            )
    return VariantSpec(
        variant_id=variant_id,
        config=config,
        architecture=architecture,
        role=_string(
            row.get("role", "treatment"),
            f"experiments.{experiment_id}.variants.{variant_id}.role",
        ),
        authorization=authorization,
        overrides=tuple(item.strip() for item in overrides_raw),
        command=tuple(item.strip() for item in command_raw),
        artifact_roots=tuple(item.strip() for item in artifact_roots_raw),
        depends_on=tuple(item.strip() for item in depends_on_raw),
        component=_string(
            row.get("component", domain),
            f"experiments.{experiment_id}.variants.{variant_id}.component",
        ),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_research_catalog`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Load and validate the active research catalog.

**Exact API:** {py:obj}`experiments.research.catalog.load_research_catalog` · **Source:** [experiments/research/catalog.py:325](../../../../experiments/research/catalog.py#L325)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_research_catalog.
  ```

**Observed usage:**

1. [test fixture: `test_active_survival_policies_share_declared_risk_limits`](../../../../tests/unit/experiments/test_experiment_run_policy_overrides.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_active_survival_policies_share_declared_risk_limits() -> None:
    from experiments.research.catalog import load_research_catalog

    experiment = load_research_catalog().experiment("survival_policy")
    assert {"setup_conditioned", "hybrid_control"} <= {
        variant.variant_id for variant in experiment.variants
    }
    for variant in experiment.variants:
        assert variant.config is not None
# … caller assertions omitted …
```

2. [test fixture: `test_library_implementations_can_be_shared_across_studies`](../../../../tests/unit/experiments/test_research_component_registry.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "static_contract",
        "observation_probe",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ExecutionSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Execution contract shared by all variants of an experiment.

**Exact API:** {py:obj}`experiments.research.catalog.ExecutionSpec` · **Source:** [experiments/research/catalog.py:39](../../../../experiments/research/catalog.py#L39)

**Observed usage:**

1. [production caller: `_execution`](../../../../experiments/research/catalog.py#L302)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    resource_lock = (
        None
        if resource_raw is None
        else _string(resource_raw, f"experiments.{experiment_id}.execution.resource_lock")
    )
    return ExecutionSpec(
        kind=_string(row.get("kind"), f"experiments.{experiment_id}.execution.kind"),
        seeds=seeds,
        walk_forward_splits=_integer(
            row.get("walk_forward_splits", 0),
            f"experiments.{experiment_id}.execution.walk_forward_splits",
        ),
        purge_bars=_integer(
            row.get("purge_bars", 0),
            f"experiments.{experiment_id}.execution.purge_bars",
        ),
        embargo_bars=_integer(
            row.get("embargo_bars", 0),
            f"experiments.{experiment_id}.execution.embargo_bars",
        ),
        additional_timesteps=_integer(
            row.get("additional_timesteps", 0),
            f"experiments.{experiment_id}.execution.additional_timesteps",
        ),
        resource_lock=resource_lock,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ExperimentSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** A scientific question with a reusable set of variants.

**Exact API:** {py:obj}`experiments.research.catalog.ExperimentSpec` · **Source:** [experiments/research/catalog.py:52](../../../../experiments/research/catalog.py#L52)

**Observed usage:**

1. [production caller: `load_research_catalog`](../../../../experiments/research/catalog.py#L428)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            for variant in chosen:
                if set(variant.depends_on) - set(members):
                    raise ValueError(f"{experiment_id}/{assembly_id} omits a required dependency")
            assemblies[assembly_id] = members
        experiments.append(
            ExperimentSpec(
                experiment_id=experiment_id,
                domain=domain,
                summary=_string(row.get("summary"), f"experiments.{experiment_id}.summary"),
                selection_role=_string(
                    row.get("selection_role"),
                    f"experiments.{experiment_id}.selection_role",
                ),
                variants=variants,
                assemblies=assemblies,
                execution=_execution(row.get("execution"), experiment_id=experiment_id),
            )
        )
    if not experiments:
        raise ValueError("research catalog requires at least one experiment")
    return ResearchCatalog(
        schema_version=schema,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ExperimentSpec.variant`

**Kind:** method · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Return one registered variant or fail closed.

**Exact API:** {py:obj}`experiments.research.catalog.ExperimentSpec.variant` · **Source:** [experiments/research/catalog.py:78](../../../../experiments/research/catalog.py#L78)

**Inputs and outputs:**

- **Args:**

  ```text
  variant_id: Registered variant identifier.
  ```

- **Returns:**

  ```text
  Result produced by variant.
  ```

**Observed usage:**

1. [production caller: `variants_for_assembly`](../../../../experiments/research/catalog.py#L76)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def variants_for_assembly(self, assembly_id: str) -> tuple[VariantSpec, ...]:
    try:
        members = self.assemblies[assembly_id]
    except KeyError as exc:
        raise KeyError(f"unknown assembly {assembly_id!r} for {self.experiment_id!r}") from exc
    return tuple(self.variant(member) for member in members)
```

2. [production caller: `build_portfolio_bundle`](../../../../experiments/research/portfolio.py#L112)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    valid = {"qualified_policy", "always_no_trade"}
    if selected - valid:
        raise ValueError(
            f"{experiment.experiment_id} has no variants named {sorted(selected - valid)}"
        )
    treatment = experiment.variant("qualified_policy")
    control = experiment.variant("always_no_trade")
    if treatment.role != "treatment" or control.role != "primary_control":
        raise ValueError("portfolio roles differ from the registered primary contrast")

    commands: list[CommandSpec] = []
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ExperimentSpec.variants_for_assembly`

**Kind:** method · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Resolve a named group of component implementations.

**Exact API:** {py:obj}`experiments.research.catalog.ExperimentSpec.variants_for_assembly` · **Source:** [experiments/research/catalog.py:63](../../../../experiments/research/catalog.py#L63)

**Inputs and outputs:**

- **Args:**

  ```text
  assembly_id: Registered selection of compatible experiment variants.
  ```

- **Returns:**

  ```text
  Variant specifications in the order declared by the assembly.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ExperimentSpec(...)
result = instance.variants_for_assembly(assembly_id=...)
```

**Lifecycle context:** This callable participates in `ExperimentSpec`: A scientific question with a reusable set of variants. Related public lifecycle methods: {py:obj}`experiments.research.catalog.ExperimentSpec.variants_for_assembly`, {py:obj}`experiments.research.catalog.ExperimentSpec.variant`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ResearchCatalog`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Validated active research catalog.

**Exact API:** {py:obj}`experiments.research.catalog.ResearchCatalog` · **Source:** [experiments/research/catalog.py:94](../../../../experiments/research/catalog.py#L94)

**Observed usage:**

1. [production caller: `load_research_catalog`](../../../../experiments/research/catalog.py#L443)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                execution=_execution(row.get("execution"), experiment_id=experiment_id),
            )
        )
    if not experiments:
        raise ValueError("research catalog requires at least one experiment")
    return ResearchCatalog(
        schema_version=schema,
        protocol=protocol,
        domains=domains,
        experiments=tuple(experiments),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ResearchCatalog.by_domain`

**Kind:** method · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Return all experiments in one research domain.

**Exact API:** {py:obj}`experiments.research.catalog.ResearchCatalog.by_domain` · **Source:** [experiments/research/catalog.py:116](../../../../experiments/research/catalog.py#L116)

**Inputs and outputs:**

- **Args:**

  ```text
  domain: Research domain identifier.
  ```

- **Returns:**

  ```text
  Result produced by by_domain.
  ```

**Observed usage:**

1. [production caller: `main`](../../../../experiments/research/cli.py#L217)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    args = parser.parse_args(argv)
    catalog = load_research_catalog(args.catalog)

    if args.command == "catalog":
        experiments = (
            catalog.by_domain(args.domain) if args.domain is not None else catalog.experiments
        )
        catalog_rows = []
        for item in experiments:
            variants = [
                variant
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `ResearchCatalog.experiment`

**Kind:** method · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Return one registered experiment or fail closed.

**Exact API:** {py:obj}`experiments.research.catalog.ResearchCatalog.experiment` · **Source:** [experiments/research/catalog.py:102](../../../../experiments/research/catalog.py#L102)

**Inputs and outputs:**

- **Args:**

  ```text
  experiment_id: Registered research experiment identifier.
  ```

- **Returns:**

  ```text
  Result produced by experiment.
  ```

**Observed usage:**

1. [test fixture: `test_active_survival_policies_share_declared_risk_limits`](../../../../tests/unit/experiments/test_experiment_run_policy_overrides.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_active_survival_policies_share_declared_risk_limits() -> None:
    from experiments.research.catalog import load_research_catalog

    experiment = load_research_catalog().experiment("survival_policy")
    assert {"setup_conditioned", "hybrid_control"} <= {
        variant.variant_id for variant in experiment.variants
    }
    for variant in experiment.variants:
        assert variant.config is not None
# … caller assertions omitted …
```

2. [test fixture: `test_library_implementations_can_be_shared_across_studies`](../../../../tests/unit/experiments/test_research_component_registry.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "observation_probe",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
        catalog.experiment("research_contract"),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `VariantSpec`

**Kind:** class · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** One intervention inside a named research experiment.

**Exact API:** {py:obj}`experiments.research.catalog.VariantSpec` · **Source:** [experiments/research/catalog.py:23](../../../../experiments/research/catalog.py#L23)

**Observed usage:**

1. [production caller: `_variant`](../../../../experiments/research/catalog.py#L256)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ):
            raise ValueError(
                f"experiments.{experiment_id}.variants.{variant_id}.{label} "
                "must be a list of non-empty strings"
            )
    return VariantSpec(
        variant_id=variant_id,
        config=config,
        architecture=architecture,
        role=_string(
            row.get("role", "treatment"),
            f"experiments.{experiment_id}.variants.{variant_id}.role",
        ),
        authorization=authorization,
        overrides=tuple(item.strip() for item in overrides_raw),
        command=tuple(item.strip() for item in command_raw),
        artifact_roots=tuple(item.strip() for item in artifact_roots_raw),
        depends_on=tuple(item.strip() for item in depends_on_raw),
        component=_string(
            row.get("component", domain),
            f"experiments.{experiment_id}.variants.{variant_id}.component",
        ),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_research_catalog`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Load and validate the active research catalog.

**Exact API:** {py:obj}`experiments.research.catalog.load_research_catalog` · **Source:** [experiments/research/catalog.py:325](../../../../experiments/research/catalog.py#L325)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_research_catalog.
  ```

**Observed usage:**

1. [test fixture: `test_active_survival_policies_share_declared_risk_limits`](../../../../tests/unit/experiments/test_experiment_run_policy_overrides.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_active_survival_policies_share_declared_risk_limits() -> None:
    from experiments.research.catalog import load_research_catalog

    experiment = load_research_catalog().experiment("survival_policy")
    assert {"setup_conditioned", "hybrid_control"} <= {
        variant.variant_id for variant in experiment.variants
    }
    for variant in experiment.variants:
        assert variant.config is not None
# … caller assertions omitted …
```

2. [test fixture: `test_library_implementations_can_be_shared_across_studies`](../../../../tests/unit/experiments/test_research_component_registry.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "static_contract",
        "observation_probe",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`

## `load_research_catalog`

**Kind:** function · **Status:** experimental · **Owner:** `experiments.research.catalog`

**Purpose:** Load and validate the active research catalog.

**Exact API:** {py:obj}`experiments.research.catalog.load_research_catalog` · **Source:** [experiments/research/catalog.py:325](../../../../experiments/research/catalog.py#L325)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input or output artifact.
  ```

- **Returns:**

  ```text
  Result produced by load_research_catalog.
  ```

**Observed usage:**

1. [test fixture: `test_active_survival_policies_share_declared_risk_limits`](../../../../tests/unit/experiments/test_experiment_run_policy_overrides.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_active_survival_policies_share_declared_risk_limits() -> None:
    from experiments.research.catalog import load_research_catalog

    experiment = load_research_catalog().experiment("survival_policy")
    assert {"setup_conditioned", "hybrid_control"} <= {
        variant.variant_id for variant in experiment.variants
    }
    for variant in experiment.variants:
        assert variant.config is not None
# … caller assertions omitted …
```

2. [test fixture: `test_library_implementations_can_be_shared_across_studies`](../../../../tests/unit/experiments/test_research_component_registry.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "static_contract",
        "observation_probe",
    ]
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    catalog = load_research_catalog(path)
    probe = catalog.experiment("research_contract").variant("observation_probe")
    original = catalog.experiment("feature_inputs").variant("observation_validity")
    assert probe.component == original.component == "observations"
    assert probe.command == original.command
    reused = build_command_group_bundle(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
