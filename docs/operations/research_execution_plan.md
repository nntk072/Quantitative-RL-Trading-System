# Active research execution plan

This page is the operational queue for the current research program. It records
the last evidence-gate disposition and the conditions for any successor work;
it is not a general architecture guide or a personal academic-submission plan.

## Current gate disposition

The latest recorded selected-pair evaluation is the seed-50 P6 reanalysis
completed on 2026-10-24. The treatment recorded 987 positions and −2.154%,
with aggregate ledger equity ending at $97,845.69. Its strict zero-breach
risk-survival gate failed on one `daily_loss` event on 2025-03-06. The
evaluation nevertheless completed the configured data split. Its matched
control recorded 825 positions, −10.056%, aggregate equity $89,943.95, and two
breach events: `daily_loss` on 2025-03-06 and `max_drawdown` on 2025-10-28.
That evaluation also completed the data split; its aggregate endpoint was
$56.05 below the $90,000 floor. Both arms failed the declared survival gate.
At the pinned run source, `trading_policy.mode=legacy` accumulated gross
negative closed-trade P&L without offsetting winning closes or measuring net
daily equity. The March `daily_loss` events therefore establish failure of
that configured legacy counter, not an FTMO-style net daily-equity breach. The
close ledgers show gross negative closes of $5,017.66 / $5,399.25 and net
realized close P&L of −$3,004.28 / −$3,389.32 for A4A / A4B through those
events. A4B's later `max_drawdown` event is separate. The stored `fail_time` is
the first breach timestamp, not the episode end. The report-period evaluation
also breached the hard floor for both arms; that interval is exposed exploratory
evidence, not a fresh confirmation period.

The retained A4A/A4B training decision, fill, and position tables have now
been reconciled by `position_id`: all 987/987 A4A and 825/825 A4B positions
link to fill events, close-fill PnL matches each position, and aggregate PnL
matches reported metrics and ending equity to under $1e-9. Every open has a
recorded 60-second decision-to-submission gap, consistent with the documented
bar-label/completed-bar boundary rather than measured inference latency. This
does not add the missing candidate-proposal-to-action linkage or identify a
causal loss mechanism. A separate TickBook analysis now derives descriptive,
timestamp-bounded per-position MFE/MAE for both training arms; it does not
resolve candidate linkage or make a feasible-exit claim. See the [paired
lifecycle research topic](../research/selected_policy_trade_lifecycle.md),
the evidence packet at
`evidence/research/selected_policy_trade_lifecycle/trade_excursions/README.md`,
and `evidence/research/failure_mechanisms/README.md`.

Do not resume or duplicate the failed run, start a 20M-step continuation, or
start the corrected five-seed comparison while P6 is failed. A successor needs
a specific, evidence-supported change to a scientific factor, a newly
registered matched configuration, and a predeclared acceptance rule. Preserve
the failed results and their run identities as historical evidence.

## Period roles and fixed inputs

- The recorded training period is 2024-12-30 through 2025-12-31.
- The inspected reporting period is 2026-01-01 through 2026-10-16. Treat it as
  exposed exploratory/report-only data; a rerun on the same dates cannot make
  it a fresh holdout.
- The M1 sequence is the policy timeline. Supplied M3–D1 bars and bid/ask ticks
  remain available to configured features and execution.
- Retain all supplied bars and use the session labels carried by current local
  data. External schedule authority, provider identity, and timestamp/license
  research are outside the user's requested scope; do not treat them as active
  gates or make claims that require them.
- Any future comparison must preserve matched data, features, action meaning,
  costs, risk rules, training budget, seed, starting capital, and evaluation
  window, or explicitly identify the difference and limit the claim.

## Completed evidence gates

- **Inputs and split:** chronological train/report identities and split-cache
  provenance are recorded in run manifests. Supplied local session context
  reaches training and reanalysis from each date's first bar. This work does
  not validate an external calendar or feed clock.
- **Feature prefix check:** the source-current all-profile report at
  `evidence/research/feature_causality/real_market_feature_prefix_invariance_all_profiles.json`
  completed in four parallel processes inside existing GH200 job `21376798`
  on 2026-11-03. It resolved 130 configurations into 19 feature-builder
  groups and checked three cutoffs (2025-12-15, 2026-03-09, 2026-06-15):
  **57/57 comparisons passed**, with no changed features and maximum absolute
  delta 0.0. The fail-closed merger required all four shard identities and
  complete group/profile/cutoff coverage. Independent verification matched
  the current verifier SHA-256
  `e0b3c038e6673a3bf0cfa147eb39b7761bfb99de754e1cb3f29e7fbc477b7566`, the
  profile-inventory SHA-256
  `fe0fd290834c31831d7486a0f26b0e6a04a4922d377b02a4458f56b2e4fdf84d`, all
  78 recorded feature-source hashes, and all four local M1 input hashes. The
  final `git diff --check` passed. This closes the real-market prefix
  invariance slice for the resolved inventory and recorded inputs; it does not
  establish every execution, label, or model-selection path.
  Prefix runner tests now pass 19/19 and the feature inventory suite passes
  3/3. A regression fixture was corrected to include the required `test_start`;
  no feature or market-data source changed during the live audit.
  The earlier selected-profile reports remain historical evidence.
  The synthetic
  assembled-matrix property also passes for its selected configuration: a
  900-row feature matrix matches through a 700-row prefix, covering configured
  technical indicators, FVG, PO3/IFVG state, and higher-timeframe
  premium/discount outputs together. The prefix comparison does not prove every
  execution, label, or model-selection path is leakage-free. Direct
  swing-structure fixtures now check HH/HL/LH/LL
  classification, current-first history slots, and trader-context precedence.
  The history fixture found and fixed a reversed swing-history slot order;
  `FEATURE_CACHE_VERSION` was advanced to `v35-causal-swing-history-order` and
  then to `v37-zero-variance-neutral`; prior caches are not reused for changed
  feature columns. The SMT source test now removes internal secondary bars,
  checks the declared last-observation forward-fill for spread values, and
  compares the full result with a truncated-prefix result. The selected
  research overlay inherits `smt.enabled: false`, so this is source-contract
  evidence, not an active-policy effect or a maximum-staleness guarantee. The
  selected historical policy artifacts remain unchanged.
  A source review also confirmed a multi-date session-level discrepancy:
  `detect_session_levels` applies its rolling high/low to the pooled time-of-day
  subset across the full input history, while `features/context/session_levels.py`
  groups running session OHLC by date. The latter's module docstring currently
  calls the semantics matching, which is inaccurate. A two-date fixture now
  captures the prior-date extreme at the next Asian open and checks full-versus-
  truncated prefix equality; all 17 session-level tests pass. A source-to-test
  graph review records 18 call sites across 15 nodes and 11 linked tests in
  `evidence/research/function_test_coverage/critical_symbol_review.md`.
  The current public output's `prev_day_close` is also assigned from
  `close.shift(1)`, not the previous calendar day's close; this raw column is
  excluded from MTF model inputs. The `detect_session_levels` and
  `features/context/session_levels.py` semantics remain distinct; both current
  docstrings misstate that relationship. Preserve the verified feature-source
  hashes for now; any source/docstring correction must be versioned and
  followed by a fresh all-profile audit. No future leak or model behavior
  change is inferred from these naming/documentation defects.
  The
  full causal feature gate remains open for logical-event cardinality and
  candidate-proposal-to-action linkage; prefix invariance does not establish
  causality for execution, labels, or model selection.
- **Structural order geometry:** source review confirmed that the environment
  supplies `cost_model.point_size` to order construction and that targets round
  toward entry before legality checks. The audit found that structural stops
  applied their buffer without rounding the executable stop to that same grid.
  `stop_menu` now validates the increment, rounds long stops down and short
  stops up (away from entry), then checks side and minimum distance. The
  focused order-geometry module passes 45/45 and the combined grid, target-time,
  bid/ask, direction-validation, and simulator quote-contract batch passes
  86/86; the packet's
  source/output hashes verify at
  `evidence/research/structural_order_geometry/`. This closes the source
  contract and synthetic grid cases; empirical candidate geometry, historical
  candidate-to-action linkage, and the broader D gate remain open.
- **Candidate price-geometry support:** the reusable analysis command in
  `scripts/research/analysis/features/candidate_geometry_support.py` uses the
  shared training-window and candidate-support rules in
  `scripts/research/analysis/features/training_context.py` and now
  measures training-only source-zone and standard-deviation retracement-band
  availability for the selected profile. It hashed all 17 configured training inputs against the local data
  manifest and processed 351,432 feature rows for 2024-12-30 through
  2025-12-31. The 24 configured candidates account for 488,008 active
  candidate-row occurrences. Six active M1 PO3/IFVG candidates expose source
  zones over 103,217 occurrences; the other 18 configured standard-deviation
  candidates expose timeframe-specific retracement bands over 384,791
  occurrences. Every one of the 488,008 active candidate rows has finite,
  ordered bounds; no active row has invalid geometry. The 68 catalog entries
  with expected source-zone fields are disabled candidates with zero active
  rows, not missing geometry in the selected profile. Report, source, input,
  and output hashes verify at
  `evidence/research/candidate_geometry_support/`; focused geometry tests and
  touched-path Ruff checks pass. This establishes feature-level geometry
  availability only. It does not define proposed entries, stops, targets,
  expiry, fills, or returns and does not close Stage D. The M3 challenger can
  use the measured source-zone and retracement-band inputs, but still needs a
  versioned candidate-object and executable entry/risk contract before policy
  integration.
- Supplemental synthetic profile coverage completed as Slurm job 21362641:
  17/17 distinct feature trees in the 130-profile resolved inventory produced
  matching assembled features for full 3,600-row inputs and separately
  truncated 2,400-row prefixes. The report is
  `evidence/research/feature_causality/feature_profile_prefix_invariance.json`;
  it includes the inventory fingerprint and generated-source/resolver hashes.
  It used synthetic two-symbol bars and establishes no real-market behavior.
  The focused validation batch passed 179 tests and Mypy passed. Both this
  successful run (1:59) and its fixture-correction predecessor 21362583
  (0:59, exit 1) were under the 120-second Slurm-step minimum; both are recorded
  as launch-control deviations in the external agent plan ledger, with no
  retry planned. Together, the real-market and synthetic profile checks cover
  complementary slices of the 130-profile inventory; neither alone closes
  Stage D.
