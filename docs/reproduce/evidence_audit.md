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

## P6 monthly entry/exit decomposition (R2 aggregate claim scope)

**Tracked identity and paired trade inputs: complete** (3/3 tracked assets present)
- evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/p6_monthly_entry_exit_decomposition.json — present
- evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/ladder_a4a_entry_fsm_hidden_qgrid025_paired_trades.csv — present
- evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/ladder_a4b_entry_fsm_qgrid025_paired_trades.csv — present

**Unavailable independent raw replay inputs: missing** (0/3 tracked assets present)
- source run manifests and per-arm environment traces — missing
- original raw tick data and broker fill inputs — missing
- frozen policy checkpoints for both arms — missing

## Entry-idea opportunity counts (R2 aggregate claim scope)

**Tracked aggregate inputs: complete** (3/3 tracked assets present)
- evidence/research/entry_idea_opportunity_counts/annual_summary.csv — present
- evidence/research/entry_idea_opportunity_counts/by_idea_timeframe.csv — present
- evidence/research/entry_idea_opportunity_counts/entry_idea_opportunity_counts.md — present

**Unavailable raw recount inputs: missing** (0/2 tracked assets present)
- timestamp-level source feature rows — missing
- source feature cache and generation manifest — missing

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

The exit-action notebook makes an R2 claim only for the tracked cohort CSV and summary. The P6 notebook recomputes monthly paired-trade aggregates and a seeded bootstrap decomposition, but raw ticks and checkpoints are absent. The entry-idea notebook recomputes family-level totals from tracked aggregate exports, but timestamp-level feature rows are absent. The setup-conditioned package supports an R1 evidence view; its missing ledgers prevent full plot regeneration.
