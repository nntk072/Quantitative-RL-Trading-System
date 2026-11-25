# Verification report (main-native, 2026-11-26)

Checks run, with the exact result. Each line was run; nothing here is inferred.

| Check | Where | Result |
|---|---|---|
| Full unit + architecture suite | 8-CPU allocation 21863642, `pytest tests/unit tests/architecture -n 8` | 4053 passed, 5 skipped, 2 xfailed, exit 0 (logs/agents/architect/2026-11-25_baseline_audit/pytest_unit_final2.log) |
| Architecture tests | login node, `pytest tests/architecture` | 69 passed |
| Study catalog, audits, runner | login node | 28 passed |
| cargo fmt --check, clippy -D warnings, cargo test, release build | native workspace | exit 0; qrl-domain 35 tests pass |
| maturin wheel + Python native tests | native/python | 17 passed (4 smoke, 4 limits parity, 9 position parity) |
| ruff format --check, ruff check | full tree | clean (1452 files), exit 0 |
| mypy full tree | earlier, 1397 files | Success, exit 0 (baseline, before later packages) |
| cargo audit | native/Cargo.lock, local advisory DB | exit 0, 16 crates, no vulnerabilities (crates.io index not refreshed: NFS lock) |
| Mutation check | trading/account/limits.py, trading/risk/sizing.py | 10 mutants, 10 killed |
| Dependency graph | tracked product Python at baseline | 17 packages, 66 edges, 0 cycles |
| Remote main CI, after the Python batch | GitHub, run 0d9304d3 | CI, Documentation website, CodeQL: all success |

Not run: full-tree mypy on the final tree; feature and learning mutation tests; the integration subset; aarch64 wheel; GPU or benchmark runs.