- **Synthetic timing examples:** four source-ordered SVG examples now show the
  PO3/IFVG confirmation-to-fill sequence with explicit illustrative UTC labels,
  the invalid same-bar pre-confirmation fill, the previous-session premium
  gate, and the optional retest path. The focused renderer test passes. The
  figures are synthetic; the premium example makes no external calendar claim.
  See `evidence/research/feature_causality/synthetic_event_timing_examples/`.
- **Timeframe mask slice:** 38 focused mask cases pass for closed-window
  padding, all-zero but valid candle rows, nine-stream MTF shapes,
  masked-payload exclusion in the current reasoning encoders, and valid-history
  use. A follow-up adds `mtf_empty_stream_masked_v1`: a distinct architecture
  ID that zeros unavailable stream tokens while preserving the old `mtf`
  encoder mapping and parameter schema. The selected encoder/config/catalog
  integration batch passes 66 tests, including agent checkpoint round-trip.
  The timestep mask still marks candle availability only; per-feature warmup
  values are separately zero-filled with no per-feature mask. This closes the
  legacy empty-stream behavior slice, not the broader warmup/mask gate. See
  `evidence/research/feature_causality/timeframe_mask_semantics/`.
- **Observation input contracts:** `pad_observation_window` rejects
  non-positive window lengths and inputs outside its documented 1D/2D shape
  contract. `normalized_account_vector` rejects non-finite inputs, non-positive
  equity where the legacy log coordinate requires positivity, and non-finite
  float32 outputs. Eighteen direct contract cases, 22 simulator
  observation-schema cases, and 23 live adapter cases pass; touched-path Ruff,
  the refreshed source-to-test map, its 2 focused checks, and `git diff --check`
  pass. Valid legacy observation coordinates are unchanged. Broader
  warmup/mask semantics remain open.
- **Saved-policy action decoding:** the SB3 adapter and backend-neutral action
  converter now reject fractional or non-finite discrete outputs, non-finite
  continuous outputs, and decisions whose category names or schemas disagree.
  This prevents silent category truncation and invalid values reaching rollout
  consumers. Adapter/provider tests pass 19/19, and action-schema plus
  checkpoint-contract tests pass 17/17; touched-path Ruff and
  `git diff --check` pass. Valid saved-policy action mappings are unchanged.
- **Observation warmup-validity slice:** measured the selected training
  observation on all nine streams. A source check showed finite day-of-week
  features became nonfinite when a 252-row rolling window had zero variance;
  `v37-zero-variance-neutral` now maps those finite values to zero and keeps
  genuinely missing source values nonfinite. The regenerated packet reports
  4.99% nonfinite M1 cells and 14.19%–21.22% in sampled HTF cells. Representative
  sweep-age, standard-deviation-distance, BOS/MSS, startup-session, and tick
  quote semantics are recorded in
  `evidence/research/feature_causality/observation_warmup_validity/`. The
  source-current all-profile refresh now verifies 130 profiles, 23 observation
  contracts, 15,571 feature rows, zero group errors, matching start/end/current
  source hashes, valid checksums, and the exact inventory/output/cache/worker
  regeneration command. Its focused tests and touched-path Ruff pass. The
  reusable triage packet in
  `evidence/research/feature_causality/observation_validity_priorities/` now
  aggregates 1,291 feature/timeframe pairs across 23 profile groups. It flags
  two features that are entirely non-finite in every group (the D1 Asia/London
  midpoint distances), 208 pairs with interior missing values, and 220 with a
  missing/finite-zero collision. These are observed patterns, not producer-cause
  findings. Source review confirms `sweep_*_age` is non-finite without active
  sweep state and zero on the event bar; the same producer exposes the event
  pulse, while the observation path maps non-finite values to zero and has no
  per-feature mask. The triage report also finds `M1 po3_phase` non-finite on
  71.7% of sampled rows across eight profile groups, with missing/zero
  collisions. `build_po3_phase_features` emits NaN outside its configured
  session and phase 0 for valid accumulation; observation conversion maps both
  to zero. `session_progress` is clipped to 0 before session start, so it does
  not explicitly distinguish that outside-session state from the first
  accumulation row. This is a source-confirmed input-semantic collision and
  requires a versioned representation decision before using that feature in a
  new policy. A reusable source-semantic crosswalk now maps all 1,291 measured
  feature/timeframe pairs to 41 reviewed producer contracts, preserves the
  measured missingness/finite-zero counts, and records companion signals and
  representation limits. Three focused tests and packet checksums pass at
  `evidence/research/feature_causality/observation_validity_semantics/`. The
  crosswalk closes the producer-source reconciliation inventory; the
  versioned observation-validity decision remains open for the unmasked
  conditional values. Real-market prefix validation is being rerun because
  the first complete report embedded a stale verifier hash.
