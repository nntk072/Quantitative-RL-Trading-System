# Known limitations and open gates

## Scope note

The user identified the current files as FTMO Demo data and directed local
analysis using only data already in the checkout. The underlying provider and
license terms were not investigated. No raw input is included in this release,
and no redistribution or data-rights claim is made. This is outside the
requested local-analysis scope.

## Release blockers

1. **Data quality and clock:** the complete local inventory hashes all 140
   entries, covering 64 distinct resolved files and 16.33 GB of unique data;
   all 38 selected matched pair data inputs match their observed campaign hashes. The
   current campaign-input audit found
   missing/non-finite required bid/ask values in all four tick files, adjacent
   timestamp ties (328,918 changed-quote pairs, 553 missing-quote pairs, no
   identical-quote pairs), and 23 uncovered training M1 minutes per
   instrument. Per-column missingness is in the detailed tick diagnostic.
   A second full-row pass accounts for all 172,290,383 tick rows: flag 2
   always coincides with ASK missing, flag 4 with BID missing, and flag 6
   with both sides present in these local files. This pattern is not an
   authoritative definition of provider flags or a quote-order guarantee.
   The configured timeframe audit now compares 30 native symbol/timeframe
   series across training and exposed-report periods: 532,350 and 423,018 bar
   rows, respectively, have exact timestamps and OHLCV parity with M1
   resampling. US100 D1 is an M1-derived view in each period. Native spread
   differs from both the M1 mean and last-value references (171,819 and 87,638
   training rows; 98,918 and 48,782 exposed-report rows). Spread semantics are
   unresolved. The first-M1-after-close audit records 15 terminal higher-timeframe
   rows per period without a later M1 row; delayed rows are not classified
   against an authoritative calendar. Timestamp DST interpretation, within-tie
   ordering, and within-minute quote availability remain open. See
   [`configured_timeframe_parity.json`](configured_timeframe_parity.json) and
   [its research interpretation](../../../../docs/research/multitimeframe_data_alignment.md).
   The candidate conditional replay adds 54,638 proposals and 1,067,731
   bracket combinations; 769,187 rows (72.0%) remain unresolved. Monthly
   unresolved shares are 84.8%–94.2% through 2025-08 and 15.9% in December.
   Incomplete local quote intervals dominate unresolved rows in every month.
   The 12-row deterministic replay audit uses the same execution function and
   is a reproducibility sample, not an independent implementation or a full
   outcome recalculation. These labels are not suitable for an unbiased
   candidate-value comparison; see the
   [candidate outcome packet](../../candidate_outcomes/README.md).
2. **Real-data causality:** the current v39 report resolves 130 configurations
   into 19 feature-builder groups and passes 57/57 prefix comparisons across
   three cutoffs with zero maximum absolute delta. The strict merge records 78
   current source hashes and four local input hashes. This establishes prefix
   invariance only for the recorded inventory, source snapshot, and cutoffs. It
   does not prove every
   execution, label, or model-selection path, upstream source-event time,
   publication latency, or authoritative session/calendar semantics.
   Candidate-event timing and exhaustive feature-family review remain
   incomplete.
3. **Execution reconciliation:** focused current-source tests pass, but full
   real-feed trace reconciliation across all order, partial-exit, breach,
   session-close, and checkpoint cases is not complete. The selected matched pair
   campaign used historical gross realized-loss counter semantics; this is not
   net daily-equity/FTMO semantics. The March events are therefore code-gate
   failures, not verified FTMO daily-loss breaches. A4B separately breached
   the configured maximum account loss. Both simulators now reset either
   policy mode on the normalized source-date `session_id`, covered by a
   controlled cross-midnight test. Equivalence to 00:00 CE(S)T remains
   unverified.
4. **Comparative selection:** the verified three-arm packet covers 351,432
   bars and 99,492 decisions in each arm. The flat control has zero
   entries/fills, return, and breaches. The one-seed random-eligible reference
   completed 1,854 positions, returned -10.16%, and recorded 25 breach events.
   The fixed structure-priority rule completed 1,169 positions, returned
   -10.03%, and recorded 25 breach events. A bundle
   writer defect that had copied the random arm's intervals into the flat arm
   is fixed and regression-tested; two affected immutable bundles remain
   marked superseded. The corrected result is negative accounting/sanity
   evidence, not a policy ranking. Matched economic results for other simple
   rules, supervised and RL baselines, independent seeds, and uncertainty remain
   incomplete. There is no untouched confirmation period.
5. **Release verification:** the `verification` section in
   [`RELEASE_MANIFEST.json`](RELEASE_MANIFEST.json) is authoritative for the
   latest full-tree Ruff and Mypy results, scoped test totals, strict Sphinx
   output manifest, documentation inventory, and release hashes. Those
   results apply only to the source and inputs recorded for that gate; they do
   not resolve the scientific blockers above. Full GitHub CI and final thesis
   figure/table regeneration remain open.
6. **Inventory completeness:** the attempt ledger covers the headline selected
   pair, the 100k screen, and the distinct 20M attempt, not all 49 indexed run
   manifests. The refreshed function map inventories 3,567 definitions across
   613 source files and 965 direct static test references (421/1,355 P0).
   It records imports
   and attribute paths; it is not a call graph or executed-test map, and a
  missing reference does not prove code is unused or untested. The selected P6
  campaign's source snapshot, both run manifests/configs, and both checkpoint
  byte hashes now verify against their recorded identities. Its run-level dirty
  source-tree hash is unknown, and the recorded feature cache is unavailable
  at its manifest path; no model replay is claimed. See the
  [bounded artifact integrity report](selected_campaign_artifact_integrity.json).

## Research interpretation limits

- The selected pair result is one seed, on a development interval; its exposed 2026
  replay cannot become a fresh holdout.
- A4A's aggregate ledger endpoint was above the 2025 hard floor, but its
  per-episode risk-survival gate failed early; the aggregate endpoint is not a
  survival pass.
- The monthly attribution is descriptive accounting over saved cohorts and does
  not prove that entry or exit rules caused the changes.
- The selected policy's class-conditioned action head is not an explicit
  price-conditioned expected-outcome model.
- The historical train logs show most entry requests occurred while the entry
  state machine was unarmed. This is action-funnel attrition, not a causal
  account of the losses; candidate-to-order-to-fill and exit attribution remain
  incomplete. See the [train-only funnel diagnosis](entry_action_funnel_diagnosis/entry_action_funnel_diagnosis.md).
- No real brokerage fill, market impact, or live profitability conclusion is
  supported.
- The separate 20M scratch attempt has a distinct identity and is not evidence
  for the selected pair.

## Remaining source-specific evidence

Use only the current local data as directed; do not add an external export.
Provider/license investigation and external calendar authority remain outside
scope. The selected-pair inputs are hash-checked, but its exact frozen
checkpoint could not be matched in the targeted archive, so an independent
checkpoint replay is unavailable. Do not promote the historical result to an
R3 claim or describe the exposed 2026 interval as confirmation.
