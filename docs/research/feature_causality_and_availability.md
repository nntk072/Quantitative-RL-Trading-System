# Feature causality and availability

The feature pipeline combines M1 observations, configured higher-timeframe
bars, structural context, and candidate-eligibility flags. A function name or
a passing synthetic example does not establish when a value becomes
observable. The evidence matrix records source event time separately from the
time at which the policy may use the value.

The current generated inventory lists 99 public top-level function candidates
under `features/`, 11 upstream time/session transformation candidates, and all
108 setup-entry idea flags. Twenty-four flags are supported by the registered
opportunity-census configuration. The matrix now has explicit source-contract
metadata for all 110 function candidates. These records distinguish reviewed
source behavior from remaining fixture, prefix, configuration, and timing
gaps; metadata presence does not mean every function has a passing direct
test. Selected component fixtures and real-market prefix checks establish
bounded behavior. The exact-source 2026-11-10 audit now covers all 141 runtime
profiles, including the valid research overlays and survival qualification
profile. All 57 registered cutoff comparisons across 19 feature profiles
passed, covering 21,749,324,775 values with zero changed values and zero
maximum absolute delta. The merged report verifies all 78 source hashes, four
local M1 input hashes, and the runtime inventory identity. The corrected
inventory and review are recorded under
`evidence/research/feature_causality/real_market_feature_prefix_invariance_current_source/`;
the earlier incomplete 130-profile run remains preserved there as superseded
evidence. The 2026 interval was used only for report-only prefix auditing, not
candidate selection. Prefix invariance does not establish external feed
publication timing or exhaustive full-pipeline causality. The paired observation-validity audit covers the same 141 runtime profiles in 28 effective observation groups and records 19,350 feature/timeframe rows. Its source-scoped packet is `evidence/research/feature_causality/observation_validity_current_source_141/ARCHIVE.md`; the corresponding `evidence/research/feature_causality/observation_validity_semantics_current_source_141/README.md` keeps observed missingness separate from cause attribution and policy use.

The synthetic assembled-matrix prefix property also passes for its selected
configuration: `tests/unit/features/test_assembled_causality.py::test_assembled_matrix_truncation_causality`
rebuilds a 900-row feature matrix and compares values through a 700-row prefix.
The fixture enables technical indicators, FVG, PO3/IFVG state, and higher-timeframe
premium/discount paths, so the assembled output comparison covers those selected
paths together. It is not a separate adversarial test for every period,
missingness case, or configuration, and does not establish external event timing.
The matrix records M1 output-row availability for all 108 setup flags. For the
24 flags supported by the selected overlay, feature producers now retain the
source times used by a separate event-identity resolver. It emits an ID only
when required times are present and unambiguous. The other 84 flags are
disabled by this configuration. Their producer lifecycles have source-level
reviews, but they have no active candidate rows or measured identity counts in
this census. Scalar FVG/IFVG outputs can collapse overlapping same-side events
and order-block state keeps one zone per direction. PO3 identity now includes
direction-matched IFVG confirmation and selected zone-origin times; M1 reads
the aligned IFVG-zone origin, while MTF reads the source-timeframe PO3-state
origin. A tuple ID may still recur across disconnected state episodes. Full
real-data coverage is measured in the training-only opportunity census: all
488,008 active candidate rows in this selected profile resolve to 109,391
candidate-scoped source-time IDs, with no missing source times. Descriptive
lifecycle counters show 115,863 identity-episode starts, 13,758 adjacent
active identity changes, and 5,719 IDs reused across separate active-mask
intervals. These measure tuple/mask transitions, not logical event
cardinality or one-ID-per-setup semantics. Exact feature-state lifetime, feed
publication latency, and configurations outside this selected profile remain
open.

The declared policy boundary is after the current M1 bar closes. The environment
builds `trade_setup_mask` from that completed `step_idx` feature row, then applies
the action before a next-bar-open fill. The M1 sequence window excludes the
current row while the candidate mask may reflect it. Runtime traces therefore
record the completed-bar decision time separately from the raw bar-open label.
Prefix-invariance and producer reviews address whether feature values depend on
future rows; they do not measure external feed publication latency. The local
bar timestamp convention alone does not establish that latency.

