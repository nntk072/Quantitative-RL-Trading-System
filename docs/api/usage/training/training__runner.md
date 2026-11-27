# Training · `runner`

This page contains 1 public callable records owned by `training.runner`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `main`

**Kind:** function · **Status:** stable · **Owner:** `training.runner`

**Purpose:** Run the training entry point without importing it during package loading.

**Exact API:** {py:obj}`training.runner.main` · **Source:** [training/runner/__init__.py:1](../../../../training/runner/__init__.py#L1)

**Observed usage:**

1. [test fixture: `test_lazy_training_package_entrypoint_delegates_to_cli`](../../../../tests/unit/training/test_seed_runtime_coverage.py#L427)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lazy_training_package_entrypoint_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    import training.runner as package
    from training.runner import training

    calls: list[str] = []
    monkeypatch.setattr(training, "main", lambda: calls.append("main"))

    package.main()

    assert calls == ["main"]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
