# Research release readiness snapshot

**Disposition: BLOCKED.** This is a provenance-backed readiness snapshot and
honest negative research package, not a ready-to-publish thesis or software
release. The evidence supports a failed selected matched policy pair and several tested
software contracts. It does not establish a viable trading policy, fresh
out-of-sample performance, or full reproducibility. It contains no raw market
data and makes no data-rights or redistribution claim.

## Start here

- [Final readiness report](FINAL_READINESS_REPORT.md) gives the gate-by-gate
  disposition and the exact remaining blockers.
- [Evidence-bounded thesis report](../../../../docs/thesis/research_evidence_report.md)
  provides the current manuscript-style synthesis. It is a draft with open
  scientific gates, not a final thesis verdict.
- [Consolidated results](CONSOLIDATED_RESEARCH_RESULTS.md) states the bounded
  empirical conclusion and separates training from exposed report-period data.
- [Legacy risk-gate trace](legacy_daily_loss_counter_breach_trace.md) documents
  the historical legacy daily-loss counter and reconciles the March events to
  the close ledgers.
- [Data provenance and access](DATA_PROVENANCE_AND_ACCESS.md) records what was
  found in the checkout and scratch campaign, and what remains unverified.
- [Local market data quality profile](local_market_data_quality.json) uses
  schema v2 and records all 39 campaign inputs (34 bar files, four tick files,
  and one configured calendar); every input is present and hash-matched. It
  stores per-file and combined day/week/month counts using parsed source-wall
  time, with no timezone or session-calendar interpretation. The reusable
  scanner lives at
  `scripts/research/analysis/market_data/scan_local_market_data_quality.py`.
  The [monthly tick quote-side table](local_monthly_tick_quote_quality.csv)
  and [figure](local_monthly_tick_quote_quality.png) summarize rows missing
  either required side by source-wall month, with denominators and profile
  hash recorded in the companion provenance JSON.
  Superseded preliminary snapshots and historical scan source copies are
  checksum-indexed in the external research archive; the corrected legacy
  byte-audit source snapshot was not recovered, which limits exact regeneration
  of that historical scan only.
- The complete local byte inventory is sourced from the semantic external file
  `local_market_data_inventory.json`; the manifest stores its exact path and
  content hash. The reusable inventory hasher lives with market-data analyses.
- [Detailed tick diagnostic](current_market_input_diagnostic.json)
  breaks bid/ask missingness down by column and classifies each adjacent
  timestamp tie by whether quotes changed or were missing.
- [Configured timeframe parity](configured_timeframe_parity.json) compares all
  configured native M3–D1 bars with M1 resampling across both local periods.
  Timestamps and OHLCV agree on every native row; native spread differs from
  both the M1 mean and last-value references, and the configured schedule is
  not asserted as authoritative.
- [Real-market feature prefix invariance](../../feature_causality/real_market_feature_prefix_invariance_all_profiles.json)
  is the current all-profile report: 130 configurations resolved to 19
  feature-builder groups, 57/57 comparisons passed across three cutoffs, and
  the current runner, inventory, feature-source, and local-input hashes are
  recorded. The selected-profile report at
  [its historical path](real_market_feature_prefix_invariance.json) remains
  for comparison only.
- [Tick flag/quote-side cross-tab](tick_quote_side_flag_cross_tab.json)
  accounts for every tick row and records the observed local relationship
  between flags 2/4/6 and missing bid/ask sides. This does not establish
  authoritative provider flag semantics.
- [Full local-data checksum manifest](RAW_DATA_SHA256_MANIFEST.json) hashes
  all 140 inventoried paths, records 64 distinct resolved files, and confirms
  all 38 campaign data inputs against their observed hashes. Superseded
  preliminary exports are outside the repository archive.
- [Model and baseline catalog](MODEL_AND_BASELINE_CATALOG.md) describes what
  the tested policy can and cannot establish.
- [Training-only setup opportunity census](../../trade_setup_opportunity_census/README.md)
  records monthly/regime eligibility and horizon coverage for all 108 setup
  categories under the registered feature overlay. Only 24 are enabled there;
  the counts are not executable-trade evidence.
- [Manifest](RELEASE_MANIFEST.json) pins source and evidence identities.
- [Selected-pair result identity](selected_pair_viability_manifest.json) binds
  both historical seed-50 arms to their recorded run manifests, configs,
  claim boundaries, and exact artifact hashes. The v2 record remains draft
  because several historical identity fields are unavailable; each is marked
  unknown with a reason.
- [Experiment provenance DAG](EXPERIMENT_PROVENANCE_DAG.json) links all
  discovered campaign/experiment manifests to their declared source, input,
  job, and artifact identities. Large data and checkpoint payloads are not
  rehashed by this export.
- [Reproducibility matrix](RESULTS_REPRODUCIBILITY_MATRIX.csv) records the
  current evidence grades and limits.
- [Function and test evidence index](FUNCTION_TEST_EVIDENCE_INDEX.csv) gives
  the reviewed test references, recorded outcomes, and scope limits. Its last
  column preserves evidence and limitations as one valid CSV field.
- [Attempt ledger](EXPERIMENT_AND_ATTEMPT_LEDGER.jsonl) covers the headline
  selected pair and the two explicitly distinguished screens; it is not a
  complete export of all indexed runs.
- [Known limitations](KNOWN_LIMITATIONS.md) records release-blocking gaps.

The [entry-action funnel diagnosis](entry_action_funnel_diagnosis/entry_action_funnel_diagnosis.md)
records where the historical policy pair's training entry requests were
rejected. It identifies action-state attrition, not the cause of economic
losses or a reason to resume training.

The [multi-timeframe alignment interpretation](../../../../docs/research/multitimeframe_data_alignment.md)
explains the parity report's denominators, spread comparison, availability
counts, and calendar limitations.

The source tree and tracked evidence remain canonical. The selected matched
pair's scratch campaign is external to Git; its recovered hashes and paths are summarized in
the operational research plan. No private market data or checkpoints are
copied into this release directory. The current strict Sphinx output is
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/run-21376798/rendered-docs-html-final-clean`.
Its 2,654-file SHA-256 manifest is at the matching `.manifest.json` path;
the manifest SHA-256 is
`6b8cb348b9289ef300f3bcee7b80f6c0d039f4525148cb4736c729793f510f58`.