- **Candidate source-time census:** the training-only opportunity census
  measured 488,008 active rows across the 24 candidates supported by the
  selected overlay. All active rows resolved to 109,391 candidate-scoped
  source-time IDs; none had a missing required source timestamp. PO3 IDs include
  the same-direction, same-timeframe IFVG confirmation time and source FVG
  origin (M1 uses the selected aligned IFVG-zone origin; MTF uses the source-
  timeframe PO3-state origin); FVG and IFVG identities include the selected
  zone origin alongside confirmation/retest time. Adjacent event pulses are retained as separate FVG
  zones, and deterministic overlap fixtures verify which selected scalar zone
  supplies the identity. The identity contract is now v3. The v3 census was
  regenerated after a focused source review found and fixed the M1 legacy PO3
  origin mapping; source-time coverage is again complete. The
  refreshed matrix schema v2 records reviewed source-contract metadata for all
  106 public feature/upstream candidates (95 feature functions and 11 upstream
  transforms) and row availability for all 108 setup flags. The current packet
  checksum is `76a977a96514bb1ffbc0cb33c57b2f8259ba80d89dd5f9d5586bcd7f7215f9b2`;
  the inventory includes the FVG per-zone retest ledger, IFVG confirmation
  ledger, and candidate-identity serializer. Direct SMT coverage now includes
  internal missing secondary bars and prefix truncation, while explicitly
  leaving source-clock and maximum-staleness limits open. The IFVG diagnostic
  ledger now also has a direct full-versus-prefix test for both scalar output
  and all earlier per-zone confirmations; this does not resolve external
  publication timing or downstream proposal/action cardinality.
  The current FVG, IFVG, order-block, PO3 lifecycle, standard-deviation swing,
  and candidate-census contract suites pass 25/25 synthetic cases across seven
  research test modules. They verify ledger/scalar reconciliation, event
  suppression and identity accounting; they do not reconstruct historical
  proposal-to-action links or establish full logical-event cardinality.
  The `reachable_r` context feature retains its legacy zero fill by default.
  An opt-in `env.reachable_r_validity_mask` sequence column now distinguishes
  unknown prior-session range from a valid zero, with synthetic coverage for
  both cases and bundle-mode compatibility checks. The selected historical
  configurations leave this option off; their observations and results are
  unchanged, and the new column is not evidence that those historical inputs
  were repaired. This closes the source/API ambiguity for future explicitly
  versioned configurations only; active-profile and full-config coverage
  remain part of the open causal-feature gate. The matrix/config/factory
  inventory now resolves 130 profiles across the canonical default, feature
  and strategy overlays, research overlays, saved experiment-run specs, and
  legacy variants into 17 exact feature-tree fingerprints. One saved run spec
  declares list-valued `features.ema_periods`; the run-override serializer and
  config loader now support validated flat primitive lists. A focused resolver
  test covers this saved spec's value. This is static config coverage, not
  producer execution or causal evidence. Feature behavior across untested
  profiles remains open. The packet is in
  `evidence/research/feature_causality/`.
  regression suite passes 17 tests, including frame/shared-bundle equivalence
  in both mask modes and fixed-action parity across four MTF architectures on
  synthetic inputs. This is implementation evidence, not market-policy
  evidence. Its Slurm step completed in 80 seconds, below the 120-second
  minimum; no retry or fan-out was made, and the operational deviation is
  recorded in the external work ledger.
  Descriptive lifecycle totals are 115,863 identity-episode starts, 13,758
  adjacent active identity changes, and 5,719 source-time IDs reused across
  separate active-mask episodes. These are not logical event counts. The
  packet and matrix record per-candidate totals and matching source/data hashes.
  This establishes timestamp resolution for this profile only, not one ID per
  logical setup, full event cardinality, execution, or publication timing.
  Independent packet verification confirms all 15 output checksums, all 13
  recorded source hashes, the resolved-config hash, and the local-data-manifest
  hash match. The tables contain all 108 setup IDs: 5,616 month/regime cells
  (52 per candidate, with 1,248 supported and 4,368 explicitly unsupported
  under this overlay) and 648 horizon rows (six per candidate). This verifies
  report coverage; unsupported means disabled by the selected config, and the
  rows do not represent executable trades or ground-truth logical events.
  A separate support review now marks 84 tuples unsupported, 22 with at least
  10 contiguous active-mask identity episodes, and two D1 standard-deviation
  directions with fewer than 10 such episodes. The low-episode flag is a
  descriptive screen only; these are not logical-event counts or independent
  samples. Month/regime and horizon review tables retain the original cells and
  add the candidate-level support status. Evidence and hashes are in
  `evidence/research/trade_setup_opportunity_census/`.
  The refreshed cross-timeframe alignment table
  (`evidence/research/trade_setup_opportunity_census/candidate_event_cross_timeframe_alignment.csv`)
  enumerates 72 configured standard-deviation timeframe pairs. Summed across
  those pairs, 140,910 M1 rows were jointly active and identity-resolved; 6,692
  rows had matching normalized source-time key tuples, covering 389
  pair-local distinct tuples (a sum across pairs, not a global event count).
  This is timestamp alignment evidence only; it does not establish shared
  logical events or count suppressed overlapping zones.
  The global strict-tuple ledger
  (`evidence/research/trade_setup_opportunity_census/candidate_source_time_tuple_clusters.csv`)
  contains 108,712 family/direction/ordered-source-time-key groups across
  the 24 supported candidates. Of those, 654 are represented on multiple
  timeframes and 378 have simultaneous active rows on multiple timeframes;
  candidate memberships sum to the 109,391 candidate-scoped IDs and every
  group's candidate count matches its timeframe count; 488,008 candidate-row
  occurrences reconcile to the active identity census.
  Only standard-deviation groups span multiple timeframes in this profile.
  These counts compare integer keys normalized from nullable numeric feature
  columns. Current epoch-nanosecond values pass through float64 and may round
  at subsecond precision; the configured M1 event keys remain separated at
  minute resolution, but they should not be read as exact nanosecond instants.
  The tuple counts are key linkage evidence, not ground-truth logical events;
  pairwise matches, scalar zone selection, feed publication timing, and
  proposal-to-action cardinality remain separate questions.
  A reusable
  `scripts/research/analysis/features/standard_deviation_swing_ledger.py`
  now audits the selected profile's one-current-leg swing retracement
  projection on all nine enabled timeframes. The training slice has 59,057
  timeframe/direction source-leg projections; 36,008 have at least one
  candidate-eligibility row, while 23,049 do not. There are 57,634 exact
  direction/pivot-key groups across timeframe projections, of which 1,346 are
  represented on multiple timeframes. These count the producer's latest
  confirmed leg keys and contiguous eligibility episodes; they do not
  enumerate latent overlapping swings or establish logical market events,
  policy decisions, orders, or trades. The hash-linked packet is
  `evidence/research/standard_deviation_swing_legs/`; its focused ledger test
  passed. This narrows the selected-profile swing-projection gap but does not
  close Stage D event cardinality or candidate-to-action linkage.
  The selected-profile M1 IFVG packet
  (`evidence/research/ifvg_zone_event_ledger/README.md`) separately records
  72,561 per-zone confirmations against 56,349 scalar pulses. It identifies
  13,136 same-row/direction collision groups containing 16,212 additional
  source-gap confirmations beyond the selected scalar zone; every scalar
  pulse reconciles to its marked newest source gap. There are 6,919 bullish
  groups (8,571 suppressed confirmations) and 6,217 bearish groups (7,641
  suppressed); collision groups range from two to six source gaps and occur in
  all 13 training months. These are detector events, not separate policy
  proposals or trades. This covers the configured M1 path only: MTF IFVG is
  disabled in this overlay. Other zone families, timeframes/configurations,
  proposal-to-action linkage, and logical event cardinality remain open.
  When multiple same-side zones fire together, current features select the
  latest source event in deterministic order and now retain that selected
  origin. Other colliding zones are not represented as separate model actions.
  A separate training-only packet,
  `evidence/research/ifvg_timeframe_collision_ledger/README.md`, now audits
  `config/2_po3_ifvg.yaml` across M1, M3, M5, M10, M15, M30, H1, H4, and D1.
  It records 105,451 per-zone confirmations (105,449 available within the M1
  spine), 86,629 source-timeframe scalar events, and 78,709 events selected by
  the configured M1-first/first-timeframe-wins merge. The packet identifies
  18,734 same-availability-row/direction collision groups, including 6,279
  spanning multiple source timeframes, with 26,740 visible per-zone events
  suppressed by scalar projection; a collision group contains up to 20
  source-zone events. Eight native input files are linked to the pinned local
  manifest by path, size, and mtime; D1 is marked as derived from M1. Source,
  schedule, config, and packet hashes reconcile. These remain detector-event
  counts, not logical setup counts, policy proposals, orders, or trades. This
  closes the configured detector-level merge census for this one MTF profile;
  other configurations, policy-action cardinality, external feed publication
  timing, and logical event identity remain open. FVG retest
  candidates are disabled in this overlay. A diagnostic FVG zone API now
  returns the unchanged scalar feature block alongside every per-zone retest
  confirmation and marks the zone selected by the scalar projection. A
  synthetic overlap fixture confirms that both source zones are retained and
  only the newer one is selected. The configured M1 training census now records
  29,327 per-zone confirmations against 27,266 scalar pulses. It identifies
  1,950 same-row/direction collision groups with 2,061 additional zone
  confirmations beyond the selected scalar zone. Bullish zones contribute
  15,469 confirmations, 14,334 scalar pulses, and 1,135 suppressed
  confirmations across 1,066 groups; bearish zones contribute 13,858, 12,932,
  and 926 across 884 groups. Collisions occur in all 13 training months; group
  sizes range from two to five zones. Event rows reconcile to the scalar
  projection, and the census output hashes, current source hashes, selected
  config identity, and all 17 local training-input hashes match. These are
  configured M1 detector confirmations under the 0.1 gap-height reaction
  buffer, not policy proposals or trades. Other FVG timeframes/configurations,
  proposal-to-action linkage, and logical event cardinality remain open. See
  `evidence/research/trade_setup_opportunity_census/fvg_retest_zone_event_ledger.csv`
  and its monthly/collision summaries.
  A reusable training-only MTF FVG packet now lives at
  `evidence/research/fvg_timeframe_event_ledger/`. For the configured
  `features/fvg_ifvg_mtf.yaml` profile, it records 49,780 per-zone retests and
  46,285 source-timeframe scalar pulses across M1, M3, M5, M10, M15, M30, H1,
  H4, and D1. The blocks remain independent by timeframe; no cross-timeframe
  scalar merge is inferred. The ledger identifies 3,262 within-timeframe,
  same-row/direction collision groups and 3,495 visible per-zone retests not
  selected by their source-timeframe scalar. D1 is derived from M1; eight
  native training inputs are linked to the pinned local-data manifest, and
  source, config, schedule, and packet checksums reconcile. These are
  detector events, not distinct logical setups, policy proposals, or trades.
  Feed publication timing, external calendar authority, other configurations,
  logical event cardinality, and proposal-to-action linkage remain open.
  A diagnostic `build_po3_setup_lifecycle_ledger()` now projects the existing
  PO3 producer state into setup-sequence rows with sweep, reclaim, IFVG
  confirmation, rearm, and input-end phase fields; same-bar sweep conflicts
  remain separate rejected rows. Thirty-one focused PO3, MTF PO3, input checks,
  prefix-invariance, and causality-matrix tests passed. The refreshed
  matrix covers 107/107 function contracts across 215 rows
  (`ff0a35e916de365545a2c3770da6a004fd09b9b8caf3b299aa54d4e2f3eb96ad`).
  These rows describe the one-active-setup implementation, not concurrent
  latent patterns or ground-truth events. A reusable M1 packet builder now lives at
  `scripts/research/analysis/features/build_po3_setup_lifecycle_ledger.py`;
  it requires `reclaim_then_ifvg`, validates both configured M1 inputs against
  the pinned raw-data manifest, records producer/config hashes, and refuses to
  overwrite a non-empty evidence directory. The generated packet at
  `evidence/research/po3_setup_lifecycle/` records **16,692 accepted producer
  sequences** and **22 same-bar sweep conflicts** for the configured local M1
  training slice. The counts describe the selected one-active-setup producer,
  not ground-truth event cardinality, candidate proposals, policy actions, or
  trades. Its input hashes match the pinned local raw-data manifest; output
  checksums verify. Bar-indexed sweep, reclaim, IFVG-confirmation, and FVG-origin
  times are exact integer nanoseconds recovered from the M1 index. Nullable
  higher-timeframe pivot/confirmation fields remain explicitly labeled source
  float nanoseconds because float64 cannot retain exact epoch nanoseconds.
  A current-source rerun of the focused PO3 producer/lifecycle state tests passes
  29/29 cases; exact output and source hashes are recorded in
  `evidence/research/po3_setup_lifecycle/producer_state_validation/`.
  Job 21363360 completed the 1,194-test focused suite, scoped Ruff/Mypy and
  packet-specific 12-test suite successfully (16 CPUs, 64 GiB requested, 6:40
  elapsed; 17.2 GiB observed MaxRSS). Logical event cardinality and policy
  proposal/action linkage remain open.
- **Execution:** the selected run uses seeded 0–30 ms arrival latency and the
  first eligible bid/ask tick after order arrival; missing required tick input
  fails closed.
- **Recovery:** deterministic checkpoint recovery was verified. The associated
  smoke did not pass its training risk-survival gate and is not viability
  evidence.
- **Screen and selection:** the 18-variant corrective screen is terminal and
  exploratory. The predeclared matched pair is retained; the pair's later P6
  evaluation did not pass.
- **Reanalysis:** chronological non-episodic daily-loss breaches stop trading
  for that session and allow the rollout to continue. Maximum-loss and
  trailing-drawdown breaches remain annual failures. This behavior is covered
  by focused tests and was used in the seed-50 reanalysis. The seed-50
  `legacy` mode's daily counter sums negative closes without offsetting gains;
  it must not be treated as net daily-equity or FTMO daily-loss semantics.
- **Position stop lifecycle:** environment and event backtest now call one
  shared confirmed-swing stop calculation. Its 26 helper unit cases and 16
  paired lifecycle characterization cases pass, covering breakeven and
  trailing-stop updates, next-bar effectivity, protective-close outcomes,
  account guardrails, and scheduled session close. Exact output and current
  source hashes are preserved in
  `evidence/research/simulator_execution_parity/position_stop_lifecycle/`.
  These are controlled synthetic cases; financing, checkpoint/replay,
  historical-policy behavior, and full account/cashflow parity remain open.
  A later short-direction characterization found a floating-point no-op: the
  same protective level could be logged as a tighter stop when its two binary
  representations differed by one ULP. The shared calculation now suppresses
  numerically equivalent levels. The full backtest integration folder passes
  155/155, the shared stop-helper suite passes 28/28, and scoped Ruff plus
  `git diff --check` pass. This closes that no-op defect only; lifecycle and
  accounting acceptance remain open.

## Next actions and gates

