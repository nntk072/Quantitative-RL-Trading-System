# Configuration · `schema`

This page contains 1 public callable records owned by `configuration.schema`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ConfigSchemaError`

**Kind:** class · **Status:** stable · **Owner:** `configuration.schema`

**Purpose:** Raised when configuration data violates the repository schema.

**Exact API:** {py:obj}`configuration.schema.ConfigSchemaError` · **Source:** [configuration/schema.py:9](../../../../configuration/schema.py#L9)

**Observed usage:**

1. [production caller: `reject_unknown_keys`](../../../../configuration/schema.py#L27)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise ConfigSchemaError(f"unknown keys at {path}: {unknown}")
    for key, value in values.items():
        schema_value = schema[key]
        value_is_mapping = isinstance(value, Mapping)
        schema_is_mapping = isinstance(schema_value, Mapping)
        if value_is_mapping and not schema_is_mapping:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
