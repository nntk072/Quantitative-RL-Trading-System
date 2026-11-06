# Feature causality and availability inventory

This packet is the generated inventory for the Stage D causal feature audit.
It lists public top-level functions under `features/` and every setup-entry
idea flag in the local opportunity census. It is an audit worklist, not a
claim that each function's timing semantics have been verified.

The current matrix has 96 unique public feature-function candidates, 11
upstream time/session transformation candidates, and 108 setup flags. All 107
function candidates now have explicit source-contract metadata; some entries
also record missing dedicated fixtures or inherited clock limits rather than
claiming complete acceptance. The registered opportunity census supports 24
flags under its selected overlay; 84 are disabled by that configuration.
Source semantics are reviewed for all 108 families, but disabled flags have
no active candidate rows or measured identity counts in this census.
The local training census contains 488,008 active candidate rows; all resolve
to 109,391 candidate-scoped source-time IDs, with no missing source times in
this selected profile. It also records 115,863 identified identity-episode
starts, 13,758 adjacent active identity changes, and 5,719 IDs reused across
separate active-mask intervals. Those are descriptive tuple/mask transitions,
not logical event cardinality. Per-flag counts and identity summaries are
generated from the [opportunity census](../trade_setup_opportunity_census/README.md).

The 107 source-contract entries cover the technical-indicator family, session
and activity helpers, entry-idea projections, SMT, liquidity, structure and
swings, PD context, PO3/IFVG/FVG, feature assembly, cache/fold/view boundaries,
and upstream timeframe/session transforms. A reviewed row describes what its
source and cited fixtures establish; it does not imply that every family has
an isolated prefix/property test or external clock authority. For all 108
candidate flags, the matrix identifies M1 output-row availability. The 24
candidates enabled by the registered overlay have source semantics reviewed
against their producers and fixtures: close-based confirmed-swing retracement
eligibility, post-IFVG PO3 state, later IFVG retest confirmation, and IFVG
close-through confirmation. A separate versioned resolver composes source
time metadata into deterministic IDs when required timestamps resolve. The
entry-idea projection fixture covers all 18 selected standard-deviation
timeframe/direction flags and the six selected M1 PO3/IFVG family/direction
flags. An MTF identity fixture also checks exact source-close visibility and
truncated-prefix agreement for all eight non-M1 standard-deviation windows.
These synthetic contracts do not establish external feed publication latency
or calendar authority. The
environment records the selected candidate ID, source-event ID/status, and
resolved source times in nanoseconds under the matching `decision_id`, without
adding them to model inputs or changing binary flags. M1 PO3 identities use the
selected aligned IFVG-zone origin; MTF PO3 identities use the source-timeframe
PO3-state origin. Synthetic trace tests and the selected training census pass;
this does not retroactively add those fields to historical campaign traces.
Provider publication time, event cardinality, and configurations outside this
census remain open.

### Resolved configuration-profile inventory

The reusable static resolver
(`scripts/research/analysis/features/build_feature_configuration_inventory.py`)
now inventories 130 feature profiles from the canonical default, six feature
overlays, three legacy strategy overlays, eight research overlays, 69 saved
experiment-run specs, and 43 variants resolved through the legacy variant
resolver. These reduce to 18 exact resolved feature-tree fingerprints. The
inventory includes source paths and SHA-256 hashes in both JSON and CSV. It
does not build features or inspect market rows, so it identifies configuration
coverage but does not close causality, event-cardinality, availability, or feed
timing gates.

