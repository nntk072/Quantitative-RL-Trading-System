# Configuration · `paths`

This page contains 2 public callable records owned by `configuration.paths`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RepositoryPaths`

**Kind:** class · **Status:** stable · **Owner:** `configuration.paths`

**Purpose:** Canonical repository locations derived from one root directory.

**Exact API:** {py:obj}`configuration.paths.RepositoryPaths` · **Source:** [configuration/paths.py:8](../../../../configuration/paths.py#L8)

**Inputs and outputs:**

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RepositoryPaths(...)
```

**Lifecycle context:** Canonical repository locations derived from one root directory.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `RepositoryPaths.from_root`

**Kind:** method · **Status:** stable · **Owner:** `configuration.paths`

**Purpose:** Resolve canonical repository paths beneath a root.

**Exact API:** {py:obj}`configuration.paths.RepositoryPaths.from_root` · **Source:** [configuration/paths.py:30](../../../../configuration/paths.py#L30)

**Inputs and outputs:**

- **Args:**

  ```text
  root: Repository directory to use as the path anchor.
  ```

- **Returns:**

  ```text
  Paths for configuration, data, cache, outputs, logs, and baselines.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = RepositoryPaths.from_root(root=...)
```

**Lifecycle context:** This callable participates in `RepositoryPaths`: Canonical repository locations derived from one root directory. Related public lifecycle methods: {py:obj}`configuration.paths.RepositoryPaths.from_root`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
