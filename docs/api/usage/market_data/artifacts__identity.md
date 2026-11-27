# Market data · `artifacts.identity`

This page contains 1 public callable records owned by `artifacts.identity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `file_sha256`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.identity`

**Purpose:** Hash file contents in bounded memory for artifact provenance.

**Exact API:** {py:obj}`artifacts.identity.file_sha256` · **Source:** [artifacts/identity.py:47](../../../../artifacts/identity.py#L47)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  Text returned by ``file_sha256``.
  ```

**Observed usage:**

1. [test fixture: `_write_alignment`](../../../../tests/integration/backtest/test_local_trace_source_clock.py#L120)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                        "stable_parser_first_valid_ask": 100.25,
                    },
                }
            )
    alignment = {
        "tick_source_sha256": file_sha256(ticks),
        "price_grid_application": {"increment": 0.25},
        "events": events,
    }
    if source_timezone is not None:
        alignment["source_timezone_used_for_timestamp_join"] = source_timezone
# … caller assertions omitted …
```

2. [test fixture: `test_file_sha256_matches_standard_digest_for_empty_and_nonempty_files`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_file_sha256_matches_standard_digest_for_empty_and_nonempty_files(
    tmp_path: Path,
) -> None:
    payload = b"artifact bytes\x00with boundaries"
    nonempty = tmp_path / "payload.bin"
    empty = tmp_path / "empty.bin"
    nonempty.write_bytes(payload)
    empty.write_bytes(b"")

    assert file_sha256(nonempty) == hashlib.sha256(payload).hexdigest()
    assert file_sha256(empty) == hashlib.sha256(b"").hexdigest()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