1. Resolve and version the daily-loss/account contract for future research.
    The training environment and event-driven backtest now both reset daily
    counters on the supplied date-derived `session_id`, allow a daily-loss
    breach to clear at the next session, and latch maximum-loss/trailing-
    drawdown failures for the rest of the rollout. Focused characterization
    tests cover the reset and annual lockout behavior. `AccountState` now
    rejects non-finite monetary inputs before mutation, requires positive
    starting capital, and prevents negative payout-reset balances; its focused
    account/risk suites pass (52 tests). This protects the local accounting
    boundary but does not establish live account-state parity. Still validate
    deterministic equity, winning-close, losing-close, open-P&L, reset, and
    training/live traces against the supplied local session IDs. The historical
    legacy result stays immutable and cannot
   establish net daily-equity survival. Identify a specific economic
   mechanism before changing the research configuration.
   Do not tune on the exposed 2026 interval as if it were untouched.
   A deterministic shared `TickBook` trace now compares environment and
   event-driven backtest entry/exit quotes, fill times, realized close P&L,
   and final balance. It exposed and fixed a one-bar-late environment action
   exit quote. The focused trace/account/tick/action/EOD/lifecycle suites pass
   (71 tests), including fixed and randomized tick-arrival latency. A delayed
   whole-bar entry now fails closed at a supplied-session boundary when
   overnight blocking is enabled; the focused decision-correlation suite
   passes. With overnight blocking disabled, a delayed order may cross the
   supplied session boundary, matching environment behavior.
   `execution.fill_latency_bars` is now validated in configuration, passed
   into direct and bundled environments, and consumed by the event-driven
   backtest and both config-driven backtest runners. A controlled shared
   `TickBook` trace with three added bars verifies matching submission and
   scheduled-fill times, entry and exit quotes, pending-entry rejection,
   action-driven exit while an entry waits, and final balance. The test is
   synthetic and does not claim historical-policy or full local-feed parity.
   A controlled 52-minute local US100 trace reproduces the selected entry and
   exit through the current TickBook parser in both engines. The expanded
   packet below supersedes this single-pair coverage; neither packet is a
   historical-policy replay.
   A controlled 52-minute replay now also uses two current local US100 M1/tick
   intervals. Both fill timestamps match unique, complete source quote groups
   from the recorded alignment scan; the production TickBook selected both
   quotes and environment/backtest fills, PnL, and ending balance reconcile.
   This is not a historical policy replay. See
   `evidence/research/simulator_execution_parity/README.md`.
   The same controlled trace runner now has a separate 23-pair local-feed
   packet: one eligible pair per month/direction stratum where a complete,
   unique source quote group resolves through the current TickBook. It covers
   January–December 2025 and both directions overall; every selected
   environment/backtest entry, exit, close-PnL, and ending-balance comparison
   passes. This satisfies the minimum one-real-feed-trace criterion under the
   unique, complete source-quote selection rule. These are controlled action
   traces, not policy replays or a campaign result. The packet records the
   exact input and generator hashes.
   The first expanded run exposed a short-action encoding gap in the trace
   generator, now covered by long/short synthetic regression tests. Its
   corrected one-step rerun completed in 106 seconds, below the repository
   120-second Slurm step hard gate; no further allocation or retry was started,
   and both scheduler logs are preserved outside the repository. This is an
   operational launch-control deviation, not research evidence. The broader
   sample does not resolve timestamp ties, external clock/session authority,
   market impact, or broker behavior.
   A controlled account-transition trace now applies prescribed opens/closes
   across the local date-derived IDs for 2024-12-30 and 2024-12-31. Each engine
   resets its own next-session starting balance from its own first-session
   close PnL, but bar-only execution does not reconcile: `TradingEnv` fills at
   the next bar open and `run_backtest` at that bar close. On this two-trade
   fixture, fill timestamps/prices and close PnL differ; ending balances differ
   by $0.60877. The existing backtest contract explicitly names its fallback
   `bar_close`. The selected research path requires TickBook execution and
   fails closed without ticks, so this is an alternate-mode limitation, not
   evidence about the selected tick path or a policy result. See
   `evidence/research/simulator_execution_parity/local_session_account_transition/`.
   The trace does not establish cross-engine bar-fallback or live-account
   parity; Stage E remains partial.
   A source/config check confirms the current YAML config tree sets
   `costs.use_tick_execution: true` only in the base config and has no
   overriding false value. The shared resolver reads that setting;
   `training/runner/data_stage.py` builds the TickBook and checks split coverage,
   while training/backtest and baseline runners pass the effective requirement
   into their environments/backtest. This supports the scoped statement that
   the current configured path is tick-required, not proof of every historical
   run's resolved configuration.
   The preserved A4A and A4B run manifests in the external research archive
   also record `costs.use_tick_execution: true` and
   `execution.randomized_fill_latency_ms: 30.0` for both selected runs. This
   confirms the bar-only mismatch is outside that selected pair's recorded
   execution configuration; it does not generalize to every historical run.
   A second two-session trace now exercises the selected TickBook path with
   `tick_execution_required=true` and 30 ms randomized latency in both engines.
   On the same prescribed actions and local sessions (2024-12-30/31), both
   engines match all open/close session IDs, fill times, directions, prices,
   close PnL, session-start resets, and ending account state exactly within the
   declared numerical tolerance. The common first-session close PnL is
   -$1.9330539759; the next-session start balance is $49,998.0669460242 and
   both final balances are $49,999.8173159597 (zero cross-engine delta).
   Packet checksums pass. This closes only the controlled selected-mode
   account-transition slice; two sessions/two positions do not replace the
   existing broader lifecycle matrix, tie/missing-quote review, full account
   reconciliation, or live/restart-safe parity. It is not a policy or
   economic result. The report is
   `evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_account_transition.json`.
   A reusable independent verifier now replays the recorded event arithmetic,
   session attribution/reset balances, close-PnL-to-ending-balance identities,
   lifecycle comparison flags, current input-byte hashes, and source-code
   hashes for both the bar and tick reports. It marks both reports
   independently consistent; separately, it correctly records simulator parity
   as false for bar fallback and true for the selected tick path. The verifier
   outputs and its implementation are included in the packet checksum manifest.
   This validates the bounded packet's recorded numbers and provenance; it does
   not replace the full account/cashflow verifier or broader Stage E matrix.
   A separate selected-TickBook scenario also sets a controlled $1 hard daily
   loss limit. The first session's realized loss is -$1.9330539759; both
   engines record one `daily_loss` breach at session 0, suppress the scheduled
   same-session re-entry, reset the next-session starting balance to
   $49,998.0669460242, and allow one next-session open. Their event and account
   state match exactly. The independent verifier recomputes the breach time,
   reason, session, equity, attempted action, absence of later same-session
   fills, next-session entry, reset, and current input/source hashes. Both the
   report and verification checks pass. This covers this controlled daily
   limit path only. A separate episodic max-loss TickBook trace now also passes
   both engines and the independent verifier. Source review found that the
   environment sampled a second randomized-latency quote while force-closing,
   after the current step had already selected the executable quote; it now
   reuses that quote, matching the event-backtest's per-bar cache. Breach equity
   and daily loss are recorded before liquidation and match. Final daily-loss
   counters are explicitly not compared because the episodic environment stops
   at the breach while the backtest reaches the next-session reset; final
   balance and equity match. Full guardrail/action coverage and live/restart-safe
   parity remain open. Evidence:
   `evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_daily_loss_reset.json`.
   Max-loss evidence:
   `evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_max_loss_terminal.json`.
   The backtest now accepts explicit `env.eod_risk` settings and shares the
   environment's planned-risk-aware adverse-excursion cutoff; a paired
   synthetic trace and lifecycle tests pass. Omitting the setting preserves
   legacy backtest close-cap behavior. This resolves only that position-guard
   difference. A same-bar target/adverse-excursion fixture exposed and closed
   one more ordering mismatch: both engines now resolve a structural target
   before the position-level adverse-loss cutoff while retaining stop-first
   precedence. The paired characterization and adjacent risk suites pass
   (40 tests). A later paired trace now verifies the configured breakeven stop
   trigger, its next-bar effective time, the retracement fill, realized PnL,
   and ending equity in both engines; the config-driven scalar-action runner
   passes the static `risk.sl_mode` into the backtest. `run_backtest` supports
   fixed, breakeven, and trailing static modes. Trailing mode now tightens
   against the completed decision bar's protective-side confirmed swing, uses
   `env.sl_buffer_pts`, and takes effect on the next bar; paired synthetic
   long/short traces reconcile update price/time, stop fill, PnL, and ending
   equity, including an irregular inter-bar gap where effective time is the
   actual next input row. Both config-driven scalar backtest and rule-baseline
   runners now pass the resolved mode and buffer. The selected A4A/A4B
   configurations enable the versioned `trade_setup_overlay` action schema
   with an `sl_mode` coordinate. `TradingEnv` decodes that coordinate at each
   decision and records the selected mode on a newly opened position; the
   selected run's static `risk.sl_mode: fixed` is the defer/default value.
   The event-driven backtest accepts scalar actions and a single configured
   `sl_mode`, and explicitly rejects vector policy outputs. Existing paired
   traces therefore establish parity for fixed mode choices per trace, not for
   a learned sequence of per-entry mode choices. The preserved selected-policy
   evaluation uses `TradingEnv`; the event-driven runner is not evidence of a
   policy replay. Do not compare a learned vector policy through that runner
   until a schema-preserving bridge exists. Learned per-action stop-mode vector
   parity, comprehensive feed/lifecycle coverage beyond the selected 23 pairs,
   and live account-risk parity remain open. The scalar policy boundary
   rejects non-integer and vector outputs explicitly. Checkpoint
   evaluation and matched setup-policy comparisons use `TradingEnv` directly;
   the matched runner enforces an exact action-schema match across policy
   arms. A parallel Stage E validation on the existing GH200 passed 166 trading,
   485 simulation, 73 live-adapter, and 150 integration/backtest tests (the
   local-feed trace generator was excluded to avoid repeating its bounded data
   work). The first simulation run exposed two failures in a trailing-stop test
   double: it returned NaN/Inf directly instead of matching the production
   `_finite` helper contract. After correcting the double, the complete
   simulation suite passed; the 47-test account/risk parity slice and 33-test
   stop-management slice also passed. These are source/contract checks, not
   broker-connected or historical-policy evidence.
   The event-driven engine remains a scalar rule/diagnostic path, and a
   lossy vector-to-direction adapter would drop setup eligibility, risk,
   stop/target, and exit coordinates. A full cross-engine bridge is still open
   if a particular schema comparison requires it; its acceptance must include
   observation/action preservation and paired trace-level parity.
   A controlled forced-session-close trace found that the environment submits
   at the start of the final NY bar and resolves the first executable quote by
   bar end, while the backtest had submitted at bar end. The backtest now uses
   the same deadline resolver and event-time boundary. A focused 8-bar
   characterization passes with zero and configured 30 ms latency, matching
   open/close quotes, fill times, PnL, and final equity. A stable event-keyed
   latency RNG now isolates the scheduled-close sample from per-bar draw-count
   differences. The characterization includes distinct quotes at 5, 10, 20,
   and 25 ms after submission; both engines select the same arrival and quote
   at configured latency. Entry-fill and protective-exit latency are now also
   event-keyed; full event-type and lifecycle parity remains open.
   Evidence: `evidence/research/simulator_execution_parity/scheduled_session_close/`, independently verified by `scripts/research/analysis/evaluation/verify_scheduled_session_close.py` and covered by `tests/integration/backtest/test_risk_lifecycle_characterization.py::test_environment_and_backtest_share_tick_scheduled_session_close`.
   A follow-up characterization found that environment entry latency depended
   on earlier no-action steps because the environment prefetched a random quote
   each step while the backtest drew only when resolving an execution. Entry
   latency is now keyed by shared seed and fill-bar timestamp. Protective exits
   are keyed by shared seed, direction, trigger kind, and trigger timestamp in
   both engines. The synthetic trace confirms matching entry latency and
   protective trigger, arrival, fill, price, and PnL after no-action prefixes;
   the full risk-lifecycle characterization file passes 16/16. Other execution
   event types and broader cashflow/lifecycle parity remain open.
   Evidence: `tests/integration/backtest/test_risk_lifecycle_characterization.py::test_randomized_execution_latency_is_independent_of_prior_no_action_steps`.
   A separate controlled three-target ladder now exercises event-keyed 30 ms
   latency through TP1/TP2/TP3. Both engines match target slot, latency sample,
   arrival and selected tick, partial size, price, PnL, and final account
   balance. This synthetic lifecycle check does not establish live-feed or
   campaign-wide partial-fill acceptance.
   Evidence: `tests/integration/backtest/test_multi_target_protective_lifecycle.py::test_randomized_tick_latency_matches_across_all_partial_targets`.
   The training environment and event-driven backtest now also share a
   fail-closed quote-wait gap characterization: the first quote arrives 2 ms
   after scheduled fill against a 1 ms maximum wait, and both raise
   `TickExecutionUnavailable` instead of returning a candle-priced fill.
   Evidence: `evidence/research/simulator_execution_parity/quote_wait_gap/` and
   `tests/integration/backtest/test_account_transition_parity.py::test_environment_and_backtest_both_fail_closed_on_quote_wait_gap`.
   This is one synthetic boundary case, not an empirical stale-quote threshold
   or complete execution-lifecycle acceptance.
   A paired zero-action trace now checks both the environment and event-driven
   backtest with an empty TickBook and randomized latency configured. Both keep
   trades empty and preserve balance, equity, and daily-loss state; the focused
   characterization passes. This closes only the no-action account slice.
   Evidence: `tests/integration/backtest/test_no_action_account_parity.py`.
   A companion tied-timestamp trace places a stop-crossing quote before a
   target-crossing quote at the same millisecond. Both engines select the first
   source-ordered quote, close at the stop, and reconcile account balances.
   The test verifies deterministic parser/simulator behavior only; it does not
   claim source order is true sub-millisecond chronology. Evidence:
   `evidence/research/simulator_execution_parity/tied_protective_trigger_order/`
   and `tests/integration/backtest/test_account_transition_parity.py::test_environment_and_backtest_use_first_source_order_for_tied_stop_target_ticks`.
   The source call-path review now traces environment and backtest decision,
   pending entry, tick/bar quote resolution, protective exits, broker/account,
   and reward/report updates. Both current paths implement market-style fills;
   no order type, candidate limit price, or limit TTL is represented in these
   execution contracts. Limit-entry/maker-fill parity is therefore unsupported
   and remains an explicit design requirement for any later price-aware order
   interface. Evidence: `evidence/research/simulator_execution_parity/execution_path_map/`.
   `TradingEnv.step()` info now records the chosen setup ID,
   action-schema version, selected family/timeframe/direction, mask eligibility,
   and named action coordinates, including explicit no-trade and inactive
   choices. The shared evaluation rollout persists these fields in
   `trade_setup_decisions` and fails if its policy-observation mask disagrees
   with the environment's decoded action/eligibility. Nine focused unit and
   integration tests cover eligible, no-trade, and ineligible choices plus
   delayed order/open/close linkage and event-index reconciliation. This
   improves categorical action-to-mask-to-outcome traceability on synthetic
   inputs but does not add candidate price geometry or create configured-market
   evaluation evidence. The configured
   `positions.csv` projection now carries the opening `decision_id` and
   selected source-event identity/version/status/timestamps from the matching
   open event. A close event cannot overwrite that entry provenance, and
   close-only reconstructions receive no entry decision attribution. Focused
   tests exercise both the actual CSV writer path and the missing-open case;
   the full position/plot export unit module passes (39 tests). This supplies
   a future decision-to-position join when a position opens; it does not
   recover the absent historical per-decision records or provide market-policy
   evidence. The configured
   stale-progress rule is paired at an overnight NY-index gap in a shared-tick
   synthetic trace. A configured
   backtest max-age close is paired with `TradingEnv` in a shared-tick trace,
   including fill time, PnL, and ending equity. The trace also corrected the
   environment guard's fill timestamp to the market quote it actually selected.
   `run_backtest` now also accepts `daily_pnl_basis`, and config-driven
   training/baseline runners pass the resolved policy basis. Controlled tests
   cover legacy closed-loss versus session-net-equity calculations across
   winning and losing closes, open P&L, and a supplied-session reset. This
   changes the daily-loss state used by backtest guardrails only. The flat
   realized-balance payout event payload is built by a shared policy helper
   used by `TradingEnv` and `run_backtest`. `run_backtest` now supports
   controlled repeated-payout transitions: it sizes against configured
   account/daily capacity and execution reserve, withdraws realized balance
   above target while flat, resets operating capital, and reports payout,
   cycle, and total-economic-value series. A synthetic overshoot case and
   focused account, execution, risk-lifecycle, policy, configured-runner, and
   report-writer, and Tier 0 baseline tests pass (97 total across the focused
   suites); scoped Ruff and Mypy pass. A non-episodic continuous-action
   `TradingEnv` trace now
   matches the backtest on one repeated-payout long: size, structural target
   net PnL, payout amount, cycle count, reset balance/equity, daily-loss state,
   and total economic value. Additional synthetic cases cover two successful
   payout cycles and one account-breach failure. This remains narrow synthetic
   parity evidence. A second paired trace now covers a first-cycle
   payout followed by a second-cycle max-drawdown failure; both engines record
   one payout and one cycle-2 failure with matching event time/reason, account
   state, daily loss, and total economic value. The accumulated focused suite
   for payout policy/backtest, runner, report export, matched baselines, and
   lifecycle-report provenance passes (81 tests). The report
   writer persists the final economic-value scalar, its curve, and payout and
   cycle event ledgers. The config-driven runner now supplies structural-stop
   settings for repeated-payout mode and computes metrics from total economic
   value. No configured market-data result has been run. Other lifecycle edge
   cases, live account parity, and empirical policy evaluation remain open;
   synthetic results are implementation evidence only.
   Backtest entry sizing now applies both the configured per-trade ceiling
   and the effective account guardrail before sizing, matching the environment;
   long/short controls verify risk-capped lots and below-minimum rejection.
   Paired long/short insufficient-margin tests now verify that the shared
   broker rejects entries in both engines without creating trade events,
   registering a traded session, or mutating balance, equity, open PnL, or
   daily loss. This closes the controlled margin-rejection case only; actual
   broker margin schedules and live-account parity remain open. Financing is
   explicitly not modeled in the current intraday contract: the configured
   environment closes positions at the NY session boundary, and `CostModel`
   contains spread, slippage, and commission but no financing charge. The
   sustainable-equity method documents that limit. Overnight-enabled runs and
   broker financing effects remain unsupported; this is a declared cost
   omission, not broker or financing parity.
   The config-driven backtest and baseline runners now pass resolved evaluation
   guardrails. `training.runner.backtest` resolves repeated-payout lifecycle
   settings, requires structural stops through the repeated-payout backtest
   contract, and computes report metrics from total economic value. It has not
   been run on configured market data. Environment/backtest parity remains
   established only for the narrow synthetic repeated-payout trace; broader
   lifecycle and training/live account parity remain open.
   The MT5 live bridge remains a separate contract: its strategy call supplies
   no account snapshot, v1 uses default account fields, v2 fails closed without
   the full state, and the configured RiskManager enforces percentage sizing
   and broker-stop exposure rather than simulator daily/max-loss latches. The
   config explicitly distinguishes these policies. The RL and multi-symbol
   robot constructors reject non-paper startup unless the supplied manager
   advertises training-equivalent daily and maximum account-loss guardrails;
   the bundled manager does not. The single-symbol crossover robot rejects
   non-paper construction, and its CLI fails before MT5 login. The multi-symbol
   CLI now also rejects non-paper mode before loading configuration or creating
   MT5-backed components. The shipped robots therefore remain unavailable for
   real-order mode. The current focused batch passes 27/27 live robot, CLI, and
   guardrail tests; scoped Ruff format/lint and `git diff --check` pass. This
   closes the fail-fast entrypoint behavior, but does not implement the missing
   provider or account-state lifecycle. The full `tests/unit/live` folder now
   passes 73/73 after close orders were changed to compare against MT5's named
   buy/sell constants instead of numeric literals; this also resolves the two
   quote-side test failures. The current manager reads balance/equity and open
   stop exposure but has no restart-safe session-start equity or trusted
   session identifier, so implementing parity from the available broker
   snapshot would be unsound. Training/live account parity is unresolved and must
   not be claimed. The shared v2 observation builder now rejects non-finite
   fields, unsupported directions/modes, malformed target masks, and invalid
   position geometry before encoding; this is input-contract hardening, not
   evidence of account-risk parity. The focused RL robot, multi-symbol robot,
   bridge, robot, multi-symbol stop, risk-contract, and guardrail suites pass
   (54 tests); no broker-connected integration trace was run. Current
   source/test-body inspection records the bounded real-order guard contract
   in `evidence/research/function_test_coverage/critical_symbol_review.md`:
   the bundled manager remains ineligible for real orders, the crossover path
   is paper-only, and no restart-safe account-risk provider exists. This
   inspection does not claim training/live parity or broker-connected testing.
   `evaluation/rollout/matched_setup_baselines.py` composes always-no-trade,
   seeded random eligible-setup, and caller-supplied existing-policy arms
   through the source-configured evaluation path, with separate policy and
   execution seeds and exact environment action schemas. Existing-policy arms
   require checkpoint identity, training identity, action mode, and an exact
   schema match; stochastic action selection has an explicit isolated seed.
   The evaluator records bars, features, and
   TickBook content hashes. `evaluation/reporting/matched_setup_baseline_bundle.py`
   writes an immutable content-addressed draft manifest with per-policy
   decisions, event ledgers, equity, metrics, input identity, resolved config,
   source identity, and verified artifact hashes; it rejects inputs whose
   hashes differ from those evaluated. Synthetic tests validate the v2
   manifest and artifact hashes, mismatched-input rejection, and immutable
   bundle behavior (40 focused tests pass). The bundle records risk sizing mode,
   dollar settings, action risk range, and hard per-trade limits. Any
   non-synthetic Tier 0 evaluation now requires an explicit positive
   `absolute_risk_budget_usd`; the evaluator clones the source config into
   `dollar_band` mode, sets the band ceiling to the explicit absolute risk
   budget for every policy action coordinate, enforces the configured
   per-trade cap, and
   persists the exact effective config used. Synthetic contract tests may omit
   the budget. The source config's `dollar_band` budget includes modeled
   execution reserve and is capped by sizing and guardrail limits. A guaranteed
   synthetic random-policy open asserts event-level approved risk stays under
   the declared $250 ceiling and modeled stop risk plus execution reserve stays
   under approved risk (8 matched-baseline integration tests pass). This covers
   that controlled ledger path only. Fixed-risk
   mode instead ignores the coordinate and does not deduct modeled reserve.
   The ceiling is a shared maximum requested budget, not evidence that policies
   have the same realized-risk distribution. The immutable bundle accepts
   additional arms only when their checkpoint source file hash matches the
   declared SHA-256; comparisons against random are descriptive.
   The current default still uses dynamic equity-scaled risk, so no matched
   absolute-budget market-data result exists. This config-level contract does
   not establish equal realized-risk distributions; no market-data evaluation
   or frozen economic result exists.
   Tick-sourced market fills now share one adverse-slippage helper in the
   environment and backtest. `run_backtest` applies the configured override
   once to tick entries, discretionary/protective closes, and terminal
   liquidation while preserving bar quote and structural-level cost behavior.
   Paired long/short tick traces, protective/terminal cases, and adjacent
   environment tests pass (91 tests). This closes that explicit stress-setting
   mismatch; broker/live parity and broader simulator lifecycle cases remain
   open.
   The shared buffered breakeven calculation now validates stop geometry and
   is reused for trigger-based and post-partial environment updates. No-op
   partial checks no longer emit `sl_update` events. The combined domain suite
   (`tests/unit/trading`, `tests/unit/simulation`, and
   `tests/integration/backtest`) passed 747 tests with three transformer
   warnings in Slurm job 21360487 (4 CPUs, 32 GB requested, 5:51 allocation,
   5:02 pytest); the new long/short/no-widen and tick/bar no-op regressions are
   included. This is simulator implementation evidence only. Feed-wide
   chronology, live-account parity, and empirical policy evaluation remain
   open.
