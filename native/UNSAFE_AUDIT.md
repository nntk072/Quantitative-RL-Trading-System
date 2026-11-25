# Unsafe audit of the native crates

Scope: every Rust source file in this repository's own crates (`native/domain`, `native/python`).

## Result

- Occurrences of the `unsafe` keyword in repository-owned Rust: **0**.
- Other unsafe-like constructs (`transmute`, `from_raw`, raw pointer casts, `extern "C"`,
  `static mut`, `#[no_mangle]`): **0**.
- Files audited: `native/domain/src/{lib,units,order,position,account,risk,wire}.rs`,
  `native/domain/tests/properties.rs`, `native/python/src/lib.rs`.

Verification command (run from the repository root; `target/` and `.venv/` excluded):

```text
grep -rn --include=*.rs -E "\bunsafe\b" native
```

The command matched nothing (exit status 1). Re-run it after any change to native code.

## Enforcement

The workspace `Cargo.toml` sets:

```toml
[workspace.lints.rust]
unsafe_code = "forbid"
```

Both member crates opt in with `[lints] workspace = true`. `forbid` cannot be overridden by an
`#[allow(unsafe_code)]` attribute in a crate, so any new `unsafe` block fails the build. The
release wheel and `cargo clippy --workspace --all-targets -- -D warnings` build under this lint.

## Third-party unsafe (PyO3)

`native/python` depends on `pyo3` 0.30.1 (with `pyo3-ffi`, `pyo3-macros`, and
`pyo3-build-config`). These crates contain `unsafe` code that wraps the CPython C API. That code
is outside this repository's audit scope and is not covered by the `forbid` lint on our crates. A
rough textual count in the PyO3 0.30.1 sources in the local cargo registry gave about 1,300
occurrences of `unsafe ` across about 95 files. This is a grep count, not a block count.

PyO3 is the only FFI boundary. The binding contains no raw pointers and no manual reference
counting. Python objects cross the boundary only through PyO3 types (`PyResult`, `#[pyclass]`,
`#[pyfunction]`).

## Remaining risk

- `native/python` relies on PyO3's soundness for interpreter attachment and object lifetime.
  Upgrading PyO3 requires re-running the wheel smoke and parity tests.
- The domain crate is pure safe Rust with checked integer arithmetic. Overflow returns
  `DomainError::Overflow` instead of wrapping.
