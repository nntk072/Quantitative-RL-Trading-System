# Research evidence sufficiency audit

This generated audit checks files required for the stated claim scope. It does not upgrade a result beyond the available inputs.

## Exit-action exact-common-entry cohort (R2 claim scope)

**Tracked identity and provenance: complete** (3/3 tracked assets present)
- evidence/research/exit_action_semantics/evidence_manifest.json — present
- evidence/research/exit_action_semantics/run_identity.json — present
- evidence/research/exit_action_semantics/evaluation_configuration.yaml — present

**Recomputable cohort summary: complete** (2/2 tracked assets present)
- evidence/research/exit_action_semantics/common_entry_cohort.csv — present
- evidence/research/exit_action_semantics/common_entry_cohort_summary.json — present

**Fixed-entry shadow exports: complete** (3/3 tracked assets present)
- evidence/research/exit_action_semantics/fixed_entry_shadow_trades.csv — present
- evidence/research/exit_action_semantics/fixed_entry_shadow_events.jsonl — present
- evidence/research/exit_action_semantics/fixed_entry_shadow_provenance.json — present

**Interpretation and comparison records: complete** (5/5 tracked assets present)
- evidence/research/exit_action_semantics/README.md — present
- evidence/research/exit_action_semantics/decoder_behavior_comparison.md — present
- evidence/research/exit_action_semantics/fixed_entry_shadow_findings.md — present
- evidence/research/exit_action_semantics/decision_gates.json — present
- evidence/research/exit_action_semantics/counterfactual_decoder_patch.diff — present

**Complete closed-loop replay inputs: missing** (0/3 tracked assets present)
- full per-arm v2 trade ledger — missing
- full per-arm v3 trade ledger — missing
- original raw tick data — missing

## Monthly entry and exit attribution (R2 aggregate claim scope)

**Tracked semantic packet, reproduction source, paired trade inputs and figure: complete** (6/6 tracked assets present)
- evidence/research/entry_and_exit_attribution/evidence_manifest.json — present
- evidence/research/entry_and_exit_attribution/monthly_entry_exit_summary.json — present
- evidence/research/entry_and_exit_attribution/treatment_paired_trades.csv — present
- evidence/research/entry_and_exit_attribution/control_paired_trades.csv — present
- evidence/research/entry_and_exit_attribution/monthly_entry_exit_attribution.png — present
- docs/reproduce/entry_and_exit_attribution.ipynb — present

**Replay inputs absent from the tracked packet: missing** (0/3 tracked assets present)
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
- evidence/research/setup_conditioned_reasoning_replay/policy_variant_comparison/arm_c/testing/policy_metrics.json — present
- evidence/research/setup_conditioned_reasoning_replay/policy_variant_comparison/arm_d/testing/policy_metrics.json — present
- evidence/research/setup_conditioned_reasoning_replay/policy_variant_comparison/arm_c/testing/equity.png — present
- evidence/research/setup_conditioned_reasoning_replay/policy_variant_comparison/arm_d/testing/equity.png — present

**Independent figure regeneration (R2): missing** (0/4 tracked assets present)
- C per-arm equity ledger — missing
- D per-arm equity ledger — missing
- C trade ledger — missing
- D trade ledger — missing

## Model observation and action semantics (source/configuration scope)

**Tracked source, configuration, and evidence: complete** (11/11 tracked assets present)
- evidence/research/model_observation_and_action_semantics/README.md — present
- evidence/research/model_observation_and_action_semantics/run_artifact_shape_inventory.json — present
- scripts/research/analysis/models/inspect_observation_action_artifacts.py — present
- docs/research/model_observation_and_action_semantics.md — present
- decisioning/trade_setup.py — present
- simulation/environment/observation_runtime.py — present
- models/encoders/mtf_reasoning.py — present
- learning/rl/hybrid.py — present
- config/research/trade_setup_mtf_reasoning_2m.yaml — present
- config/research/trade_setup_mtf_reasoning_conditioned_2m.yaml — present
- evidence/research/trade_setup_opportunity_census/census.json — present

**Run-specific or scientific claims not established by this packet: missing** (0/4 tracked assets present)
- run-resolved tensor shapes for every compared configuration and checkpoint — missing
- per-decision selected-setup and proposed-price geometry traces — missing
- authoritative candidate event timestamps and publication delays — missing
- candidate-level fill, return, and calibrated outcome evidence — missing

## Real-market feature prefix invariance (resolved profile inventory)

**Tracked analysis and result: complete** (7/7 tracked assets present)
- scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py — present
- scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py — present
- tests/research/test_feature_prefix_invariance.py — present
- tests/research/test_real_market_feature_prefix_shards.py — present
- evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json — present
- docs/research/feature_causality_and_availability.md — present
- evidence/research/feature_causality/feature_causality_matrix.csv — present

**Claims deliberately left open: missing** (0/4 tracked assets present)
- authoritative source-event publication timestamps — missing
- authoritative session-calendar validation — missing
- configurations outside the resolved 130-profile inventory — missing
- logical event cardinality and historical candidate-to-action linkage — missing

## Fill quote source alignment (selected local fills)

**Tracked analysis and result: complete** (5/5 tracked assets present)
- scripts/research/analysis/market_data/analyze_fill_quote_source_alignment.py — present
- tests/research/test_fill_quote_source_alignment.py — present
- evidence/research/fill_quote_source_alignment/README.md — present
- evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json — present
- docs/research/fill_quote_availability.md — present

**Claims deliberately left open: missing** (0/3 tracked assets present)
- authoritative provider clock and daylight-saving history — missing
- authoritative market session calendar — missing
- within-timestamp quote chronology or broker order-arrival quote — missing

## Interpretation

The real-market prefix packet resolves 130 registered configurations into 19 feature-builder groups and passes all 57 comparisons across three cutoffs; it is limited to that inventory and local history. Logical event cardinality, authoritative publication timestamps and calendar semantics, and historical candidate-to-action linkage remain open. The exit-action notebook makes an R2 claim only for the tracked cohort CSV and summary. The monthly entry and exit attribution notebook recomputes paired-trade aggregates, seeded bootstrap intervals, a decomposition, and the versioned figure; raw ticks and checkpoints are absent from this tracked packet. This audit does not inventory ignored local scratch assets or independently validate their availability. The entry-idea notebook recomputes family-level totals from tracked aggregate exports, but timestamp-level feature rows are absent. The setup-conditioned package supports an R1 evidence view; its missing ledgers prevent full plot regeneration.