2. Register any proposed successor with immutable data, source, config,
   feature/cache, checkpoint, and run identities. State the control, treatment,
   changed factor, evaluation window, risk gate, and action-mode/seed rules in
   advance.
3. Run a bounded P6 pair only after the new protocol is complete. Advance to
   multi-seed comparison or cost stress only if the pair passes its declared
   gate. Keep prior failed runs unchanged.
4. Freeze a consolidated result report only after the corrected P6 evidence
   and any authorized successor comparison are complete. Report negative and
   inactive outcomes, period exposure, uncertainty, and unresolved feed
   limitations alongside performance.
5. Repair the standalone Tier 1 baseline smoke before treating its output as
   evidence. The synthetic smoke had passed with zero positions for every arm:
   raw OHLCV defaults omitted the canonical swing anchors that `TradingEnv`
   requires to construct structural stops. `run_baseline_eval.py` now adds
   missing anchors from the causal M1 structure-level builder, records the
   generated columns and comparison scope, and the synthetic smoke requires
   buy-and-hold to open at least one position while always-flat remains empty.
   The reusable `score_rule_baselines.py` runner now uses that same shared
   helper instead of an unrelated rolling five-bar approximation. The matched
   setup evaluator now accepts a deterministic structure-priority Tier 1 rule
   using the exact eligible setup mask and environment action schema; it
   records the rule's family/timeframe precedence and permitted inputs without
   inventing checkpoint provenance. Its synthetic unit/integration suite
   passed (21 tests). The matched evaluator now also calculates and stores
   per-policy moving-block confidence intervals for bar-return Sharpe/Sortino/
   drawdown and completed-trade win rate; immutable bundles hash the new
   `confidence_intervals.json` artifact under the v2 result-manifest schema.
   The immutable bundle also records paired treatment-minus-random-control
   moving-block intervals for mean bar return, Sharpe, Sortino, and maximum
   drawdown using exact timestamp-matched equity paths and shared resampling
   indices in the versioned v2 record. It marks the estimate `not_estimable`
   with a reason when fewer than two paired returns exist, instead of failing
   bundle generation or emitting a degenerate interval. These intervals are
   conditional on one evaluation path and the
   action seeds; they do not estimate between-seed variation, pair trade win
   rates, or establish equal realized-risk distributions. Synthetic helper and
   bundle integration coverage passed with the 1,157-test matched evaluation,
   risk, simulation, and trading validation batch. This
   makes one structure-rule comparison and its within-path uncertainty
   executable, but does not
   complete the EMA/RSI/session-momentum baseline set or establish market
   results. No market-data baseline result was generated; broader Tier 1 risk,
   action, cost, and period gates remain open.
   The `--include-structure-priority` flag is explicitly opt-in: the focused
   CLI contract suite passes 6/6, and the runner/test pass touched-path Ruff
   check and format validation. Its source/output hashes are recorded in
   `evidence/research/matched_setup_baseline_cli/`. No market comparison was
   run; C/D/E still gate that work.
   The shared baseline evaluator exposes opt-in `macd_histogram` and
   `rsi_mean_reversion` arms; its prior default arm list is unchanged. A caller
   and action-contract audit found that these signal series were being sent
   through a continuous action interface where zero means hold, so RSI's
   documented neutral-band exit was not executed. `rsi_mean_reversion` now
   retains its long/short state until RSI enters 45–55, then returns flat. The
   reusable `evaluation/rollout/baseline_signal_actions.py` adapter converts
   these target transitions into the `discrete-trading-v1` schema, emits an
   explicit exit, and delays a reversal entry until the following bar. The
   evaluator uses high-risk/low-target actions with an effective 1% risk and
   1.0 R target, matching its former full-intensity continuous settings, and
   records the action mode and risk ranges in its report. The standalone
   training baseline already uses discrete zero-as-exit semantics, so it now
   receives the stateful RSI target correctly. Focused signal, evaluator,
   training-runner, and shared action/exit parity validation passes 24 test
   cases; touched-path Ruff check and format pass on seven Python files. These
   are synthetic/contract checks only. No market-data baseline was run, and
   the optional arms remain non-matched to the RL campaign action schema.
   A caller audit found that `TradingEnv` skips non-eligible NY-session rows
   while several baseline strategies advanced their signal cursor once per
   action. `BaseStrategy.act_at()` now selects a precomputed signal by the
   environment's absolute bar index; the standalone baseline evaluator, rule
   scorer, LSTM baseline, and rule-control analysis use that index. The rule
   scorer's unlevered reference also starts at the first eligible decision
   bar. Scoped Ruff and Mypy passed, and the combined CPU validation batch
   completed 777 tests in Slurm job `21362557` (including the overnight-gap
   regression and baseline evaluator/LSTM script smokes). This repairs
   source-to-bar alignment only; it is not market-data
   evidence and leaves the listed economic gates open.
   `MultiLevelBreakoutStrategy` now rejects non-finite or out-of-contract
   sizing, ATR, and volume-threshold parameters before precomputing actions, so
   an invalid rule configuration cannot emit an action outside the continuous
   strategy contract. The classical baseline module passes 21 focused tests,
   scoped Ruff, and scoped Mypy. This is configuration validation only; the
   Tier 1 market comparison remains gated.
