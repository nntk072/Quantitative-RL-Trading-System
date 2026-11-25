# Native modernization plan: working notes

This folder holds the plan and its tracking for the parallel branch.

- Branch: `main-native`, a worktree at `/scratch/work/nguyenl37/worktrees/main-native`, parallel to `perf/env-step-speedup`.
- Baseline: `6755417ee789fd82aa2c536d71dce2e3ff07c481` (merge of PR #17, which is GitHub `main`).
- Plan: [ARCHITECTURE_MODERNIZATION_PLAN.md](ARCHITECTURE_MODERNIZATION_PLAN.md).
- Work-package ledger: [work_package_ledger.json](work_package_ledger.json). Statuses: pending, active, blocked,
  accepted, rejected_with_evidence, not_applicable_with_evidence. Only executed tests and evidence may move a
  package to accepted.
- BASELINE-AUDIT inventory: [baseline_audit/baseline_inventory.json](baseline_audit/baseline_inventory.json),
  generated from `git ls-files` at the baseline.

## Status

- BASELINE-AUDIT: active. Done: tracked-file inventory, oversized-module list, anchor-path check.
  Not done: dependency graph, defect catalog with reproducers, baseline test and check run.
- Other 34 work packages: pending.
- These files are not committed on `main-native`. Commit only when authorized.
- `cargo` is not installed on this host, so no `native/` crate exists yet (NATIVE-TOOLCHAIN is pending).
