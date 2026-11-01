# Research evidence sufficiency audit

This generated audit checks files required for the stated claim scope. It does not upgrade a result beyond the available inputs.

## Exit-action exact-common-entry cohort (R2 claim scope)

**Tracked identity: complete** (2/2 tracked assets present)
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/provenance.json — present
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/config.yaml — present

**Recomputable cohort summary: complete** (2/2 tracked assets present)
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/phase2_common_entry_cohort.csv — present
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/phase2_cohort_summary.json — present

**Fixed-entry shadow exports: complete** (2/2 tracked assets present)
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/fixed_entry_shadow/paired_trades.csv — present
- evidence/research/archive_2026/evidence/exit_action_semantics_20261024/fixed_entry_shadow/shadow_events.jsonl — present

**Complete closed-loop replay inputs: missing** (0/3 tracked assets present)
- full per-arm v2 trade ledger — missing
- full per-arm v3 trade ledger — missing
- original raw tick data — missing

## Setup-conditioned replay (R1 evidence view)

**Tracked evidence: complete** (5/5 tracked assets present)
- evidence/research/setup_conditioned_reasoning_replay/README.md — present
- evidence/research/setup_conditioned_reasoning_replay/benchmark_output_20261028/C/testing/thesis_policy_metrics.json — present
- evidence/research/setup_conditioned_reasoning_replay/benchmark_output_20261028/D/testing/thesis_policy_metrics.json — present
- evidence/research/setup_conditioned_reasoning_replay/benchmark_output_20261028/C/testing/equity.png — present
- evidence/research/setup_conditioned_reasoning_replay/benchmark_output_20261028/D/testing/equity.png — present

**Independent figure regeneration (R2): missing** (0/4 tracked assets present)
- C per-arm equity ledger — missing
- D per-arm equity ledger — missing
- C trade ledger — missing
- D trade ledger — missing

## Interpretation

The exit-action notebook makes an R2 claim only for the tracked cohort CSV and summary. The fixed-entry shadow exports exist, but the full per-arm ledgers and raw ticks are missing. The setup-conditioned package supports an R1 evidence view; its missing ledgers prevent full plot regeneration.