6. Stage G source diagnosis confirms that the selected A4A/A4B policies retain
   the same continuous action schema; the observation-only A4B toggle adds
   state features but no dynamic ARMED-state action mask. An intensity-qualified
   request in `FLAT` or `CANDIDATE` is deliberately counted as
   `entry_state_not_armed` and forced to no-entry, matching the measured 88.3%
   / 91.1% funnel shares. A focused FSM test now verifies those state-specific
   rejections and that the same action can trigger after ARMED. This rules out
   an action-mask change from the visibility toggle as the mechanism; it does
   not explain historical policy choices or their economic effect. The paired
   source-ledger reports reconcile 987/987 A4A and 825/825 A4B positions to
   fill events and aggregate PnL. A separate current-TickBook analysis now
   derives timestamp-bounded liquidation-side MFE/MAE for both training arms;
   median MFE is 0.569R/0.552R and median MAE is 0.815R/0.774R. The arm cohorts
   differ, endpoint bounds vary for 2/1 trades, and quote-side carry and source
  chronology remain limitations. A new hash-linked description of those
  existing rows groups results by recorded exit reason: structural stops have
  median realized net R −1.000/−1.000 and lower-bound median MFE 0.396R/0.333R;
  20.7%/19.4% reached 1R MFE. Session-end exits have median realized net R
  0.058/0.037 despite median MFE 0.377R/0.347R. This is descriptive path
  evidence, not a feasible-exit replay: MFE excludes costs, gross/cost R are
  absent from this cohort source, the arms are distinct cohorts, and quote
  chronology remains uncertain. See
  `evidence/research/failure_mechanisms/exit_reason_cohorts.json`. The prior
  run still lacks per-decision action/state joins. Current rollout rows are
  implemented to persist the eligible IDs, chosen action, source-event
  identity, FSM outcome, resulting trade-event index range, and compact
  selected/NO_TRADE/top-eligible probabilities for future diagnosis; they
  cannot backfill the old run. Four focused probability-summary helper cases
  pass. A synthetic policy-to-rollout-to-CSV integration now verifies that the
  selected action, selected probability, NO_TRADE probability, and highest
  eligible trade probability/ID survive `trade_setup_decisions.csv` export.
  This does not reconstruct the old policy run or establish candidate-event
  cardinality. During that check, `save_run()` exposed ambiguous DataFrame
  truth-value checks for rollout `payout_events`/`cycle_events`; the writer now
  keeps list compatibility and lets DataFrame ledgers follow their typed export
  path. The integration plus repeated-payout export test passes 6/6; scoped
  Ruff and Mypy pass. A factorized or conditional action
  interface is a new experiment and remains gated on D/E.

P8 independent review was waived for the prior deliverable; no independent
review is claimed. Reopen it only if requested or needed to support a claim.

