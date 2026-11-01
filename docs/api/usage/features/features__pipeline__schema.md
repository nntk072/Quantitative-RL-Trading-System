# Features · `pipeline.schema`

This page contains 4 public callable records owned by `features.pipeline.schema`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `select_legacy_obs_columns`

**Kind:** function · **Status:** compatibility-only · **Owner:** `features.pipeline.schema`

**Purpose:** Reproduce the pre-sequence-schema observation filter for explicit legacy replay.

**Exact API:** {py:obj}`features.pipeline.schema.select_legacy_obs_columns` · **Source:** [features/pipeline/schema.py:125](../../../../features/pipeline/schema.py#L125)

**Inputs and outputs:**

- **Args:**

  ```text
  features: Feature values supplied to the operation.
  raw_columns: Items supplied for the raw columns, in input order.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``select_legacy_obs_columns``.
  ```

**Observed usage:**

1. [production caller: `select_obs_columns`](../../../../features/pipeline/schema.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def select_obs_columns(
    features: pd.DataFrame,
    raw_columns: tuple[str, ...] | list[str] = (),
) -> pd.DataFrame:
    legacy = select_legacy_obs_columns(features, raw_columns)
    metadata_cols = [
        str(column)
        for column in legacy.columns
        if str(column).endswith(OBSERVATION_METADATA_SUFFIXES)
    ]
    return legacy.drop(columns=metadata_cols)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `select_obs_columns`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.schema`

**Purpose:** Select model columns, excluding raw prices and absolute metadata.

**Exact API:** {py:obj}`features.pipeline.schema.select_obs_columns` · **Source:** [features/pipeline/schema.py:152](../../../../features/pipeline/schema.py#L152)

**Inputs and outputs:**

- **Args:**

  ```text
  features: Feature values supplied to the operation.
  raw_columns: Items supplied for the raw columns, in input order.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``select_obs_columns``.
  ```

**Observed usage:**

1. [test fixture: `test_entry_ideas_are_multi_hot_and_keep_source_timeframes`](../../../../tests/unit/features/test_entry_ideas.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        }
    )

    ideas = build_entry_idea_features(source)
    context = entry_idea_context(pd.concat([source, ideas], axis=1).iloc[0], 1)
    model_features = select_obs_columns(ideas)

    assert ideas.loc[0, "entry_idea_long_count"] == 4.0
    assert ideas.loc[0, "entry_idea_overlap_long"] == 1.0
    assert set(ideas.columns).issubset(model_features.columns)
    assert context["ideas"] == ["po3", "order_block", "standard_deviation", "fvg_retest"]
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `select_legacy_obs_columns`

**Kind:** function · **Status:** compatibility-only · **Owner:** `features.pipeline.schema`

**Purpose:** Reproduce the pre-sequence-schema observation filter for explicit legacy replay.

**Exact API:** {py:obj}`features.pipeline.schema.select_legacy_obs_columns` · **Source:** [features/pipeline/schema.py:125](../../../../features/pipeline/schema.py#L125)

**Inputs and outputs:**

- **Args:**

  ```text
  features: Feature values supplied to the operation.
  raw_columns: Items supplied for the raw columns, in input order.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``select_legacy_obs_columns``.
  ```

**Observed usage:**

1. [production caller: `select_obs_columns`](../../../../features/pipeline/schema.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def select_obs_columns(
    features: pd.DataFrame,
    raw_columns: tuple[str, ...] | list[str] = (),
) -> pd.DataFrame:
    legacy = select_legacy_obs_columns(features, raw_columns)
    metadata_cols = [
        str(column)
        for column in legacy.columns
        if str(column).endswith(OBSERVATION_METADATA_SUFFIXES)
    ]
    return legacy.drop(columns=metadata_cols)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `select_obs_columns`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.schema`

**Purpose:** Select model columns, excluding raw prices and absolute metadata.

**Exact API:** {py:obj}`features.pipeline.schema.select_obs_columns` · **Source:** [features/pipeline/schema.py:152](../../../../features/pipeline/schema.py#L152)

**Inputs and outputs:**

- **Args:**

  ```text
  features: Feature values supplied to the operation.
  raw_columns: Items supplied for the raw columns, in input order.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``select_obs_columns``.
  ```

**Observed usage:**

1. [test fixture: `test_entry_ideas_are_multi_hot_and_keep_source_timeframes`](../../../../tests/unit/features/test_entry_ideas.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        }
    )

    ideas = build_entry_idea_features(source)
    context = entry_idea_context(pd.concat([source, ideas], axis=1).iloc[0], 1)
    model_features = select_obs_columns(ideas)

    assert ideas.loc[0, "entry_idea_long_count"] == 4.0
    assert ideas.loc[0, "entry_idea_overlap_long"] == 1.0
    assert set(ideas.columns).issubset(model_features.columns)
    assert context["ideas"] == ["po3", "order_block", "standard_deviation", "fvg_retest"]
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