The existing reusable assembled-prefix audit
(`scripts/research/analysis/features/verify_feature_profile_prefix_invariance.py`)
compares 17 distinct feature trees in its recorded inventory snapshot on a 3,600-row synthetic
two-symbol M1 input, using each profile's declared session timezone. All 17
full-build outputs match their separately truncated 2,400-row builds. The
machine-readable result is
[`feature_profile_prefix_invariance.json`](feature_profile_prefix_invariance.json);
it records the inventory fingerprint, 68 generated-source hashes, five
configuration-resolver hashes, synthetic input parameters, and per-profile
comparisons. Slurm job 21362641 completed with exit 0 on csl10 (4 CPUs, 32 GB
requested, 1:59 elapsed); its focused validation batch passed 179 tests and
Mypy passed. Both this run and the preceding fixture-correction run
(21362583, csl4, 0:59, exit 1) were shorter than the Triton 120-second
minimum-step rule. The initial run found a mismatch because its synthetic
timestamps used one timezone for profiles declaring another; the fixture was
corrected to use each profile's configured timezone, session labels, and
session IDs. This is recorded as a launch-control deviation in the external
agent plan ledger, and the check was not rerun. The successful synthetic
comparison is supplemental to the selected real-market prefix evidence. It
does not establish real-market availability, feed publication timing, event
cardinality, external schedule authority, or economic value, and it does not
close Stage D.

One experiment-run spec declares `features.ema_periods` as a list. The override
path now accepts validated flat primitive lists, serializes them as JSON, and
parses them through the same configuration schema as other overrides. The
inventory resolves this run spec through the production normalizer. This fixes
config transport only; no historical run was relaunched. The 43 files under
`config/variants/` are risk-policy settings rather than feature overlays; the
three `config/data_modes/` files are validated data-only profiles and contribute
no feature settings. Current machine-readable results are
[`feature_configuration_inventory.json`](feature_configuration_inventory.json)
and [`feature_configuration_inventory.csv`](feature_configuration_inventory.csv).

The real-data identity count shows source-time resolution only; it does not
prove one ID per logical setup or trade. For all 84 disabled flags, source
review describes the producer lifecycle but does not claim candidate
availability or identity measurement in this selected overlay. The audit
records known identity limits: same-side FVG/IFVG events can collapse in
scalar outputs or latest-zone state; an order-block producer keeps one active
zone per direction; and PO3 IDs remain source-time tuples that can recur across
separate state episodes. Missing or nonpositive sources collapse to an inactive
flag. Test paths not
attached to a reviewed contract are static name matches and are not counted as
coverage.

The selected profile disables FVG-retetest candidates. The FVG producer can
aggregate multiple same-side zones into one scalar retest timestamp, so a
future FVG identity census must represent multiple events and ambiguity
explicitly before using those timestamps as candidate outcome labels.
Synthetic overlap fixtures now show that the zone collection preserves two
adjacent overlapping FVG records, while the model-facing scalar retest selects
the newest zone origin when both confirm on the same row; its emitted prefix
matches a separately truncated build. This characterizes the projection rule
without claiming that the scalar feature retains both logical event IDs.

At runtime, `trade_setup_mask` is built from the current `step_idx` feature
row; the action transition consumes that row and fills at the next index. The
M1 sequence window excludes the current row even though the candidate mask may
reflect it. The local decision contract is tested for open-stamped M1 rows:
current-row candidate eligibility is read at the completed-row decision
boundary, and a market order targets the next bar's open. This establishes
simulator timing, not provider publication latency. No definite future leak
was established.

The [current-source all-profile real-market report](real_market_feature_prefix_invariance_current_source/README.md)
records the v40 IFVG missing-ATR cache identity. The strict merge resolved all
130 profiles and verified 78 source hashes plus four local input hashes. All
19 feature-builder groups pass 57/57 cutoffs with zero changed values and zero
maximum absolute delta across 21,741,766,365 compared values. This supersedes
the [v39 snapshot report](real_market_feature_prefix_invariance_v39.json) for
current-source prefix evidence; the source reconciliation documents prior
snapshots and limits.
The v40 IFVG/PO3 subset packet
(`ifvg_profile_prefix_current_source/`) checks five selected feature groups
at all three registered cutoffs: 15/15 comparisons pass with zero changed
features and zero maximum absolute delta. This is current-source evidence for
those groups only; the full-inventory packet above now supersedes that subset.
Even when current-source prefix checks pass, they do not establish every
execution, label, or model-selection path, logical-event cardinality, or
historical candidate-to-action linkage.
The [source reconciliation](prefix_source_reconciliation.md) retains earlier
source-hash differences as historical notes and records the final v40 run whose
source, inventory, and local-input hashes match current bytes.

