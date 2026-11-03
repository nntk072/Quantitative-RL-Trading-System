# Feature causality and availability

The feature pipeline combines M1 observations, configured higher-timeframe
bars, structural context, and candidate-eligibility flags. A function name or
a passing synthetic example does not establish when a value becomes
observable. The evidence matrix records source event time separately from the
time at which the policy may use the value.

The current generated inventory lists 95 public top-level function candidates
under `features/`, 11 upstream time/session transformation candidates, and all
108 setup-entry idea flags. Twenty-four flags are supported by the registered
opportunity-census configuration. The matrix now has explicit source-contract
metadata for all 106 function candidates. These records distinguish reviewed
source behavior from remaining fixture, prefix, configuration, and timing
gaps; metadata presence does not mean every function has a passing direct
test. Selected component fixtures and real-market prefix checks establish
bounded behavior, while external feed-publication timing and exhaustive
full-pipeline coverage remain unverified. This evidence uses current local
data only.

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

The environment builds `trade_setup_mask` from the current `step_idx` feature
row, and the transition applies the action using that same row before the
next-index fill. The M1 sequence window excludes the current row while the
candidate mask may reflect it. This is safe only if the current bar's source
values are available before the policy decision; the local timestamp
convention does not establish that boundary, and no all-family test proves it.
The audit found no definite future-leak defect, but current-row eligibility is
not promoted as causal evidence.

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
accepts Asian level arguments but only uses London levels, and `wick_ratio`
measures the upper wick only. Those semantic/API naming questions are recorded
without changing feature columns that existing checkpoints may consume.

The current-source real-market prefix audit resolves 130 configurations into
19 feature-builder groups and passes all 57 comparisons across three cutoffs.
The current runner and profile inventory hashes match; 78 feature-source and
four local-input hashes are recorded. This establishes prefix invariance for
that resolved inventory and those cutoffs only. It does not prove source-event
time, publication latency, authoritative session boundaries, logical-event
cardinality, or every execution and label path. The latest full-tree software
gate passed 931 scoped release tests with two existing transformer warnings;
full-tree Ruff and Mypy also passed. The final documentation inventory,
evidence audit, and strict Sphinx build are deferred until evidence packets
stabilize.

The reusable analysis and fail-closed shard merger are
`scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py`
and `scripts/research/analysis/features/merge_real_market_feature_prefix_shards.py`.
The current report is
[`real_market_feature_prefix_invariance_all_profiles.json`](../../evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json).

See the [generated causality matrix](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/feature_causality),
the [setup opportunity census](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/trade_setup_opportunity_census),
and [multi-timeframe alignment findings](multitimeframe_data_alignment.md).

No data-provider, redistribution-rights, or authoritative calendar claim is
made. The analysis uses current local data only, as directed.