The entry-idea projection creates overlapping binary context flags. A separate
resolver composes retained family timestamps for active candidates without
changing those flags or the 109-way action mask. Confirmed pivots wait for the configured
right-side bars, and accepted swings wait for their reversal threshold before
their values appear. SMT matches confirmed swings by nearby row indices and
backward-fills the secondary stream without a staleness limit; its publication
clock and maximum acceptable secondary age remain open.

A source review of the 24 categories enabled by the registered overlay records
the event/state semantics for standard-deviation, PO3, IFVG-retest, and
IFVG-close-through signals. Environment decisions now carry the selected
source-event ID or unresolved status under their `decision_id`; synthetic
rollout and artifact tests verify that linkage. Local real-data resolution is
measured for the selected profile; event cardinality, untested configurations,
and publication time remain open. The source-backed mapping is in
`evidence/research/feature_causality/README.md`.

Indicator contracts use current/past rolling or recursive state; their exact
warm-up and units are recorded in the matrix. `sweep_velocity` currently
accepts Asian level arguments but only uses London levels. `wick_ratio`
measures the upper wick only; a valid zero-range candle now maps to a finite
zero ratio. PO3 phase uses `-1` outside the configured session, while active
phases are 0/1/2; this sentinel distinguishes clipped `session_progress` from
active boundaries without changing observation shape. The latest completed
feature audit used cache identity `v40-ifvg-missing-atr-distance`. IFVG distance
now preserves its 5.0 sentinel when ATR is unavailable instead of using a
unit-price fallback;
the focused evidence is in
`evidence/research/feature_causality/ifvg_distance_atr_availability/`. The
focused PO3-state test module passes 23 tests. The v40 selected-group prefix
packet at `evidence/research/feature_causality/ifvg_profile_prefix_current_source/`
passes 15/15 cutoffs across five IFVG/PO3 groups, with zero maximum delta. The
final full v40 audit resolves 130 configurations into 19
feature-builder groups and passes all 57 comparisons across three cutoffs,
covering 21,741,766,365 values with zero maximum absolute delta. The fail-closed
merge and independent post-run verification matched 78 feature-source hashes,
the inventory hash, and four local-input hashes to current files. The
[`current-source prefix packet`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/feature_causality/real_market_feature_prefix_invariance_current_source/README.md)
records that run. The percentage-only risk-config migration is included in the
verified snapshot. This establishes prefix invariance for that resolved inventory,
source snapshot, and those cutoffs only. It does not prove source-event time,
publication latency, authoritative session boundaries, logical-event
cardinality, or every execution and label path. The v40 evidence above is a
historical source snapshot. The current code has since advanced through
`v41-pd-distance-availability`, which preserves unknown active-session PD
distances as nonfinite, to `v42-htf-bias-availability`, which adds a finite
availability channel for a neutral versus unavailable HTF bias. Focused
regressions are registered but unrun; the full-profile feature matrix,
missingness report, prefix audit, and release gate must be refreshed before
treating the v41/v42 changes as accepted. The latest full-tree software gate
recorded for the prior snapshot passed 931 scoped release tests with two
existing transformer warnings; full-tree Ruff and Mypy also passed. The final
documentation inventory, evidence audit, and strict Sphinx build are deferred
until evidence packets stabilize.

The reusable analysis and fail-closed shard merger are
`scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py`
and `scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py`.
The current report is in the
[`current-source packet`](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/feature_causality/real_market_feature_prefix_invariance_current_source/README.md);
the v39 snapshot remains in
[`real_market_feature_prefix_invariance_v39.json`](../../evidence/research/feature_causality/real_market_feature_prefix_invariance_v39.json).

See the [generated causality matrix](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/feature_causality),
the [setup opportunity census](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/trade_setup_opportunity_census),
and [multi-timeframe alignment findings](multitimeframe_data_alignment.md).

No data-provider, redistribution-rights, or authoritative calendar claim is
made. The analysis uses current local data only, as directed.
