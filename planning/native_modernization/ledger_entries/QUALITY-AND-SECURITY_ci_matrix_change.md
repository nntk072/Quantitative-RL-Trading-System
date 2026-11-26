# QUALITY-AND-SECURITY: native CI matrix decision

Decision: `.github/workflows/ci.yml` is **not edited** by the QUALITY-AND-SECURITY commit. The
native job below is the exact change to apply in a separate, owner-approved workflow commit.

## Why the workflow was not edited

1. The only way to make a native job a required gate is to add it to the `needs` list of the
   `ci-success` job. That edits an existing job. The work package allows a workflow edit only
   when the Python-only jobs are untouched, so the layout does not allow a gated addition.
2. Every existing job runs a named `./tools/check <gate>` through `uv`. No `tools/check` gate runs
   cargo. A native job outside that dispatcher would bypass the named-gate contract in
   `.agents/rules/ci-verification.md`.
3. An ungated native job would pass or fail without affecting `ci-success`, which is a weaker gate
   than the work package requires.

## Required change (not applied)

### A. Add one job after `training-smoke` and before `ci-success`

```yaml
  native-domain:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        # Add ubuntu-24.04-arm only after hosted aarch64 runner access is confirmed for this
        # repository. The GH200 node is not a hosted runner (see NATIVE-TOOLCHAIN).
        os: [ubuntu-latest]
    steps:
      - uses: actions/checkout@v4
      # rust-toolchain.toml pins 1.100.0 (clippy, rustfmt); rustup selects it automatically.
      - run: rustup show active-toolchain
      - run: cargo fmt --all -- --check
      - run: cargo clippy --workspace --all-targets -- -D warnings
      - run: cargo test --workspace
      - run: cargo install cargo-audit --version 0.23.0 --locked
      - run: cargo audit --deny warnings
      - uses: astral-sh/setup-uv@v5
        with:
          version: "0.12.17"
      - name: Build the CPU wheel and import it
        run: |
          uvx maturin==1.9.4 build --release -i python3.12 --out target/wheels -m native/python/Cargo.toml
          uv venv --python 3.12 .venv-native
          uv pip install --python .venv-native/bin/python target/wheels/*.whl pytest
          .venv-native/bin/python -c "import qrl_native"
      - name: Native Python parity and boundary tests (no skips allowed)
        run: .venv-native/bin/python -m pytest native/python/tests -q -rs
```

The explicit `import qrl_native` step is required. The Python tests use
`pytest.importorskip("qrl_native")`, which turns a missing module into skipped tests, so the job
would otherwise pass with nothing executed.

### B. Add the job to the aggregator

In the existing `ci-success` job, change only its `needs` list:

```yaml
    needs: [dependency-lock, security-deps, security-secrets, quality, docs, architecture, graph-quality, contracts, unit, build-smoke, integration, coverage-report, parity, training-smoke, native-domain]
```

No other line of the Python-only jobs changes.

### C. Scope

- Apply on `main-native` only. `main` is Python-only and has no `native/` tree, so the job must not
  be cherry-picked to `main`.
- Local equivalents for each hosted step, run on the exact candidate before the push:
  - `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
    `cargo test --workspace`, `cargo audit --deny warnings` (with the local advisory DB path, see
    `QUALITY-AND-SECURITY_cargo_audit.json`);
  - the wheel build and `.venv-native/bin/python -m pytest native/python/tests -q -rs`.
- Hosted-only gap: the GitHub runner fetches the advisory DB over the network. The local run used
  `--no-fetch` with a scratch checkout because the default lock fails on this NFS home.

## Status

- Not applied in this commit. Lead or owner must approve the workflow change and then watch the
  hosted run. This commit does not claim that any hosted native check passed.