## Evidence and execution safeguards

Historical source paths and checksums are preserved in the
`evidence/research/historical_source_provenance/README.md` packet.
The historical 18-variant screen's archived report records that its raw
attempt-3 report directories and matching checkpoints were absent from the
then-current outputs scan. A fresh path inventory now records that the former
`/scratch/work/nguyenl37/Aalto_MS_Thesis` checkout and the known main-plan,
source, and recovery directories are absent at their recorded paths. The
retained CPU-buffer probe has a source snapshot and campaign summary but no
trained checkpoint. A separate bounded search of the frozen selected seed-50
pair hashed 50 ZIPs with matching variant-and-seed paths (25 per arm;
1,663,296,245 bytes) against the two frozen digests. Neither matched, and both
recorded source-run directories are absent from the preserved archive. This is
not a whole-archive or scratch-wide absence claim. The older report-pack scan
remains scoped to its recorded outputs tree. See the recoverability packet at
`evidence/research/historical_variant_screen_recoverability/README.md`.
Run directories remain under `outputs/experiment_runs/`; they are immutable
evidence, not an alternate task queue. The selected-pair monthly attribution
is documented in the [entry and exit attribution topic](../research/entry_and_exit_attribution.md)
with its [semantic evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_and_exit_attribution/README.md).
Historical training-dynamics records remain in the archive and are not the
current research index.

As of 2026-11-01, the local scratch campaign
`outputs/gpu_campaigns/rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1/`
was found with its source snapshot, resolved configs, per-arm provenance,
final checkpoints, and train/test trade ledgers. Its campaign fingerprint
matches the paired-decomposition evidence. The recorded training outcomes are
987 A4A positions at −2.154% and 825 A4B positions at −10.056%; both failed
the strict zero-breach survival gate, and report-period replays remain
exposed, report-only results. Both training evaluations reached `data_end`.
A4A's sole recorded breach was the legacy gross-loss `daily_loss` counter;
A4B recorded that event and a later `max_drawdown`. The March events do not
establish net daily-equity breaches. The stored `fail_time` is each arm's first
breach, not its episode end. A4A's aggregate ledger ends above $90,000, but
that does not erase its historical configured-gate failure. The semantics and
close-level reconciliation are documented in the release snapshot's P6 risk
gate trace. This scratch recovery does not change the tracked-packet
R2 registry grade: 10/10 manifest-listed per-arm artifact hashes match, and
all 39 manifest-listed input paths are present. The selected campaign input
audit verified 8,162,529,858 bytes against its SHA-256 manifest. The separate
full local-data inventory hashes 140 declared paths resolving to 64 distinct
files (16,325,449,095 unique bytes); all 38 overlapping campaign data files
match their observed hashes. The machine-readable checksum report is in
`evidence/research/releases/negative-evidence-readiness/RAW_DATA_SHA256_MANIFEST.json`.
The full flag/quote-side cross-tab (`tick_quote_side_flag_cross_tab.json`)
accounts for every row in the four local tick files: flags 2/4 coincide with
ASK/BID missing respectively, while flag 6 has both sides present. This is a
measured pattern in the current files, not an authoritative flag definition.
Job 21343231 completed on csl23 (2 CPUs, 8 GB requested, 13:58); all 39
campaign input hashes matched. Local timestamp/session interpretation and
feed semantics remain documented limitations. Per the user's direction, no
external feed, license, or authoritative calendar lookup is part of this plan.
The current configured native-versus-derived timeframe parity report is
complete, with spread differences and calendar limitations preserved.
Per the user's scope, provider/license records were not investigated; no raw
data is bundled and no rights claim is made. No checkpoint replay was run. The
scan found missing/non-finite required bid/ask values in all four tick files,
adjacent timestamp ties, and 23 training M1 minutes without ticks for each
instrument. Minute overlap does not establish within-minute quote availability
or schedule correctness. Detailed scan job 21340127 classified
329,471 ties as 328,918 changed-quote pairs, 553 pairs with a missing quote,
and zero identical-quote pairs. It counted 371,390 rows with one required
bid/ask side missing or non-finite, and none with both sides missing. No
timestamp parse failures, adjacent reversals, nonpositive or inverted quotes,
or invalid OHLC rows were observed. This does not determine within-tie
chronology or the authoritative feed clock/session calendar. A durable
release manifest must preserve this external-artifact boundary. The separate 20M-step
`p6_entry_fsm_viability_seed50_train2025_20261021_scratch1` campaign has a
different fingerprint and only seven training positions per arm; do not
conflate it with the selected pair or resume it.

A current-byte refresh is now packaged at
`evidence/research/market_data_quality/README.md`.
It rechecked all 39 campaign inputs (8,162,529,858 bytes); all paths were
present and all manifest hashes matched. The scan observed 172,290,383 tick
rows, 2,215,084 bar rows, and the same 371,390 one-sided missing/non-finite
quote rows and 329,471 adjacent timestamp ties recorded above. The updated
configured-timeframe report covers 32 series: 30 native series match M1-derived
timestamps and OHLCV exactly (532,350 training-role and 423,018 report-role
common rows), while US100 D1 is derived from M1 in both roles. The packet adds
a monthly quote-side table and a provenance-linked figure. The plot uses one
shared y-axis label to keep all four panels readable. These results do not
resolve local timestamp ties, quote carry-forward semantics, source-clock or
calendar authority, or provider rights. Optional `LAST` and `VOLUME` fields
are empty throughout the tick exports; the available flag column accounts for
all rows, with no flag semantics inferred. Under the configured close schedule,
first-M1 availability is exact at close for 527,449 training-role rows and
419,706 report-role rows, later for 5,145 and 3,502, and absent for 16 rows in
each role. The regenerated report also compares observed M1 rows with nominal
minute slots inside each HTF interval, clipped by configured session close:
19,507 of 955,834 series-bars were partial and none had zero M1 rows. All 932
D1 bars were partial relative to a 1,440-minute grid; this is descriptive and
does not classify market closures as data loss. Nonempty partial bins remain
available at their calculated close, not at the last contributing M1 row; a
sparse-M1 integration fixture verifies no value appears before the close and
that the first observed M1 row after close receives only the prior interval's
aggregate. This verifies code and configured local-data boundaries, not feed
publication time or calendar authority. The older release-readiness snapshot
is retained unchanged because its manifest and downstream evidence link to it.

A reusable pipeline-denominator register now records the available marginal
counts from local source rows through quote rows, the selected training-only
feature/candidate census, and the archived A4A/A4B training/report partitions.
The current scan covers 39 manifested inputs (8,162,529,858 bytes), with
2,215,084 bar rows and 172,290,383 tick rows; 171,918,993 tick rows have finite
two-sided quotes, while 371,390 lack at least one required side. The selected
census reports 351,432 primary-symbol M1 feature rows and 488,008 active
candidate-row occurrences across 24 supported tuples; 84 catalog tuples are
unsupported by that profile and zero active rows lack required source time.
The four policy partitions reconcile diagnostics to fill and position CSV row
counts, and all recorded positions are completed. These are separate evidence
groups and do not form conversion rates: historical action-by-session counts,
order attempts/acceptances, and candidate-to-action links are not recorded in
the scanned run artifacts. Entry-FSM trigger requests are not order counts.
The report-period partitions remain exposed exploratory evidence. See the
pipeline denominator packet at
`evidence/research/pipeline_denominators/README.md` for per-partition counts,
explicit unavailable states, input identities, and checksums. The broad Stage C flow-denominator gate remains open until missing
links are instrumented for future runs or otherwise recovered with sufficient
evidence; missing records are not counted as zero.

The current production TickBook path was also run over all four tick inputs,
with each file hash checked before and after streaming. Of 172,290,383 raw rows,
171,918,993 already had a valid raw two-sided quote; 371,390 rows became valid
after independent side carry-forward (136,547 bid-side and 234,843 ask-side
carry counts). All rows were retained and none were dropped after carry. The
counts reconcile by file and the audit uses no session-hour filter. This is a
measured current transform, not proof both quote sides were simultaneously
available or ordered within tied timestamps. See
`evidence/research/market_data_quality/tickbook_carry_forward_audit.json`.

The same packet now includes a schema dictionary with synthetic examples, a
138,992-row day/week/month quality table flattened from the machine report, a
32-series configured-timeframe coverage table, and a nominal-grid occupancy
figure. The figure is explicitly descriptive: configured-close clipping and
partial bars do not classify expected closures as data loss. These exports are
reproducible from the saved current-byte and timeframe reports without another
8 GB raw-data scan. The TickBook carry-forward audit closes the local
raw-versus-transformed quote-row accounting for the four selected input files;
historical order-attempt and candidate/action links remain unavailable, and
authoritative feed-clock/calendar claims remain outside local evidence.

The current and selected-campaign tick-builder source blocks independently
carry bid and ask sides across missing values before retaining valid pairs.
Thus an executable row may combine a new side with a value from an earlier
source row; this does not establish simultaneous quote availability. The
current tick builder file hash differs from the selected campaign's source
hash, although this preprocessing block is identical. Detailed source and
quote-quality evidence is in
`evidence/research/releases/negative-evidence-readiness/DATA_PROVENANCE_AND_ACCESS.md`.

The current-tree function/test navigation map was regenerated from this
checkout with the AST-based static inventory tool. It covers 613 production
Python files and 3,567 function, async-function, and class definitions; 965
definitions have at least one statically visible direct test reference. The
generator now follows explicit symbol re-exports through package `__init__.py`
files and unambiguous local variables initialized by production class
constructors. It now resolves the public `simulation.backtest.run_backtest`
import to nine test files and maps key instance methods including
`TradingEnv.step`, `TickBook.quote_at`, and `Broker.open_position` to their
test files. The map is explicitly `static_reference_only`: it does not
establish calls,
assertion quality, runtime branch coverage, or behavior correctness. Generated
package views now include per-directory reference counts, 934 P0 definitions
without a direct static test reference (421 of 1,355 P0 definitions have a
static reference), and current cross-package production reference edges.
These are review queues and the 333 cross-package edges are static edges, not
  runtime coverage or a call graph. The broader Stage N audit still needs
  prioritized source/caller review beyond the scoped critical-symbol review. The selected review
