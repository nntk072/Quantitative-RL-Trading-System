# Configuration · `hashing`

This page contains 1 public callable records owned by `configuration.hashing`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `config_sha256`

**Kind:** function · **Status:** stable · **Owner:** `configuration.hashing`

**Purpose:** Hash the canonical representation of a configuration mapping.

**Exact API:** {py:obj}`configuration.hashing.config_sha256` · **Source:** [configuration/hashing.py:23](../../../../configuration/hashing.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values to serialize deterministically.
  ```

- **Returns:**

  ```text
  Lowercase SHA-256 hex digest.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = config_sha256(config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