The standalone [synthetic HTF availability example](causal_feature_availability_example.png)
shows the source-bar interval and compares a deliberately leaked open-time
projection with the repository's configured close-time alignment. It is a
code-semantic illustration, not market-data evidence.

The [synthetic event-timing examples](synthetic_event_timing_examples/README.md)
show source-ordered PO3/IFVG confirmation and next-bar fill using explicit UTC
fixture timestamps, alongside an incorrect same-bar fill. They also show the
previous-session premium gate and optional retest path, swing confirmation
after the right-side bars, order-block overlap followed by a later confirmed
retest, and forward-fill behavior when an SMT secondary bar is missing. All
values and times are synthetic; these examples make no external calendar,
feed-clock, historical-market, or economic claim.

The [timeframe mask audit](timeframe_mask_semantics/README.md) verifies
left-padding, empty closed windows, valid all-zero candle rows, and payload
exclusion for the active reasoning MTF encoders. The audit also adds the
versioned `mtf_empty_stream_masked_v1` encoder for empty-stream masking while
preserving legacy `mtf` checkpoint semantics. Per-feature warmup validity and
the broader active-feature mask gate remain open.

The [timeframe validity and padding semantics packet](timeframe_validity_padding_semantics/README.md)
checks M1 and all eight HTF sequence tensors, temporal and per-feature validity
channels, left-padding, empty streams, and registered encoder compatibility.
It confirms finite-value validity semantics and temporal padding behavior. It
does not establish producer-level warmup validity where upstream feature code
already emits finite zero; that source classification remains open.

The current-source [profile-wide observation validity audit](observation_validity_across_profiles/README.md)
measures 130 configurations in 23 groups across 15,571 feature/profile rows.
The [producer semantics crosswalk](observation_validity_semantics/README.md)
maps all 1,291 feature/timeframe pairs to 41 source-reviewed producer
contracts. It records 620 pairs with no missing rows, 463 with leading-only
missingness, 206 with interior missingness, and two unavailable throughout the
measured profiles; 219 pairs contain both nonfinite values and finite zeros.
These are observation-boundary measurements and reviewed limitations, not
evidence that a policy consumes validity signals or that those features have
economic value. VAE validity remains a separate gate.

The current 130-profile observation-validity packet covers 23 observation
groups and 15,571 feature rows, with zero failed groups and verified packet
checksums. Its 1,291 feature/timeframe pairs include 206 with interior missing
values, 463 with leading-only missingness, 620 with no missing values, and two
unavailable in every group; 219 pairs have a missing/finite-zero collision.
`po3_phase` now uses `-1` outside the configured session, which distinguishes
clipped `session_progress` from active session boundaries. Valid zero-range
candles now produce a zero upper-wick ratio. Eight leading nonfinite rows per M1 PO3 feature (one in each affected group) are consistent with train-only rolling normalization requiring two observations for standard deviation. Conditional
event distances and ages still require a full feature-validity contract; this
packet does not close that gate.

## Selected-overlay signal timing review

The registered opportunity-census config supports 24 of the 108 catalog
flags: 18 standard-deviation timeframe/direction combinations, plus M1 PO3,
IFVG-retest, and IFVG-unretested long/short. Source review records their local
event semantics; it does not establish provider publication time or an
authoritative external clock:

