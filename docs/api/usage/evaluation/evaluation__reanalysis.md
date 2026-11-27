# Evaluation · `reanalysis`

This page contains 1 public callable records owned by `evaluation.reanalysis`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `main`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reanalysis`

**Purpose:** Run the reanalysis entry point without importing it during package loading.

**Exact API:** {py:obj}`evaluation.reanalysis.main` · **Source:** [evaluation/reanalysis/__init__.py:1](../../../../evaluation/reanalysis/__init__.py#L1)

**Observed usage:**

1. [test fixture: `test_lazy_reanalysis_package_entrypoint_delegates_to_cli`](../../../../tests/unit/evaluation/test_eval_run_provenance.py#L1464)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lazy_reanalysis_package_entrypoint_delegates_to_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evaluation.reanalysis as package
    from evaluation.reanalysis import checkpoint_reanalysis

    calls: list[str] = []
    monkeypatch.setattr(checkpoint_reanalysis, "main", lambda: calls.append("main"))

    package.main()

    assert calls == ["main"]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
