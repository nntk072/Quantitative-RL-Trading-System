# Research release readiness snapshot

**Disposition: BLOCKED.** This is a provenance-backed readiness snapshot and
honest negative research package, not a ready-to-publish thesis or software
release. The evidence supports a failed selected P6 pair and several tested
software contracts. It does not establish a viable trading policy, fresh
out-of-sample performance, or full reproducibility. It contains no raw market
data and makes no data-rights or redistribution claim.

## Start here

- [Final readiness report](FINAL_READINESS_REPORT.md) gives the gate-by-gate
  disposition and the exact remaining blockers.
- [Consolidated results](CONSOLIDATED_RESEARCH_RESULTS.md) states the bounded
  empirical conclusion and separates training from exposed report-period data.
- [P6 risk-gate trace](P6_RISK_GATE_SEMANTICS_AND_BREACH_TRACE.md) documents
  the historical legacy daily-loss counter and reconciles the March events to
  the close ledgers.
- [Data provenance and access](DATA_PROVENANCE_AND_ACCESS.md) records what was
  found in the checkout and scratch campaign, and what remains unverified.
- [Current P6 input audit](current_source_market_input_audit.json) records the
  39 manifest-matched file hashes and bounded structural checks. Its
  [preliminary version](current_source_market_input_audit_preliminary_20261101.json)
  is retained as superseded evidence because its tick metric treated optional
  blank fields as required.
- [Detailed tick diagnostic](current_source_market_input_diagnostic_20261101.json)
  breaks bid/ask missingness down by column and classifies each adjacent
  timestamp tie by whether quotes changed or were missing.
- [Full local-data checksum manifest](RAW_DATA_SHA256_MANIFEST.json) hashes
  all 140 inventoried paths, records 64 distinct resolved files, and confirms
  all 38 P6 campaign data inputs against their observed hashes. The preliminary
  alias export is retained with a superseded filename.
- [Model and baseline catalog](MODEL_AND_BASELINE_CATALOG.md) describes what
  the tested policy can and cannot establish.
- [Manifest](RELEASE_MANIFEST.json) pins source and evidence identities.
- [Experiment provenance DAG](EXPERIMENT_PROVENANCE_DAG.json) links all
  discovered campaign/experiment manifests to their declared source, input,
  job, and artifact identities. Large data and checkpoint payloads are not
  rehashed by this export.
- [Reproducibility matrix](RESULTS_REPRODUCIBILITY_MATRIX.csv) records the
  current evidence grades and limits.
- [Attempt ledger](EXPERIMENT_AND_ATTEMPT_LEDGER.jsonl) covers the headline
  selected pair and the two explicitly distinguished screens; it is not a
  complete export of all indexed runs.
- [Known limitations](KNOWN_LIMITATIONS.md) records release-blocking gaps.

The source tree and tracked evidence remain canonical. The selected P6 scratch
campaign is external to Git; its recovered hashes and paths are summarized in
the operational research plan. No private market data or checkpoints are
copied into this release directory. The latest rendered docs archive is
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261101_latest`
with a 2,587-file SHA-256 manifest at the matching `.manifest.json` path.
