# Artifacts · `promotion`

This page contains 3 public callable records owned by `artifacts.promotion`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `BaselineValidation`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.promotion`

**Purpose:** Validation evidence returned only after every promotion check passes.

**Exact API:** {py:obj}`artifacts.promotion.BaselineValidation` · **Source:** [artifacts/promotion.py:18](../../../../artifacts/promotion.py#L18)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineValidation(...)
```

**Lifecycle context:** Validation evidence returned only after every promotion check passes.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `promote_to_baseline`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.promotion`

**Purpose:** Validate and atomically publish an artifact as a baseline directory.

**Exact API:** {py:obj}`artifacts.promotion.promote_to_baseline` · **Source:** [artifacts/promotion.py:99](../../../../artifacts/promotion.py#L99)

**Inputs and outputs:**

- **Args:**

  ```text
  source: Path or filename identifying the source.
  destination: Destination used by the operation described above.
  manifest: Manifest used by the operation described above.
  validate: Validate used by the operation described above.
  ```

- **Returns:**

  ```text
  Path returned by ``promote_to_baseline``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = promote_to_baseline(source=..., destination=..., manifest=..., validate=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `BaselineValidation.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.promotion`

**Purpose:** Return validation results as a JSON-compatible mapping.

**Exact API:** {py:obj}`artifacts.promotion.BaselineValidation.to_dict` · **Source:** [artifacts/promotion.py:31](../../../../artifacts/promotion.py#L31)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = BaselineValidation(...)
result = instance.to_dict()
```

**Lifecycle context:** This callable participates in `BaselineValidation`: Validation evidence returned only after every promotion check passes. Related public lifecycle methods: {py:obj}`artifacts.promotion.BaselineValidation.to_dict`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