| Active group | Source signal and event/state semantics | Source-to-M1 availability | Remaining timing limit |
|---|---|---|---|
| Standard deviation (18) | `build_swing_retracement_features` uses the latest confirmed swing leg and the current source-bar close inside the configured 0.5–0.786 retracement band. Eligibility can persist; the resolver composes retained leg start/end times so the same leg shares an ID across qualifying rows. | M1 uses its source-row close boundary. M3–D1 blocks pass through `align_blocks` using `timeframe_close_times`; they project onto the first M1 feature row at or after the configured source close. | Local code/config timing only; feed publication clock and schedule authority are not established. Decision/fill order is covered separately by the environment event contract. |
| PO3 M1 (2) | `_po3_direction` requires direction-matched `po3_distribution_after_ifvg` and an active same-direction IFVG. Identity includes sweep, reclaim, same-side IFVG confirmation, and the selected aligned IFVG-zone origin. A sweep/manipulation flag alone is not an eligible PO3 entry idea. | M1 source-row close boundary; the flag is a row-wise projection of M1 state. | Activation is established from producer state, not an exchange/feed publication timestamp; tuple recurrence is not logical event cardinality. |
| IFVG retest M1 (2) | `ifvg_retest_bull/bear` is emitted on a later bar after a confirmed zone has been left, retested, and the close clears the reaction threshold. The resolver uses both confirmation and retest times. | M1 source-row close boundary. | Later-bar confirmation is established by code/fixtures; feed publication time remains unknown. |
| IFVG unretested M1 (2) | The candidate projects `ifvg_bull/bear_confirmed`, emitted on the close-through confirmation bar after an earlier passage through the zone. The resolver uses the selected confirmation timestamp; it does not mean the later retest event used by the distinct IFVG-retest signal. | M1 source-row close boundary. | Close-through confirmation is established by code/fixtures; feed publication time remains unknown. |

Source and fixture references: `features/context/entry_ideas.py`,
`features/context/swing_retracement.py`, `features/pipeline/feature_matrix_builder.py`,
`features/pipeline/po3_stage.py`, `features/po3/po3_phase_state.py`, and
`features/po3/ifvg_detection.py`; tests are in
`tests/unit/features/test_entry_ideas.py`, `tests/unit/features/test_po3_state.py`,
and `tests/unit/features/test_po3_ifvg_state.py`. The local open-stamped
decision/fill boundary is tested; source-feed publication time remains outside
the evidence.

## Reproduction

From the repository root, regenerate the matrix and summary:

```bash
.venv-x86/bin/python scripts/research/analysis/features/build_feature_causality_matrix.py
.venv-x86/bin/python scripts/research/analysis/features/plot_feature_availability_example.py
```

Artifacts:

- `feature_causality_matrix.csv` — one row per public-function candidate and
  setup-entry idea flag, with explicit unassessed fields and separate source
  review versus selected-overlay measurement status.
- `feature_causality_matrix.json` — counts, census checksums, identity totals,
  output checksum, and incomplete acceptance status. Remaining items include
  event-cardinality review, disabled candidate configurations, and
  configurations outside selected checks. Local timestamp meaning inherits
  supplied bar/index labels; external provider-clock authority is outside this
  work's scope.

## Current-source active-family regression batch

`active_family_contracts/` records a consolidated run of 14 focused modules
covering swing, order-block, FVG/IFVG, PO3, SMT, candidate projection, MTF
window, prefix, and observation-validity contracts. All 137 tests passed in
24.49 seconds on the existing GH200 allocation. The packet includes test and
production-source hashes. It does not resolve the model-input feature-validity
mask gap or historical proposal-to-action linkage.

## Observation value sanitization

`observation_value_sanitization/` records a small production fix at the model
input boundary. NaN and both infinities now map to zero for M1, MTF, and VAE
feature inputs; the focused observation/schema suite passes 32/32 tests. This
prevents extreme infinity values from reaching encoders. It does not add
per-feature validity masks or resolve zero/missing collisions.

## Active event-family contract tests

The focused [event-family semantics packet](active_event_family_semantics/README.md)
records 157 passing current-source tests across swings, order blocks, FVG/IFVG,
PO3, higher-timeframe close visibility, liquidity sweeps/BOS, and SMT secondary
bars. It verifies the listed synthetic event order, state transitions, and
prefix behavior. It does not measure event prevalence or policy outcomes; the
broader validity-channel and model-input acceptance gate remains open.