is recorded in
`evidence/research/function_test_coverage/critical_symbol_review.md`; it
inspects source and test bodies without claiming runtime coverage. See the
same packet for README, source map, package views, generator, and review hashes
  in `SHA256SUMS`. The manifest had stale values after this refresh; it is now
  regenerated and all seven listed artifacts verify. The current map test
  passes 2/2, and the session-level contract test passes 17/17 in parallel on
  the existing GH200 allocation.

## Release readiness snapshot

The current release snapshot and final readiness report are recorded under
`evidence/research/releases/negative-evidence-readiness/`. The
[`RELEASE_MANIFEST.json`](../../evidence/research/releases/negative-evidence-readiness/RELEASE_MANIFEST.json)
verification record is the authority for the latest full-tree Ruff and Mypy
results, scoped test totals, strict Sphinx output manifest, and release hashes;
each result applies to the exact source state and inputs recorded there.
Readiness remains **blocked** on scientific validity and thesis/release
deliverables, independent of the software gate status. Current documentation,
evidence sufficiency, and hash checks are required parts of that gate.

The selected local-data inventory verifies 140 paths resolving to 64 files;
all 38 selected-pair overlaps match their recorded hashes. The full quality
profile, configured-bar comparison, and 3,698-event fill-to-tick alignment are
bounded local evidence. A saved-report review confirms that no no-carry or
next-quote price/economic sensitivity is identified because quote prices and
within-timestamp order are absent. A source review describes the signal
semantics for the 24 flags enabled by the registered overlay. Their feature
producers now retain family-specific source times, and a versioned resolver
builds IDs only when those times are present and unambiguous. Synthetic tests
cover stable/repeated identities, explicit missing/conflicting states, the
unchanged 109-choice mask, and exclusion of absolute times from model inputs.
All 488,008 active candidate rows in the selected profile resolve to 109,391
candidate-scoped source-time IDs, with no missing required source times; see
`evidence/research/trade_setup_opportunity_census/` and the identity-linked
`evidence/research/feature_causality/feature_causality_matrix.csv`. Job
21349879 completed on csl23 in 9:21 (4 CPUs, 48 GB requested; 11.6 GB
observed maximum RSS). The refreshed lifecycle census command completed in
9:54 under the existing 4-CPU/48-GB job 21350383. That interactive allocation
later reached its time limit after the work was complete; its idle tmux wrapper
was removed after Slurm reported the job terminal. No successor is pending.
The 84 candidates disabled by this overlay have no active rows or measured
identity counts; their producer lifecycles have been source-reviewed. The
current census packet records `trade-setup-event-identity-v3`, including
family-specific formation/confirmation timestamps and the selected zone origin
where applicable. Its output hashes, recorded source hashes, source commit,
and local input-manifest hash verify against the current checkout. The 488,008
active rows and 109,391 candidate-scoped IDs are current for that selected
configuration and input manifest. The review found that overlapping FVG/IFVG
events can collapse into scalar/latest-zone state, order blocks retain one
active zone per direction, and scalar identities still do not prove logical
event cardinality. Current rollout
records include selected candidate ID and source-event ID/status/times under
`decision_id`; synthetic tests establish that local correlation only. A
read-only search of preserved campaign outputs found no historical
`trade_setup_decisions.csv` or equivalent per-decision candidate-to-order
trace, so the new fields do not explain the prior policy's actions. Logical
event cardinality, feed publication timing, and configurations outside this
profile remain open; this work does not close Stage D.
The `evidence/research/candidate_event_cardinality/` register now reconciles
the current profile's existing producer, scalar-projection, and candidate-ID
ledgers without adding those different units into a purported event total. It
records 24 supported and 84 unsupported candidate tuples, 488,008 active
candidate-row occurrences, 109,391 candidate-scoped source-time IDs, 16,692
configured PO3 setup sequences, 59,057 latest-leg projections, and 72,561 M1
per-zone IFVG confirmations against 56,349 scalar pulses. Packet hashes and
documented count reconciliations verify. This bounds the reportable counts for
the selected local profile; a ground-truth logical-event count and historical
candidate-to-action trace remain unavailable, so the full Stage D gate remains
open.
New direct order-block fixtures exercise later-row retest confirmation,
same-direction zone replacement, and M5 close-boundary visibility through the
feature pipeline. The MTF PO3 path now builds post-IFVG readiness on each source
timeframe before close-time alignment; synthetic M5 tests cover the next
completed-bar boundary and prefix invariance. These tests do not establish all
MTF configurations or external feed publication timing.
An opt-in per-zone order-block retest ledger now preserves older still-active
zone confirmations alongside the unchanged latest-zone scalar output; the
regular feature path skips the diagnostic scan. A reusable local-training
analysis command reconciles selected events and summarizes collisions across
configured timeframes. Its overlap, scalar-projection, and prefix checks pass
(8 focused tests). Slurm job 21357191 on skl4 exited after 44 seconds because
the collision summary incorrectly required exactly one scalar-selected event;
older-zone groups with no latest-zone pulse are valid and now have regression
coverage. The step and logs are preserved as a launch-control deviation. No
local-data packet was produced. The selected research config disables
order-block features, so this detector-only census is not required to establish
current policy eligibility; do not rerun it as another short step. The reusable
command remains available for a future naturally substantive audit. None of
this establishes policy choices, feed publication timing, or economic value.

Execution/risk parity, matched economic baselines, independent-seed robustness,
and an untouched confirmatory period remain unresolved. The 2026 interval stays
exposed/report-only. At the user's direction, use current local data only and
do not seek external provider/license records or an authoritative schedule; no
raw data or rights claim is included. No training, checkpoint replay, commit,
push, or release tag was made. Preserve the negative P6 result and do not
resume or duplicate the failed campaign.

The reusable `scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py`
report now records explicit lifecycle mismatch counts and a fail-closed overall
integrity status for fill-count mismatches, completed positions without one
open and a close, close-fill versus position net-PnL mismatches, orphan fill
position IDs, decision/submission/fill ordering violations, aggregate PnL, and
account-equity reconciliation, including the valid empty no-trade ledger.
It now checks payout reset type, positive amount versus balance-before-reset
and operating balance, sequential cycle/time order, payout totals versus
evaluation diagnostics, and final total-economic-value curve identity. The
account equation includes recorded withdrawals:
initial balance + completed-position PnL = final account equity + payouts.
Cycle success/failure events now reconcile against payout rows, diagnostic
outcome counters, and the terminal cycle count. Terminal failure events also
match the recorded account breach by time, reason, and equity. The verifier
accepts either writer's established payout ledger name (`payouts.csv` or
`payout_events.csv`) and fails closed if both appear; empty optional cycle
ledgers are supported. Missing source fields remain incomplete; numeric or
event mismatches fail closed. The synthetic verifier suite passes (16 tests),
plus the report-writer export test (17 combined). Scoped Ruff format/check and
Mypy pass through the environment's Python module entry point. The console
Mypy launcher itself has a stale interpreter path in this checkout. No
historical payout-cycle report was regenerated because the preserved campaign
has no payout run. The existing `selected_policy_trade_lifecycle` packet now
also contains descriptive reconciliations of the saved A4A/A4B report-period
ledgers. Each arm has 203/203 positions linked to fills, zero unlinked fill
position IDs, all 203 close-fill PnL values reconciled, and account equity and
reported PnL differences below $0.000000001. Both report manifests mark the
associated holdout as previously inspected; these summaries are not untouched
confirmation or fresh evaluations. Broader Stage E acceptance remains open.

The model observation/action artifact scanner now recognizes the evaluation
writer's canonical `trade_setup_decisions.csv` and
`trade_setup_candidate_id` field. A regression failed before this fix and
passes after it. The selected historical campaign scan found no per-decision
setup or candidate price-geometry trace in its 24 recognized artifacts. A
broader read-only inventory then scanned 276 recognized artifacts under
`outputs`, `baseline`, `evidence/research`, and
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System`; it also
found no qualifying trace. See
[`decision_trace_availability_inventory.json`](../../evidence/research/model_observation_and_action_semantics/decision_trace_availability_inventory.json)
and the evidence packet README for scanner scope and limits. These are scoped
absence findings, not proof that no trace exists elsewhere. The broad scan was
regenerated with directory-symlink traversal disabled after archived checkout
mirrors produced repeated, non-resolving paths. It still contains 276 unique
artifacts, all 276 recorded paths resolve, and no qualifying trace is found
within the four physical roots. Artifacts reachable only through directory
symlinks are outside this scan. The scanner fix
improves future evidence capture and requires populated decision/setup IDs and
same-row entry, stop, target, and TTL values for geometry traces. It does not
recover historical decisions or establish price-geometry conditioning.

The configured `MTFReasoningEncoder` passes a synthetic history-sensitivity
check: an earlier valid M5 row changes its output while all timeframe latest
rows remain fixed. This verifies use of historical path input only. It does
not establish useful predictive information or economic value; candidate
price-geometry conditioning and its sensitivity test remain open.
The conditioned actor's setup-ID perturbation, stored-action log-probability,
PPO update, and checkpoint-roundtrip contracts also pass their focused tests.
They do not test proposed-price geometry or establish economic value.

The current `trade_setup_mtf_reasoning_2m` environment contract is now
instantiated from the configured local training window by
`scripts/research/analysis/models/build_configured_observation_action_contract.py`.
The paired Variant C/D reports record 351,432 training bars, a `[60, 282]` M1
stream, M3–D1 stream windows and masks, a `[109]` setup mask, and the same
six-coordinate `trade_setup_overlay` action schema. Their data, input hashes,
observation schemas, and action schemas compare equal. Variant D declares a
32-dimensional setup embedding and 128-unit conditioned execution head; the
setup selector remains market-latent-only. Neither policy receives candidate
entry/stop/target/TTL geometry. The packets hash the resolved configs, local
data, feature/tick records, and relevant sources. They use no report-period
rows, policy actions, environment steps, checkpoints, or economic results.
This closes the paired current-config shape inventory only; it does not prove
historical-run parity or price-geometry conditioning.

Trade-setup diagnostics now include a `decision_open_linkage` integrity
summary. It joins new per-step decision records to opening fills by exact
`decision_id`, counts missing, duplicate, unknown, or multiply opened IDs, and
checks the selected candidate ID against each linked open. Its focused
regression passes. This instruments future evaluation evidence; historical
per-decision traces remain unavailable, so the old policy's proposal-to-open
linkage is still unresolved.

Preserve existing jobs, allocations, checkpoints, fingerprints, and evidence.
Follow [Triton operations](triton.md) before any compute request. Do not start
an expensive training run for a documentation or maintenance change.
