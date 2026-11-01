# Artifacts · `retention`

This page contains 1 public callable records owned by `artifacts.retention`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RetentionClass`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.retention`

**Purpose:** Retention policies for generated artifacts.

**Exact API:** {py:obj}`artifacts.retention.RetentionClass` · **Source:** [artifacts/retention.py:6](../../../../artifacts/retention.py#L6)

**Observed usage:**

1. [production caller: `read`](../../../../artifacts/manifest.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("artifact manifest root must be a mapping")
        try:
            data = dict(data)
            data["retention"] = RetentionClass(data.get("retention", RetentionClass.RUN_RETAINED))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"artifact manifest has invalid retention: {exc}") from exc
        parents = data.get("parents", ())
        if not isinstance(parents, (list, tuple)):
            raise ValueError("artifact manifest parents must be a sequence of artifact ids")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
