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
resolver. These reduce to 17 exact resolved feature-tree fingerprints. The
inventory includes source paths and SHA-256 hashes in both JSON and CSV. It
does not build features or inspect market rows, so it identifies configuration
coverage but does not close causality, event-cardinality, availability, or feed
timing gates.

The reusable assembled-prefix audit
(`scripts/research/analysis/features/verify_feature_profile_prefix_invariance.py`)
compares each of those 17 distinct feature trees on a 3,600-row synthetic
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

The current-source all-profile real-market report completed in existing
allocation 21376798. It resolves 130 configurations into 19 feature-builder
groups and passes 57/57 comparisons across three cutoffs. The strict merger
verified complete group and cutoff coverage; the runner and profile-inventory
hashes match current files, and the report records 78 source-file and four
local-input hashes. The latest full-tree software gate passed 931 scoped
release tests with two existing transformer warnings; full-tree Ruff and Mypy
also passed. The documentation inventory, evidence audit, and strict Sphinx
build remain for the final release pass. Prefix invariance does not establish
event cardinality, publication timing, calendar authority, or untested
configurations. No provider, license, or external timestamp-authority claim
is made here.

The [all-profile real-market report](real_market_feature_prefix_invariance_all_profiles.json)
is the current source-linked result. Prefix invariance does not establish
every execution, label, or model-selection path, logical-event cardinality,
or historical candidate-to-action linkage.

The standalone [synthetic HTF availability example](causal_feature_availability_example.png)
shows the source-bar interval and compares a deliberately leaked open-time
projection with the repository's configured close-time alignment. It is a
code-semantic illustration, not market-data evidence.

The [synthetic event-timing examples](synthetic_event_timing_examples/README.md)
show source-ordered PO3/IFVG confirmation and next-bar fill using explicit UTC
fixture timestamps, alongside an incorrect same-bar fill. They also show the
previous-session premium gate and optional retest path. All values and times
are synthetic; the examples make no external calendar or feed-clock claim.

The [timeframe mask audit](timeframe_mask_semantics/README.md) verifies
left-padding, empty closed windows, valid all-zero candle rows, and payload
exclusion for the active reasoning MTF encoders. The audit also adds the
versioned `mtf_empty_stream_masked_v1` encoder for empty-stream masking while
preserving legacy `mtf` checkpoint semantics. Per-feature warmup validity and
the broader active-feature mask gate remain open.

The [observation warmup-validity packet](observation_warmup_validity/README.md)
measures all nine configured training streams and source-reviews representative
missing-value causes. It found that finite day-of-week features were being
turned into missing values by zero-variance rolling normalization; the
`v37-zero-variance-neutral` correction maps those finite values to zero and
leaves true missing inputs nonfinite. After regeneration, M1 nonfinite cells
fall from 5.84% to 4.99%, and sampled HTF rates range from 14.19% to 21.22%.
Conditional event distances and ages still require a full feature-validity
contract; this packet does not close that gate.

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
