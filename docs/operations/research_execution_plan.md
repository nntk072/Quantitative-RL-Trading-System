# Active research execution plan

This page is the operational queue for the current research program. It records
the last evidence-gate disposition and the conditions for any successor work;
it is not a general architecture guide or a personal academic-submission plan.

## Current gate disposition

### Feature missingness follow-up — implementation only

The profile-wide producer crosswalk found that PD context distance features
were zero-filled even when an active session range or positive ATR was
unavailable. `build_pd_context_features` now preserves those active-but-unknown
distances as nonfinite, while known-inactive ranges remain zero; the survival
policy's versioned finite-value channels can then distinguish the states. A
follow-up adds `htf_day_bias_available`, preserving the neutral zero bias while
exposing whether its selected composite range exists. The feature cache
identity is now `v43-heldout-fit-state` after held-out rows were corrected to use
the last preceding training fit. Focused regressions cover missing
ATR, missing prior-session ranges, and neutral-versus-unavailable bias; they
are included in the consolidated suite but have not run. The v40 all-profile
prefix and validity packets are historical for these source changes. Refresh
the feature matrix, full-profile missingness audit, and prefix audit before
closing Stage D or using these features in a result. This bias feature is
available only to profiles enabling `features.include_pd_context`; the current
survival overlay does not enable that family, so it is not evidence about the
survival checkpoint's inputs.

The related standard-deviation retracement path was source-checked separately:
its level-distance columns use the confirmed-leg validity state to preserve
unknowns as nonfinite, and `standard_deviation_leg_valid` plus direction are
model-facing eligibility inputs. Existing synthetic expiry/eligibility tests
cover this contract; they remain in the consolidated suite. This resolves that
specific retracement-validity concern. A source check of the separate MTF
structural swing-distance fields found that accepted swing levels are carried
forward, so unavailable values remain nonfinite until a level exists; the
existing per-feature finite-value channels preserve that distinction from a
valid zero. The prior missingness packet reports leading-edge-only missingness
for these fields, but it is historical after the v42 cache change and must be
refreshed. The crosswalk resolver also mislabeled generic MTF swing distances,
primary swing distances, swing levels, and swing ages as retracement outputs;
its mappings now distinguish `build_features`, `swing_features`,
`append_structure_features`, and `build_swing_retracement_features`. A producer-
mapping regression is selected for the consolidated suite. The report now also
distinguishes the temporal `seq_mask` from optional per-feature finite-value
channels instead of describing all sequence validity as row-only. The checked-
in generated crosswalk is preserved as historical until the v42 profile packet
is regenerated. This source disposition does not close Stage D.

The consolidated implementation gate selects the complete feature unit-test
directory and the observation-validity crosswalk regression. A duplicate
feature-directory argument and a redundant child test path were removed, so
the final batch will not execute those feature tests twice. Tests remain
deferred until implementation is complete.

### Canonical metric input validation — implementation only

`evaluation.metrics.performance.compute_metrics` now rejects boolean or
non-numeric equity values, boolean/nonpositive initial balances, non-integer
annualization periods, and nonfinite or malformed position PnL inputs. Valid
numeric runs retain the existing metric definitions; this does not close the
Stage O audit of daily returns, time-to-ruin, cost decomposition, historical
schemas, or figure QA. Regression cases are included in the consolidated
quality gate and remain unrun. The final training artifact writer now uses the
same availability-aware payload as run summaries: undefined trade metrics are
JSON `null` with a reason, and the Markdown summary renders them as `N/A`
instead of `0` or `inf`. The writer regression is selected for the consolidated
suite and remains unrun. Metric schema v3 now derives complete-session daily
return summaries and right-censored time-to-ruin from complete account-state
traces, recording payout-attribution ambiguity or missing trace linkage as
unavailable. Payouts executed within a session remain attributable even when
the account resets its session-start anchor afterward; the metric retains the
session's first anchor and includes cumulative payouts in ending economic
value. A payout first seen only at a session boundary remains unavailable.
The trained-policy, walk-forward, baseline, reanalysis, matched-
setup, and generic episode metric paths pass their retained traces where
available. Zero-session breach rate is now unavailable instead of a fabricated
zero. The numerical-report verifier reads the exported account trace for v3 and
retains v2's original field set and zero-denominator convention for historical
reports. These regressions are selected for the consolidated suite and remain
unrun; v3 summaries have not yet been regenerated from evaluation runs.

Metric schema v4 now defines breach rate as the fraction of distinct breached
sessions, rather than dividing a potentially multi-event breach count by the
session count. It reports breach-event count separately, derives the rate
numerator from event `session_id` values or the explicit session count, and
emits availability reasons when the ledger, distinction, or denominator is
missing or inconsistent. The report verifier continues to accept v2/v3 reports
under their historical field sets; new reports use v4. Focused tests are
selected in the consolidated suite and remain unrun.

The cost-ledger source audit found that `trade_fill_cashflow.v1` independently
reconciles gross PnL at executed fill prices, entry/exit commission, and net
closed-fill PnL. New environment and event-backtest fills now also emit
`fill_cost_provenance.v1`: the pre-adjustment quote, broker-facing quote,
slippage amount, and whether the adverse adjustment changed only the traded
side or shifted a protective-level quote. Account-state reconciliation checks
that transformation, and artifact diagnostics retain its coverage status. The
run writer now creates `cost_decomposition.json` from complete closed positions;
it reconciles midpoint-reference PnL to spread, slippage, commission, and net
PnL, validates fill-level gross-price and commission arithmetic, and records
missing historical provenance as unavailable. The numerical
report verifier independently recomputes that output from exported `trades.csv`.
When a report declares a complete account-state trace, it also recomputes
`account_state_reconciliation.json` from the exported trace, trade events, and
breach rows, and rejects a missing or inconsistent reconciliation artifact.
This does not retroactively recover a historical spread/slippage ledger: old
results lack the quote provenance. Stage O still requires the consolidated
regressions to run, live-result regeneration, full fill-path provenance
coverage confirmation, and a bounded historical disposition.

## Bounded survival runtime correctness smoke — 2026-11-10

The purpose-named runtime smoke passed on source
`11aebfca7a694430be1bc149112f272e4ee108ba`. It exercised the configured
tick-backed environment, six-coordinate setup action, bounded PPO update,
checkpoint round trip, evaluator replay, 60 legal masked actions, and terminal
survival reward using synthetic data. Peak host RSS was 3,228,824 KiB and
elapsed time was 30.65 seconds. This is implementation correctness evidence
only; it does not authorize scientific training or selection. The promotion
review records no-go because the available readiness manifest is tied to an
older source and denies authorization. See
[`survival_runtime_correctness_smoke_20261110.md`](../research/survival_runtime_correctness_smoke_20261110.md)
for the exact contracts, results, and artifact hashes.

The research TODO tracker now labels its list as dependency-ready. Passing
those hard dependencies does not evaluate conditional gates, scientific
authorization, resource availability, or permission to execute an experiment.
The survival command builder and current-source authorization record remain
the execution controls.

## Survival-first model selection

Per the user's direction on 2026-11-06, survival is the first feasibility gate,
before any portfolio-performance optimization. Training/reward design must
also represent a hard account breach as terminal infeasibility that accumulated
profit cannot offset; a numeric penalty alone is not a replacement for that
constraint. Survival is a policy objective, not a rule applied only during
evaluation: the policy must observe its remaining daily-loss and maximum-loss
budgets while training under those same account rules. The 5% daily and 10%
static maximum-loss limits stay active during training, so the learner must
choose behavior that avoids breaching them. Final evaluation measures whether
the learned policy survives; it cannot substitute for survival training. The
simulator now initializes a dedicated `SurvivalReward` instead of an
unused DSR/composite reward in this mode. Intermediate transitions receive
zero, a hard account breach receives terminal `-1`, and a complete breach-free
split receives terminal `+1`; configured reward-shaping flags cannot silently
replace this path objective. New configurations now
default to `account-state-v2`; qualification manifests must match the full
ordered schema expected from the effective config, including optional
entry-state visibility. Historical checkpoints retain their recorded
observation schema. Existing `dsr`, `pnl`, and other reward modes still use their
portfolio reward and a fixed `-10` breach term; that signal does not prove
survival-first optimization. An opt-in `survival` mode is now implemented in
source: it assigns no intermediate portfolio reward, emits `+1` only for a
complete breach-free split and `-1` for a hard-breached account, and requires
full-split training with undiscounted returns. The cross-seed phase barrier is
now implemented: six or more unique seeds must each survive the full train
split and every one of at least five purged walk-forward folds before a passing
gate is written. Qualification now requires
`env.strict_research_eligibility: true`, so missing NY-session labels cannot
fall back to treating all bars as tradable. Portfolio admission revalidates the
same requirement against both the current request and the saved qualification
config, so an older permissive gate cannot authorize optimization. Because
phase identity deliberately excludes `reward_mode` to compare qualification
with later portfolio training, the qualification verifier now separately
requires the hash-verified saved effective config itself to specify
`reward_mode: survival`; a protocol label alone cannot establish that survival
was optimized during training. Qualification also now fails closed unless the
training config uses the selected $100,000 initial balance, static maximum-loss
mode, 5% daily and 10% maximum-loss limits, 1% risk fraction with the $900
per-trade sizing cap, no repeated-payout lifecycle, and all configured
timeframes (`M1`, `M3`, `M5`, `M10`, `M15`, `M30`, `H1`, `H4`, `D1`) for input
bars, higher-timeframe features, generated setup-eligibility candidates, and
structural targets. The gate requires `features.entry_ideas.enabled: true`;
listing all timeframes while leaving the feature family disabled no longer
passes. These are checked both before training and against the hash-verified
saved config. The reusable overlay is `config/research/survival_qualification.yaml`;
it pins `reward_mode: survival`, undiscounted PPO returns, the account and
timeframe contract, and versioned feature-validity channels so the policy can
distinguish nonfinite values at the observation boundary from finite zeros while
learning; this does not repair upstream finite-zero imputation. Because
`reachable_r` is explicitly zero-filled by its producer, the overlay also
requires its separate `reachable_r_valid` sequence feature, and the gate checks
that it is present in the saved schema. The sequence-schema round-trip now
preserves the channel layout in run manifests; qualification rejects a saved
manifest that drops or mutates it. The run-manifest gate also requires all 108
setup/timeframe/direction eligibility features in the policy sequence schema,
so config flags alone cannot assert that the learner received those inputs.
Architecture, seed count, and walk-forward count remain explicit. Enabling
setup eligibility is prospective: the existing
candidate census and profile-wide packets describe older resolved configurations
and do not establish which setups are present in the survival overlay. Refresh
the feature cache, candidate census, and relevant causality/availability
evidence for the resolved survival config before qualification training. The
feature-pipeline regression now builds all 108 setup flags from the survival
overlay and checks their observation inclusion; it remains queued for the
consolidated suite. The load-and-validate and schema regressions are included
in the consolidated implementation suite and remain unrun. Encoder construction
derives sequence widths from the effective observation space; four standard
single-stream encoders now have a widened-input regression selected in that
suite, while the earlier four-encoder MTF inference check is bounded evidence
for MTF only. In the qualification
phase, checkpoint callbacks no longer rank short-prefix checkpoints by equity
or stop training for inactivity. Gate admission rejects configs that enable
activity/equity aborts, and the runtime disables those callbacks defensively;
non-finite training still aborts. This keeps a breach-free no-trade policy
eligible for the hard survival gate without diverging from the saved config. A hard breach terminates a
survival-objective trajectory with the infeasible outcome, independent of
subsequent market bars.
Per-seed evaluation summaries now label the survival phase and mark a complete,
fully trained, breach-free split admissible even when return is negative,
activity is zero, or an auxiliary peak-drawdown fit misses; these remain
diagnostics. They now call this a train-split survival result, not a complete
survival qualification: the latter requires the separate cross-seed and
walk-forward gate in `survival_phase_gate.json`. An interrupted learner is not
train-split admissible even if its last replay survived. Regressions for both
completed/interrupted status and the scope label are included in the
consolidated suite and unrun. The evaluation summary schema is versioned to 3
for its explicit phase, scope, and admissibility fields.
Run-level finalization follows the same order: survival status is computed from
the full-split outcome, completion of the configured training schedule, and no
breach sessions. Profit, activity, and the older equity/policy-fit gate are
reported separately and cannot veto qualification. In survival mode the
run-level `train_equity_ok` alias follows survival, while
`train_portfolio_fit_ok_by_seed` preserves the older fit diagnostic. A peak-DD
policy-fit miss remains diagnostic and does not recommend retraining during
survival qualification. Aggregate summaries now require one completed result
for every configured seed. Persisted portfolio-fit and activity flags also
require literal boolean `true`; malformed strings such as `"false"` cannot
become passing diagnostics through truth-value coercion in either per-seed or
multi-seed summaries. Evaluation JSON, walk-forward records, and report-only
split summaries now preserve only literal boolean survival/completion evidence;
malformed values fail closed. Persisted breach counts are retained only when
they are nonnegative integers (excluding booleans); malformed values become
unknown and cannot qualify as zero breaches in train-split or fold evidence.
Run artifact diagnostics now preserve malformed survival flags as false and
malformed counts as unknown instead of truth-coercing them.
The shared performance-metric adapter also rejects boolean, string, float, and
negative breach-session counts instead of converting them to integer counts.
The underlying metric function now validates both breach and session counts as
typed nonnegative integers, preventing invalid denominators or breach rates.
Regressions are included in the consolidated suite and remain unrun.
Regression cases are included in the consolidated suite and remain unrun.
Runtime logs report the per-seed full-split survival
outcome separately from the cross-seed/fold qualification, preserve zero-trade
activity as `INACTIVE` diagnostic status without rejecting survival, and label
equity-policy misses as diagnostics during that phase. These regressions are
included in the consolidated suite and remain unrun.
The year-episode regressions now also construct the environment with composite
sweep shaping and check that intermediate rewards remain zero, successful
completion is exactly +1, and a hard breach is exactly -1; they are included in
the consolidated suite but unrun. If training survival fails, the runner now
attempts to write a failed gate artifact and
skips walk-forward work; this path is unverified pending the consolidated
implementation batch. A known finalization failure is passed into the gate
builder as a forced failure, so stale passing seed artifacts cannot override
that failure. Seed-training and walk-forward execution errors now use the same
fail-closed path; these protections remain unverified until the consolidated
implementation gate. Portfolio-reward training requires that gate and must
resume the exact qualified per-
seed PPO or SAC checkpoint with matching source tree, behavior config,
algorithm, reward selector, datasets, feature-cache identity, and revalidated
seed/fold evidence. A zero-trade policy can pass survival; profit and activity
are not substitutes for the hard no-breach condition. These changes remain
unverified pending the consolidated implementation gate, so keep training
blocked until then. The gate reads hard-risk status separately from the
policy-fit `ok` field: negative returns or a policy-fit miss cannot veto an
otherwise complete breach-free qualification, while any breach or mutated
per-seed evidence blocks portfolio training. Portfolio resume is one qualified
seed per run and rejects a multi-seed resume before data loading. It also
validates each run's survival reward, algorithm, architecture, strategy, fold
setup, and saved effective configuration against the gate request. Duplicate,
missing, or mismatched seed results also fail closed. Run provenance records
and rejects MVP-capped training and locked-report-period selection. Portfolio
admission requires the versioned survival gate contract and exactly one
evidence entry per unique seed. Every required full
evaluation path must finish with zero hard daily-loss or maximum-loss breaches;
any breach makes that candidate ineligible for selection, regardless of profit
or later recovery. The Stage E hard-breach event now records a versioned
valuation `detection_time` and pre-detection trade-event prefix, separate from
the decision-bar label. The independent account and policy verifiers use that
prefix to distinguish a fill that caused a breach from an entry after it;
old or incomplete breach records fail closed. This source change and its
same-minute regressions remain unverified until the consolidated gate. Only candidates that
survive every predeclared seed and period can be compared on net return over
always-no-trade. The existing minimum six paired seeds and sign-flip/bootstrap
contract still apply. This changes the prospective selection order; it does not
rewrite historical DSR rewards or breach results. No new training or model
selection starts before the implementation and upstream evidence gates close.
The limit-fill sensitivity report now rejects non-boolean setup-eligibility
flags and reports missing or malformed position-completion flags as unknown
instead of coercing strings such as `"false"` to true or assuming completion.
Regression cases are included in the consolidated suite and remain unrun.
The shared performance metric now excludes identified positions with malformed
completion markers or incomplete close cashflows, rejects booleans as numeric
PnL, and retains the documented legacy inference for a final close with no
completion marker. It no longer inserts zero PnL when a completed position has
no valid cashflow. The trade-event position exporter also parses explicit
completion flags without truthiness coercion and leaves missing or malformed
terminal flags unknown for identified and unlinked events. Focused regressions
are included and remain unrun.
Saved-run report assembly now rejects malformed or mutually inconsistent
`breached` and `hard_risk_ok` values, and the rendered hard-risk status no
longer infers PASS from a reason string when a typed flag is invalid. Its
regressions are now included in the consolidated release test list and remain
unrun.
Training run summaries also require typed, consistent hard-risk flags and a
literal `true` for gate `ok`; malformed values can no longer produce passing
hard-risk, policy-fit, or activity status. Its regression is in the same
consolidated gate and remains unrun.
The gate producer and portfolio revalidator now require literal `true` values
for completion/survival and an integer zero breach count on every train and
walk-forward path; malformed truthy strings can no longer satisfy survival.
Both also reject capped `max_days`, non-full-split episode mode, and
`max_episode_steps` configurations, including when revalidating the saved
qualification config. Regression coverage is in the consolidated suite but
remains unrun.
The legacy `qrl-experiment variants` path and its direct per-variant training
function have been retired: they called `model.learn()` outside the survival
phase barrier and could rank variants on exposed report-period data. The direct
`compare_encoders.py` command is retired for the same reason; it trained reward-
optimizing policies outside the gate and evaluated the already-exposed 2026
period. Its injected-model evaluation helper remains available. Existing report
reading and aggregation helpers remain available; new training must go through
the canonical, provenance-checked training and experiment-run workflow. A
regression for the retired encoder command is included in the consolidated
command-boundary suite; it has not been run separately and awaits the requested
full implementation gate.

## Live repository and compute snapshot

Live-state refresh taken 2026-11-06 08:56 UTC: branch
`codex/final-research-evidence-release`, HEAD
`367561a7717a3367fbb280084ffcf0781f57119c`, with 604 Git status entries.
Preserve all existing work; do not reset, clean, or stage unrelated changes.
`squeue` has no pending or running jobs; `sacct` reports allocation `21426161`
as `TIMEOUT` at its 12-hour limit. No `scancel` was issued. The persistent
`qrl-live-guardrail-validation` tmux session is at the login5 prompt after the
allocation step ended. No training or evaluation is running. The attempted
same-basename scratch scan wrote its report but exits with `incomplete_walk_errors`
for 3,516 inaccessible directories; it found no exact matches among 589 hashed
files and cannot establish absence outside the readable user tree. Current
shared-filesystem `df` reports `/scratch` at 54% and `/home` at 88%; these are
filesystem-wide figures, not refreshed personal quotas. Do not start training
until implementation gates pass and the registered scientific gate permits it.

The train-only feature-snapshot comparator passes its 24 focused tests and
Ruff checks. A current-source checkpoint replay first exposed and fixed a
schema derivation bug: the schema used encoder observation windows instead of
`risk.target_timeframes`, which the environment and backtest actually consume.
The focused manifest suite passes 24/24 with scoped Ruff checks. The replay
then stopped at the sequence-schema guard: the saved A4 checkpoint and manifest
declare width 746, while current source selects width 724 and excludes 23 raw
structural coordinates, including price levels, from the normalized model input. The
checkpoint input width independently confirms the saved width. Reintroducing
those coordinates would change the current model-input contract, so current-
source same-policy replay is a bounded no-go. The A4A attempt stopped before
inference; A4B was not attempted. The disposition and hashes are in
`evidence/research/selected_checkpoint_train_replay/current_source_input_schema_disposition/`.
The pinned-source historical replay remains the bounded checkpoint result.
Deterministic repeatability for the historical A4 checkpoints is a bounded
no-go under the current no-new-Slurm direction: A4A's available current-source
replay is stochastic, while A4B has only one changed-policy replay. Any future
survival-qualification checkpoint must use the corrected deterministic worker
and comparator. The train-only full-ledger writer and repeatability comparator
now require hashed cycle-event and payout-event
artifacts even when those event tables are empty; a missing ledger no longer
looks like a valid zero-event result. Setup-aware action schemas also require
the separate setup-decision ledger at export and repeatability comparison.
Both replay reconciliations now require `status: matched` and a literal integer
zero failure count; booleans, strings, and floating-point zero fail closed.
Every ledger row count is also required to be a nonnegative integer, so a
boolean cannot stand in for a one-row artifact. The independent account and
policy reconcilers now also reject Python and NumPy booleans as numeric amounts
or integral actions/IDs instead of coercing them to zero or one. The policy
reconciler also requires typed setup-eligibility and position-completion flags;
truthy strings such as `"false"` make the evidence incomplete. Regressions
cover daily-loss amounts, actions, eligibility, and close completion; all are
in the consolidated suite and remain unrun.

## Implementation-first sequencing gate

Complete and verify every implementation checkbox in the consolidated full-plan
checklist before starting any new research experiment or training campaign.
Work through the remaining reusable code and architecture items first; keep
experiment execution paused until that implementation list is complete. Then
resume the plan's scientific and evidence gates and start experiments only when
those gates authorize them. Implementation completion alone does not authorize
model selection or training. The release-quality script now includes the
currently changed test modules, including the new survival gate, candidate
geometry, checkpoint-resume, and local tick-trace verifier tests. A static
coverage check confirmed all 154 listed test paths exist and all changed test
modules are represented; this does not replace running the consolidated gate.

The candidate-geometry implementation is now wired through the environment,
PPO policy/distribution contract, action decoding, checkpoint metadata, and
evaluation/backtest paths. The fixed observation contract remains 217 slots
(NO_TRADE plus 108 setup IDs by market/limit execution) with versioned causal
geometry features and explicit candidate masks.

The full V3 TODO 1–162 contract is represented by the machine-readable catalog
and validated as an exact dependency DAG. Critical TODOs must reference a real
repository tool, not merely appear in a checklist. Current-source pre-training
work now includes an explicit synthetic terminal-survival-to-PPO-gradient
reachability proof plus one semantic compute contract covering full-path counts,
rollout rounding, walk-forward terminal exposure, vector-environment geometry,
and measured end-to-end wall-time estimates.

Post-survival work is source-complete as an execution framework: reviewed phase
records can freeze exact direct-child commands for checkpoint replay, portfolio
continuation, robustness, and the one-time exposed report period; a source-bound
bundle/executor runs them without embedding Slurm allocation/cancellation
commands. Portfolio hard risk, the six-seed primary v2 treatment-vs-no-trade
payload, v4 metrics, final research tables/narrative/limitations/figure index,
checkpoint registry, provenance, old-open-box dispositions, release package,
final handoff, and TODO 162 FINISHED all have explicit validators. Actual
checkpoints and measured numerical outcomes remain runtime evidence rather than
source-code assumptions.

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
that configured gross realized-loss counter, not an FTMO-style net daily-equity breach. The
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
start a multi-seed comparison while P6 is failed. A successor needs
a specific, evidence-supported change to a scientific factor, a newly
registered matched configuration, and a predeclared acceptance rule. Preserve
the failed results and their run identities as historical evidence.
Any later policy-selection analysis must follow the current
[validation protocol](../research/validation_protocol.md); the historical
five-seed exploratory pair does not satisfy that prospective selection
contract.

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
- **Feature prefix check:** the final v40 all-profile run is preserved in
  `evidence/research/feature_causality/real_market_feature_prefix_invariance_current_source/`
  completed in four parallel processes inside existing GH200 job `21405414`
  on 2026-11-04 and completed in 2,319.61 seconds. It resolves 130 configurations into 19 feature-builder
  groups and checks three cutoffs (2025-12-15, 2026-03-09, 2026-06-15):
  **57/57 comparisons passed**, covering 21,741,766,365 values with no changed
  features and maximum absolute delta 0.0. The fail-closed merger required all
  four shard identities and complete group/profile/cutoff coverage. A separate
  post-run check matched all 78 source hashes, the inventory hash, and four
  local M1 input hashes to the current checkout and data. The percentage-only
  risk-limit migration is included in this current-source snapshot.
  The v39 report is retained at
  `evidence/research/feature_causality/real_market_feature_prefix_invariance_v39.json`
  as a source-versioned historical comparison. The v40 five-group packet
  remains useful as a bounded IFVG/PO3 rerun and is preserved separately.
  The preceding v38 reconciliation and superseded snapshot are
  recorded in `evidence/research/feature_causality/prefix_source_reconciliation.md`.
  The final `git diff --check` passed. This run closes the prefix
  invariance slice for its resolved inventory and recorded inputs; it does not
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
  A source review confirmed a multi-date session-level discrepancy:
  `detect_session_levels` pools rows selected by time-of-day across the supplied
  history before applying a rolling high/low, while
  `features/context/session_levels.py` computes running OHLC within each
  session date. A two-date fixture captures the prior-date extreme at the next
  Asian open and checks full-versus-truncated prefix equality; all 17
  session-level tests passed before the documentation-only correction. After
  correcting both public docstrings, the focused structure and session-level
  suites pass 22/22 and Ruff passes for both touched files. The correction does
  not change feature outputs or cache semantics. The later current-source
  all-profile prefix audit covered these docstrings and the SMT correction:
  all 19 configured profile groups passed 57/57 cutoffs, comparing
  21,741,766,365 values with zero maximum absolute delta under the v39 feature
  semantics. Its merged packet is
  under `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/real_market_feature_prefix_current_source/`.
  This closes prefix invariance only. A source-to-test graph review records 18
  call sites across 15 nodes and 11 linked tests in
  `evidence/research/function_test_coverage/critical_symbol_review.md`.
  The current public output's `prev_day_close` is assigned from `close.shift(1)`,
  not the previous calendar day's close; this raw column is excluded from MTF
  model inputs. No future leak or model behavior change is inferred from these
  documentation defects.
  Candidate-scoped event counts now have a bounded disposition; a single
  cross-family logical-event total is a documented no-go because there is no
  source-backed global event ontology. Historical candidate-proposal-to-action
  linkage remains open; prefix invariance does not establish causality for
  execution, labels, or model selection.
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
- **Candidate geometry at decision scale:** the geometry analyzer now joins the
  source feature matrix to close and ATR computed from the exact same M1
  training-bar index; it fails if those indices differ. This was necessary
  because the model feature matrix intentionally omits raw close and ATR. The
  first scale-aware draft is preserved at
  `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/superseded/candidate_geometry_relative_scale/`
  as a superseded diagnostic, with its output checksum manifest preserved;
  its absent reference columns yielded unavailable normalized metrics. The corrected run is
  `evidence/research/candidate_geometry_price_scale/`, schema
  `candidate-price-geometry-support-v3`; its source, inputs, outputs, and
  packet checksums are recorded. It covers the same 351,432 training rows,
  109 catalog entries, 24 active candidate categories, and 488,008 active
  candidate-row occurrences, with finite geometry and valid ATR scaling for
  every active occurrence. Across candidate-category medians, standard-
  deviation bands have median width 5.262 M1 ATR and median distance 0 ATR;
  the close lies within those bands on 59.6%–100% of candidate rows by
  category. The two PO3 categories have median width 0.328 ATR and median
  distance 1.097 ATR, with the close inside 7.1%–7.6% of rows. IFVG-retest
  and IFVG-unretested categories have median widths 0.432 and 0.321 ATR and
  median distances 1.226 and 1.374 ATR; their closes are outside the bounds
  on all active rows. Distance is zero while close is inside a zone and is
  otherwise the distance to its nearest bound, divided by current M1 ATR.
  These are feature-availability and geometry-location summaries, not
  candidate labels, entry/stop/target proposals, fills, returns, or policy
  evidence. This strengthens the input-feasibility evidence for a geometry-
  aware challenger; executable candidate objects, outcome-label integrity,
  historical action linkage, and matched economic evaluation remain open.
- **Candidate proposal and outcome contract:** `evaluation/candidate_proposals.py`
  now defines versioned proposal records with causal confirmation/validity/
  expiry, one market and optional zone-midpoint limit proposal, production-built
  stop/target choice menus, price-grid validation, stable identity, and explicit
  fixed-entry outcome/censoring states. The canonical conditional-outcome-v2
  record now lives only in `evaluation/candidate_outcomes.py`; its duplicate v1
  definition and tests were removed from the proposal module. The v2 contract
  rejects premature non-fill labels and realized returns on non-fills or
  censored exits. The combined proposal, outcome, eligibility, and replay suite
  passes 37 focused tests on the existing GH200 allocation.
  The training-only proposal-ledger generator now reads the configured local
  training inputs, deduplicates source-identified candidate events, uses the
  last quote in each completed M1 bar, and builds each proposal's stop/target
  menus with `place_strategy_order`. Its substantive build completed with exit
  code 0 on Slurm job 21376798, which remains available on the existing
  one-GH200 allocation. It processed 488,008 active candidate-row occurrences
  across 24 configured categories, identified 109,391 candidate events, and
  wrote 203,397 proposals (105,458 market and 97,939 pending-limit proposals).
  These are candidate-incidence counts, not policy-eligible actions or outcomes.
  The verified packet records 56,099 proposals on bars labeled NY and 147,298
  outside NY; this confirms the need to apply action eligibility before using
  it for candidate-policy inference. Of the identified events, 107,036 have at least
  one proposal; 2,355 produce none under the current geometry rules. All 108
  catalog categories are present in the coverage table; 24 are configured
  supported categories. Its exact generator, dependencies,
  resolved config, and local data manifest are preserved with 15 checksums in
  `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/run-21376798/source_snapshot/`.
  An independent verifier matched the recorded source hashes, resolved config,
  local raw-data manifest, input identities, and proposal-row count. All four
  packet output checksums pass; the original proposal contract had 14 focused
  tests before schema consolidation. The
  earliest and latest `valid_from` timestamps are within the configured local
  training window. Twenty-nine proposal expiries extend beyond that window and
  must be right-censored at the training-data cutoff during replay. Before
  outcome labels are treated as candidate-training evidence, retain explicit
  eligibility dispositions while keeping all feature rows unchanged.
  The reusable `evaluation/candidate_eligibility.py` classifier now mirrors the
  environment's NY-row, open-blackout, next-fill-bar, configured latency, and
  same-session follow-up/overnight-boundary rules; eligible rows also resolve
  their local M1 session-close deadline for forced-exit replay. Five synthetic
  boundary tests pass. The corrected builder now applies this classifier and
  only marks an event consumed after it creates a proposal, so an earlier
  ineligible, unconfirmed, unquoted, or geometry-incomplete row cannot suppress
  a later eligible decision. The rebuilt packet at
  `evidence/research/candidate_proposals/` completed on the existing one-GH200
  allocation. Independent verification passed proposal, ID uniqueness,
  source/config/raw-manifest/input/output hash, and training-window checks. It
  contains 54,638 proposals, all labeled NY and within the training window:
  28,787 market and 25,851 pending-limit proposals. Across 109,391 identified
  events, 29,904 pass static action eligibility and 29,116 produce at least one
  proposal; the 788 eligible events without a proposal remain attributable to
  quote or geometry rules. The packet status remains static eligibility with
  no outcome replay and no account-state evaluation.
  A reusable quote-coverage audit now compares source-wall-clock raw tick rows
  and two-sided quote validity with configured M1 `tickvol` at
  `evidence/research/tick_quote_coverage/`. It finds 40,330 M1-minute count
  mismatches, 161,302 raw rows without valid two-sided quotes, and 258,106 of
  351,432 M1 rows meeting the conservative per-minute consistency rule. This
  is local-source reconciliation, not external tape-completeness evidence.
  Joining those minutes to proposal action-fill and order-life windows finds
  quote-complete coverage for the eligible market-fill minute on 24,064 of
  28,787 market proposals, and across the full pending-limit life on 5,543 of
  25,851 limits. Other intervals must not receive a no-touch or no-exit label
  merely because no trigger appears in the observed TickBook. Both audit
  packets have verified output checksums. The corrected proposal contract,
  outcome schema, eligibility, and replay focused suite passes 37 tests on the
  existing GH200 allocation. Next: make replay coverage-aware, preserve
  unresolved-data outcomes, then build and independently verify the
  training-only conditional outcome ledger. This remains conditional
  fixed-entry evidence, not policy-action or account-level value.
-  The reusable bar-level census completed on the configured local 2025
   training M1 input at
   `evidence/research/candidate_action_eligibility/`. All 351,432 source rows
   reconcile: 99,492 are NY-session rows; 96,384 (27.43% of all M1 rows) pass
   static action/fill eligibility. The 255,048 rejected rows comprise 251,940
   off-session rows, 2,590 open-blackout rows, 259 off-session fill bars, and
   259 overnight-boundary fills. Packet checksums and independent row/reason
   totals pass. This is a denominator census only; it does not count active
   candidate features or policy actions.
-  `evaluation/candidate_execution.py` now implements conditional tick replay
  for market and pending-limit proposals, executable bid/ask fills, protective
  exits over a zero-copy, cutoff-bounded tick window, commission and adverse-
  fill costs, and explicit non-fill and right-censoring states. It returns a
  v2 outcome record, including when a known fill leaves the selected stop or
  target invalid or a protective trigger lacks a timely quote, preserving fill
  details without inventing a return. Fixed brackets are scanned in one bounded
  tick pass rather than one Python call per minute. A supplied local session
  close now force-closes unresolved brackets through the configured deadline
  quote resolver; missing close quotes remain unresolved with the fill
  retained. The `evaluation/candidate_outcomes.py` v2 schema defines stable
  bracket-specific identity and allows known fill metadata on unresolved-data
  records while still prohibiting return labels.
  All 24 replay/schema/eligibility tests pass on the current GH200 node; Ruff
  passes for the six touched Python files. This is synthetic contract evidence
  only.
  **Current-source packet:** the proposal builder processed current local
  training data and emitted 54,638 statically eligible proposals across 29,116
  candidate events. The separate interval audit found complete quote coverage
  through disposition for 24,064 market proposals and 5,543 pending-limit
  proposals; incomplete or missing intervals remain unresolved. Exact-touch
  and strict trade-through replays each emitted 1,067,731 bracket rows. The
  exact-touch statuses are 273,350 filled/resolved, 29,701 unfilled/expired,
  and 764,680 unresolved; strict trade-through has 273,315, 29,736, and
  764,680 respectively. Both current packets pass full independent array-level
  replay of every status, time, fill, exit, reason, and return field with zero
  mismatches. Independent source-quote and net-R arithmetic also has zero
  mismatches (273,350 and 273,315 resolved rows). Twelve-row stratified samples
  pass through the production replay function for both packets. A second exact-
  touch replay matches all 1,067,731 Arrow rows exactly. Across 513,141 paired
  limit outcomes, strict trade-through changes 35 exact-touch fills to expiry;
  104,607 resolve under both assumptions. The mean strict-minus-exact net R
  among those jointly resolved rows is -0.000147 and the median is zero. These
  are training-only conditional fixed-entry results, not independent trades,
  policy outcomes, or an economic edge estimate. The high unresolved share
  reflects local quote gaps and limits conclusions to the resolved subset.
  Current packets are at `evidence/research/candidate_proposals/`,
  `evidence/research/tick_quote_coverage/`,
  `evidence/research/candidate_outcome_coverage/`,
  `evidence/research/candidate_outcomes/`, and
  `evidence/research/candidate_outcomes_trade_through/`. The fill-sensitivity
  implementation is in
  `scripts/research/analysis/evaluation/compare_candidate_limit_fill_packets.py`.
  **Implementation follow-up:** fixed-proposal limit replay now uses the
  shared TickBook limit resolver, supports exact-touch and strict
  trade-through as an explicit input, applies seeded submission latency, and
  includes a quote at the declared TTL expiry. Limit fills retain their hard
  submitted-price bound and do not inherit market-order slippage. The outcome
  builder records the fill assumption and hashes its runner source. The paired
  limit-fill sensitivity report is
  `evidence/research/candidate_outcomes/limit_fill_sensitivity.json`.
  The exact-event linkage audit can
  cover matched development baseline traces only; the traces do not identify a
  selected market-versus-limit proposal for each event, and historical PPO
  proposal-to-action linkage remains unavailable. Neither replay nor that
  limited linkage establishes account-level policy value or closes Stage D.
  The separate candidate-action audit now preserves every matched, unmatched,
  and within-validity-window baseline decision row. Of 70,716 identified
  selected-candidate rows in each non-flat arm, 67,973 random and 68,011
  structure-priority rows share a candidate/event key with the proposal
  ledger; only 39,566 and 43,974 rows respectively fall inside the ledger's
  recorded validity window. Across both arms, 22,310 of 29,116 proposal
  candidate events overlap a selected baseline event, while 9,137 overlap
  within that validity window. These are development baseline trace joins,
  not historical PPO actions, executed market/limit choices, fills, or policy
  value. Packet checksums pass. The unmatched and outside-window rows remain
  available for further disposition in
  `evidence/research/candidate_action_linkage/`.
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
  aggregates 1,291 feature/timeframe pairs across 23 profile groups. The
  current-source report flags two features that are entirely non-finite in
  every group (the D1 Asia/London midpoint distances), 206 pairs with interior
  missing values, and 219 with a missing/finite-zero collision. These are
  observed patterns, not producer-cause
  findings. Source review confirms `sweep_*_age` is non-finite without active
  sweep state and zero on the event bar; the same producer exposes the event
  pulse, while the observation path maps non-finite values to zero and has no
  per-feature mask. A v39 source review replaced the outside-session
  `po3_phase` NaN with an explicit `-1` sentinel (active phases remain 0/1/2),
  which also distinguishes clipped `session_progress` from active session
  boundaries. Valid zero-range candles now have a defined zero upper-wick
  ratio, while missing OHLC inputs remain nonfinite; the feature-cache identity
  is `v39-feature-validity-semantics`. The regenerated all-profile audit covers
  130 profiles, 23 observation groups, and 15,571 feature rows with zero group
  failures. Its current triage has 219 missing/finite-zero collision pairs,
  206 interior-missing pairs, 463 leading-only pairs, and two fully unavailable
  pairs. The producer-semantics crosswalk now maps the 1,291 pairs to 41
  reviewed producers and records sentinel, zero-range, and normalization
  semantics; eight leading nonfinite M1 PO3 rows per feature (one in each
  affected group) are consistent with the normalizer's two-observation
  standard-deviation warmup. The current-source v40 all-profile prefix
  comparison passes 57/57 cutoffs over 19 feature groups, zero failures, and
  zero maximum absolute delta. Its strict merger and independent post-run hash
  check verified all 130 inventoried profiles, 78 source hashes, the inventory
  hash, and four local input hashes in GH200 job `21405414`. The focused
  source/validity batch passes 84 tests and the
  touched-path Ruff checks pass. This measured validity audit does not certify
  that every historical architecture receives every companion feature.
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
  remain part of the open causal-feature gate. The new survival qualification
  overlay enables this column and requires it in run-manifest sequence identity;
  it has not yet produced a trained policy. The matrix/config/factory
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
  `config/features/fvg_ifvg_mtf.yaml` profile, it records 49,780 per-zone retests and
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
  checksums verify. A current-tree source-hash audit found two mismatches, both
  limited by the working diff to docstrings and the packet's limitation wording;
  the stored results remain descriptive, but current-source reproduction
  provenance is not exact until the packet is regenerated or explicitly
  re-bound and re-hashed. Bar-indexed sweep, reclaim, IFVG-confirmation, and FVG-origin
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
- **Reanalysis:** a daily-floor breach permanently fails the account/evaluation
  and blocks later entries. Non-episodic rollouts may continue for training
  data collection, but failed accounts do not survive evaluation. This behavior
  is covered by the paired local-data trace and focused tests. The seed-50
  historical gross realized-loss counter sums negative closes without
  offsetting gains; it must not be treated as net daily-equity or FTMO daily
  loss semantics.
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
   The implemented research contract separates the session loss allowance
   from maximum-loss drawdown. Daily loss measures session net equity from the
   session-opening anchor, includes open PnL, and allows 5% of initial equity.
   Equality at the daily floor is allowed; equity below it permanently fails
   the account. A payout can withdraw only realized balance above the initial
   operating balance; it resets the session anchor and recalculates the day's
   floor. Maximum-loss
   drawdown is selected as `static`, `eod`, or `intraday_trailing`, each with
   its allowance based on initial equity. EOD and intraday floors cap at
   initial balance; payout locks those floors to initial balance immediately.
   Per the user's decision, equity exactly at that payout floor is allowed and
   equity below it breaches. Static drawdown keeps its fixed initial-balance
   floor; equality there is allowed and only equity below it breaches. Agents
   cannot select the mode. Unit and environment/backtest payout
   lifecycle tests pass 60/60, with the current payout boundary exercised in
   all three modes. This freezes the research semantics, not training/live
   parity or exact external session-calendar parity; provider/license and
   external-calendar research remain excluded by user direction.
    The training environment and event-driven backtest both reset the daily
    allowance on the supplied date-derived `session_id`, while any daily-loss
    breach now permanently fails the account/evaluation and blocks entries in
   later sessions. Maximum-loss/trailing-drawdown failures remain latched for
   the rollout. The paired daily-breach characterization now runs both the
   environment and backtest across a session transition with an always-long
   policy; each records one breach and only the pre-breach opening. The focused
   test passes (1/1) with touched-path Ruff checks. The superseded
   next-session-recovery trace and its verifier are checksum-preserved outside
   the repository under
   `/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/repository_packets_pre_current_source_20261105/daily_loss_reset_superseded/`;
   the current packet contains only the separately named daily-breach failure
   trace. Daily/static floor
   boundaries are verified in
   `evidence/research/simulator_execution_parity/daily_static_floor_boundaries/`.
   The new paired full-evaluation characterization packet is
   `evidence/research/simulator_execution_parity/daily_breach_full_evaluation/`;
   it records exact output, source hashes, reproduction command, and claim
   limits. This closes only the daily-breach next-session block subcase.
   `AccountState` now
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
   The current-source PnL-blind stratified extension contains 58 controlled
   pairs across 23 of the 24 2025 month/direction strata (May-long has no
   eligible pair), with up to three pairs per stratum and no event reuse. All
   58 environment/backtest traces match their selected TickBook source, fill
   time/price, source decision bar, close PnL, and ending balance. The first
   current-source verifier run exposed a phase-field bug: it compared the
   environment's completed-bar timestamp with the backtest's next-bar decision
   timestamp. The verifier now compares the two engines' `decision_bar_time`
   fields and retains their separate decision/submission timestamps; its
   regression tests pass 2/2 and independent verification passes all checks.
   This strengthens feed-path characterization only; it is not historical
   policy linkage, statistically independent evidence, portfolio lifecycle
   acceptance, or an economic result. Evidence and reproduction are in
   `evidence/research/simulator_execution_parity/README.md` and
   `local_tick_action_trace_set_stratified.json`.
   The first expanded run exposed a short-action encoding gap in the trace
   generator, now covered by long/short synthetic regression tests. Its
   corrected one-step rerun completed in 106 seconds, below the repository
   120-second Slurm step hard gate; no further allocation or retry was started,
   and both scheduler logs are preserved outside the repository. This is an
   operational launch-control deviation, not research evidence. The broader
   sample does not resolve timestamp ties, external clock/session authority,
   market impact, or broker behavior.
   A controlled account-transition trace applies prescribed opens/closes
   across local date-derived IDs for 2024-12-30 and 2024-12-31. It initially
   found that `TradingEnv` filled at the next bar open while `run_backtest`
   used the next bar close. The event backtest now uses the same next-bar-open
   quote and timestamp for bar fallback. The rebuilt two-session trace passes
   independent event/account reconciliation, both engines agree on lifecycle
   fields and ending account state, and the focused execution-contract module
   passes 25/25. This closes the controlled bar-fallback discrepancy only; it
   does not establish broad lifecycle, live-account, or economic parity. The
   selected research path still requires TickBook execution. Evidence:
   `evidence/research/simulator_execution_parity/local_session_account_transition/`.
   Stage E remains partial.
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
   loss limit. This older trace allowed a next-session open after a daily
   breach and is superseded by the user's full-evaluation-failure rule; do not
   use it as current semantics. The current-source replacement sets the
   controlled $1 hard daily limit through its percentage field, attempts both
   same-session re-entry and next-session entry, and verifies that both engines
   record one `daily_loss` breach and latch the failed account for the rest of
   the evaluation. The two engines and independent verifier agree on breach
   reason, session, equity, daily loss, fills, and zero later opens. The current
   packet and all four account-trace verifications pass. A separate episodic
   max-loss TickBook trace now also passes both engines and the independent
   verifier. Source review found that the
   environment sampled a second randomized-latency quote while force-closing,
   after the current step had already selected the executable quote; it now
   reuses that quote, matching the event-backtest's per-bar cache. Breach equity
   and daily loss are recorded before liquidation and match. Final daily-loss
   counters are explicitly not compared because the episodic environment stops
   at the breach while the backtest reaches the next-session reset; final
   balance and equity match. Full guardrail/action coverage and live/restart-safe
   parity remain open. Current daily-loss evidence:
   `evidence/research/simulator_execution_parity/local_session_account_transition/daily_breach_full_evaluation_failure.json`.
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
   At the time of this audit, the event-driven backtest accepted scalar actions
   only. That limitation was partially superseded by the later mask-aware,
   schema-versioned setup callback, which now carries risk, geometry, execution,
   and SL/TP management coordinates through event-backtest orders and fills.
   The preserved selected-policy evaluation still uses `TradingEnv`; the new
   event-backtest action path is not itself a historical checkpoint replay.
   Comprehensive feed/lifecycle coverage beyond the stratified 58-trace sample,
   and live account-risk parity remain open. The scalar policy boundary
   rejects non-integer and vector outputs explicitly; vector actions require
   the opt-in setup schema. Checkpoint
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
   The event-driven engine retains its scalar rule/diagnostic path and now has
   an opt-in mask-aware setup-action path. A lossy vector-to-direction adapter
   would still drop setup eligibility, risk, stop/target, execution, and exit
   coordinates. Full cross-engine parity remains open for optional observation
   branches, account lifecycle, and paired policy traces.
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
   A data-end comparison found that the event backtest liquidated an open
   position but `TradingEnv` left it open when the final policy bar truncated
   the split. The environment now realizes that position before recording
   terminal reward/account values. Both paths use a stable `bar_fill` event key
   for configured randomized tick latency. The paired synthetic case passes at
   zero and 30 ms latency; the adjacent risk-lifecycle, payout, and year-survival
   batch passes 38/38. A follow-up handles an explicit `max_episode_steps`
   boundary: the paired environment/backtest case matches terminal time, quote,
   PnL, balance, and equity at natural data end and at a four-step cutoff, both
   at zero and 30 ms latency. The expanded adjacent batch passes 40/40. Its
   environment event records the cutoff cause while the sliced backtest records
   data end. Evidence and current source hashes are in
   `evidence/research/simulator_execution_parity/data_end_position_liquidation/`.
   The natural-end result is retained in that packet; explicit step-limit
   evidence is in
   `evidence/research/simulator_execution_parity/max_episode_step_liquidation/`.
   These close only the tested terminal-liquidation cases; arbitrary early
   reset, checkpoint/replay, overnight-held post-NY tails, and full
   account/report parity remain open.
   The source call-path review now traces environment and backtest decision,
   pending entry, tick/bar quote resolution, protective exits, broker/account,
   and reward/report updates. A later source review traces learned market
   and resting-limit choices, bounded limit price/TTL, TickBook fills, and
   setup/session/account cancellation in
   `evidence/research/simulator_execution_parity/learned_market_limit_execution_path/`.
   The earlier `execution_path_map/` remains as its historical market-only
   review. Synthetic order lifecycle coverage exists separately; broad
   runtime/account parity remains open.
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
   A separate source audit found `RLStrategyAdapter` rebuilds normalized live
   features without the train-only mask and has no serialized normalization
   state to restore. This differs from the train/evaluation path, which applies
   the fitted training mask and freezes its statistics beyond the cutoff.
   The paper inference path therefore does not demonstrate feature parity, even
   when it loads the run's feature config. Record live policy use as a bounded
   no-go until a versioned fit-state is persisted and replay parity is verified.
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
   The standalone `score_rule_baselines.py` output now records the actual
   evaluation bounds, marks any overlap with 2026-01-01 through 2026-10-16 as
   `exposed_report_only`, prohibits selection use, and leaves other periods
   unclassified rather than naming them holdouts. Three focused period-role
   tests pass with touched-file Ruff check/format. The market scorer was not
   run; this fixes report semantics and does not add a baseline result.
   Source inventory confirms `run_baseline_eval.py` already registers the
   combined EMA/MACD/RSI, Asian-level breakout, and session-momentum rules,
   plus opt-in MACD-histogram and RSI mean-reversion arms. Their current code
   and synthetic signal tests establish availability only; no matched market
   comparison was run, and the Tier 1 result gate remains open.
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
A4A's sole recorded breach was the gross realized-loss counter, recorded under
the `daily_loss` event label;
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
data is bundled and no rights claim is made. The scan found missing/non-finite required bid/ask values in all four tick files,
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

## Selected checkpoint train-only replay

Both selected A4 seed-50 checkpoints now replay under their recorded
stochastic action mode on the 2025 training partition only. Each output matches
the saved training metrics for trade count, return, Sharpe, maximum drawdown,
and breach count; both fail full-period survival. The 2026 report split was not
evaluated. This is a diagnostic check of retained checkpoints and does not
authorize new training or resuming the failed campaign. The run reports and
scope are recorded in
`evidence/research/selected_checkpoint_train_replay/`.

The original full v24 cache bytes remain unavailable, but an assembled
training-only feature frame was reconstructed and its digest matches both A4
run manifests (`train_features.sha256=696cff0bef5ecea1b3d872d645752a28bc40fb8a862ee641084b903e89419717`).
This verifies the training frame only; it does not recover the full cache,
testing features, or complete tick identity. A current-source deterministic
ledger replay was attempted with this frame and correctly stopped before
inference: both checkpoints record the M5/M15/H1 stop menu, while the current
runtime derives M3/M5/M10/M15/M30/H1/H4/D1 from the saved config. The pinned
source snapshot confirms its default menu was the recorded three timeframes.
Do not bypass this schema mismatch or count the empty no-op CLI attempt as a
replay. The repeatability gate remains open pending an explicit compatibility
scope; no model result or ledger was produced by the failed current-source
attempt.

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
explicit unavailable states, input identities, and checksums. The denominator
reporting gate now has a bounded disposition rather than a single merged
funnel. The current matched-baseline arms have 99,492 unique decision rows
each, and all 1,854 random-arm and 1,169 structure-priority open events link to
their own decision IDs; the always-flat arm has no opens. The current summary
is `evidence/research/pipeline_denominators/current_matched_baseline_flow_summary.json`.
Historical A4A/A4B per-session decisions, order attempts/acceptances, and
candidate-to-action links remain unrecorded in scanned run artifacts, so the
historical joined flow is a bounded no-go and those counts remain unavailable,
not zero. This closes reporting of available scoped denominators; it does not
close Stage D historical policy linkage or establish historical order flow.
Future runs should retain those identifiers.

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
Readiness remains **blocked** on scientific validity and research/release
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
open. The single global logical-event count is a bounded no-go, not a pending
measurement; producer and candidate-scoped counts remain the reportable units.
The opportunity census was rebuilt from current source commit `367561a7`
after the prior packet's README checksum and two source hashes failed to match
the checkout. All census output checksums, 13 source hashes, and 17 training
input hashes now verify. The earlier packet is preserved outside the repository
at `superseded/candidate_opportunity_census_pre_current_source_rebuild/`.
The action-artifact scanner now recognizes exact `decisions.csv` exports by
their row schema; its refreshed 289-artifact inventory finds 13 such traces,
all under the matched-baseline result tree, and no complete per-decision
price-geometry trace. The three-arm baseline traces are linked to eligible
candidate choices and opens by the independent accounting audit, but do not
reconstruct the earlier selected A4 policy. The regenerated cardinality
register therefore records 13 current baseline trace files separately from a
bounded no-go for historical candidate-to-action recovery in the other scanned
artifacts. Candidate geometry, historical action linkage, and Stage D remain
open; the global logical-event total has the bounded no-go disposition below.
The 2026-11-04 nested-container follow-up found archived `policy.pth` members
inside the P6 viability attempt-1 checkpoint ZIPs. Their `ppo_best.zip` and
`ppo_final.zip` outer-file digests are among the 50 variant-and-seed files in
the frozen-pair hash report, and neither equals the replacement18 attempt-3
frozen digest. The candidates are retained as P6 lineage evidence and cannot
substitute for the selected policies. The bounded reconciliation is
`evidence/research/historical_variant_screen_recoverability/archived_checkpoint_container_reconciliation.json`;
this does not close the broader recovery search or historical action-linkage
gate.
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
The current checkout now contains that detector-level packet at
`evidence/research/order_block_zone_event_ledger/`; this supersedes the earlier
"no local-data packet" note above. Its output checksums pass, and its recorded
source/input hashes match the current checkout and pinned local M1 manifest.
For 351,432 training M1 rows, the nine configured timeframe projections
produce 134,227 per-zone retest confirmations against 21,154 scalar pulses;
33,810 same-row collision groups suppress 79,967 per-zone confirmations.
The focused research module passes 3/3 tests and touched-path Ruff passes.
The config records the OB detector as disabled, so these are descriptive
detector counts for the audit config, not selected-policy opportunities. They
close this one config's zone-level collision census only; they do not establish
logical cross-timeframe event identity, policy actions, trade outcomes, or
publication timing.

Execution/risk parity, matched economic baselines, independent-seed robustness,
and an untouched confirmatory period remain unresolved. The 2026 interval stays
exposed/report-only. At the user's direction, use current local data only and
do not seek external provider/license records or an authoritative schedule; no
raw data or rights claim is included. No policy training, commit, push, or
release tag was made. Preserve the negative P6 result and do not
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

## Continued full-goal execution — 2026-11-03

The no-trade Tier 0 arm completed on the full 2025 development split inside the
existing allocation 21376798 (gpuarm2). It processed 351,432 bars and 99,492
policy decisions, with zero entries, fills, return, and breaches. Its
hash-manifested output is
`evidence/research/matched_setup_baselines/matched_setup_baselines_18c585089f5e7857/`.
This verifies real-data control-path and artifact persistence only; it does
not provide an economic comparison.

The first random-eligible Tier 0 attempt stopped at bar 3,854,
`2025-01-02 19:49:00+03:00`. A source-data check of all 455 local tick rows in
that minute found a bid low of 20,790.45 and ask low of 20,791.65. The short
TP3 was 20,790.65, so the ask had not reached it. The failure was a checker
false positive: it compared bid OHLC with an ask-side short exit. The reusable
`trading.execution.exit_side_bar_range` now maps long exits to bid OHLC and
short exits to spread-adjusted ask OHLC in both TradingEnv and event-driven
backtest. Tick-only execution also skips candle fallback SL/TP fills. A unit
test covers exit-side range semantics; targeted simulation regressions pass.
A paired no-trade/random rerun subsequently completed as a bounded Tier 0
result. Bar spread remains a recorded estimate, not a reconstruction of
intrabar spread changes. The accepted matched packet and per-arm caveats are
summarized at `evidence/research/matched_setup_baselines/README.md`.

The no-trade result and random-arm blocker are reflected in the research
report, baseline catalog, figure/table registry, known-limitations list, and
release README. Current-source testing also found that TradingEnv returned the
previous decision row's setup mask after advancing its index. The next-row
observation is now rebuilt after the step; the regression and random-eligible
rollout integration coverage passed 10/10. Historical campaign outputs predate
this source correction, and the selected checkpoint is not recoverable for an
independent replay; no claim is made that historical policy results have been
reproduced under the corrected observation timing.

The current source patch has not passed the final release gate. The latest
known full-tree documentation/API audit still reports 256 Google-style
docstring gaps, Sphinx/inventory and release hashes are stale after the new
research packet and topic rename, and full GitHub CI was not run. Scientific
gates remain no-go for policy selection: historical proposal-to-action
linkage, authoritative local tick execution, broad account/lifecycle parity,
independent seeds, matched economic baselines, and untouched confirmatory
data are not established. Do not start training or treat the exposed 2026
period as confirmation. The release remains blocked; these are explicit
bounded dispositions, not completed empirical acceptances.

## Multi-target chronology and source quote precision — 2026-11-03

The next random-eligible run showed that multi-target tick replay moved a
short stop from 21,332.75 to 21,323.65 after a partial target, while the
post-replay OHLC assertion compared the updated stop against the whole bar.
The bar's high may have occurred before the stop update. The assertion now
checks only unchanged stop levels and target slots still active after tick
replay; the ordered quote replay remains authoritative for levels that changed
or were filled during the bar. A synthetic chronology regression covers a
pre-target high followed by a tighter stop, and the strict missing-target
regression remains enabled.

A later exact-level case exposed source precision loss: the CSV parser read raw
bid/ask as binary32, turning an input bid of 21,460.15 into 21,460.150390625.
The parser and TickBook now retain binary64 source prices, and the cache key is
versioned as `v7-source-precision-quotes` so earlier precision-losing caches
cannot be reused. The raw-price equality regression, tick loading suite, and
multi-target lifecycle tests pass 47/47. The current paired no-trade/random
2025 development evaluation is running on the corrected source and cache in
allocation 21376798; earlier paired attempts are retained only as execution
diagnostics and are not economic evidence.

The first complete two-arm trajectory showed 99,492 steps for each policy with
identical input hashes and evaluation bounds, but valuation timestamps diverged
at step 14 because the traded arm recorded a millisecond fill time and the flat
control stayed on the bar timestamp. The paired interval builder now uses the
common environment-step sequence only when input hashes, step count, and
evaluation bounds all match; otherwise it records paired inference as not
estimable. A focused 20-test evaluation batch passed.

## Per-arm uncertainty packet integrity

The completed bundle `matched_setup_baselines_3142f2920f4bd0cd` is retained as
a superseded artifact, not accepted as valid uncertainty evidence: its flat
control's confidence-interval JSON repeated the random policy's values even
though the saved flat equity and metrics were constant. The evaluation
calculation itself produced arm-specific values; the bundle writer reused the
last arm's function-scoped interval variable in its artifact-writing pass.
The writer now binds and validates intervals again for each arm in that pass.
A synthetic regression assigns a distinctive value to the later arm and
verifies both saved files and manifest comparison rows; the full matched-
baseline integration module passes 13/13.

The first three-arm manifest then exposed a second writer issue: its declared
flat-versus-random comparison contained the structure rule as an extra metrics
row. The writer now filters each comparison's metrics to exactly its declared
run IDs. The deterministic-rule integration case asserts that membership for
every comparison; all 13 matched-baseline integration tests pass. The prior
three-arm bundle `matched_setup_baselines_571b404168826c0e` is preserved with
its per-arm outputs but marked superseded for comparison metadata.

The corrected three-arm bundle is
`evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e/`.
Each arm processed 351,432 development bars and 99,492 steps. The flat arm
ended at $100,000 with zero entries, fills, return, and breaches; the seeded
random reference ended at $89,840.15 (-10.16%) with 1,854 positions and 25
breach events; the fixed structure-priority rule ended at $89,965.10 (-10.03%)
with 1,169 positions and 25 breach events. Its draft result manifest passes
schema, cross-reference, and artifact-hash verification when checked with the
packet root. Per-arm confidence intervals agree with their own trajectories
and manifest comparison rows. Both paired intervals use the exact shared step
sequence because inputs, count, and endpoints match; within-bar valuation
timestamps remain separately recorded. The fixed rule's paired one-path
intervals against random include zero for mean return, Sharpe, Sortino, and
drawdown difference. This is negative Tier 0/Tier 1 accounting and sanity
evidence, not model selection or an economic edge claim. The earlier valid
two-arm bundle `matched_setup_baselines_58323baeba0eb79f` is retained.

## Independent decision-to-account reconciliation

An independent verifier now reconciles the corrected three-arm bundle at
`evidence/research/matched_setup_baselines/matched_setup_baselines_19770241b07b5b5e/`.
It checks artifact hashes and bundle containment, identical unique decision
traces and input hashes across arms, selected-candidate eligibility, decision
to open identity and chronology, stop/target side geometry, partial and
terminal position cashflows, total realized PnL, equity endpoints/return/
drawdown, step counts, and breach counts. All three arms pass. The flat arm
has no position cashflows to reconcile; its zero matched-position count is
expected because it opens no positions. The random arm reconciles 1,854
positions (41 partial closes), and the structure-priority arm reconciles 1,169
positions (40 partial closes). Their realized net PnL is -$10,159.85 and
-$10,034.90, respectively, matching the stored equity and metrics. EMA-exit
trades may have no scalar target price; this is counted explicitly (207 random
and 90 structure-priority opens) and is not treated as missing protective
geometry. The independent packet's output checksums pass, and its focused
verifier tests pass 2/2 on the GH200 allocation.

This closes the simulator bundle's decision-to-account telemetry and accounting
reconciliation slice only. It does not establish historical candidate-to-
policy-action linkage, broker-fill parity, feed-wide event cardinality, or
economic value; Stage D and broader Stage E acceptance remain open. The
reproducible audit packet is
`evidence/research/matched_setup_baselines/accounting_reconciliation_verified/`.

## Chronological close cashflow and equity reconciliation

The reusable selected-policy lifecycle report now reconstructs account cash
from initial balance, chronological partial/final close-fill `net_pnl`, and
recorded payout withdrawals. It compares each completed-close `equity` value
with the reconstructed cash balance only when the account is flat, and it
checks payout pre-reset balances against the same running ledger, and verifies
each close `net_pnl = pnl - entry_commission_allocated`. The packet
aggregator verifies each partition's input and report hashes before publishing
the combined report. All four preserved A4 partitions match: 2,218 of 2,218
completed closes reconcile, and all 2,304 close fills satisfy the recorded
net-PnL arithmetic. There are zero payouts, no ending open positions, and no
unresolved fill/report mismatches. Reconstructed ending balances match
the saved account endpoints. This is a realized-cash transition check; it does
not reconstruct open-position mark-to-market, validate exit fees embedded in
recorded `pnl`, derive daily account risk from fills, or close the historical
candidate-to-action chain. The 2026 report partitions remain exploratory.
Reproduce with `scripts/research/analysis/evaluation/summarize_policy_trade_lifecycle.py`
for each partition followed by
`scripts/research/analysis/evaluation/build_policy_trade_lifecycle_packet.py`.

## Candidate conditional outcome packet recheck — 2026-11-04

The candidate outcome replay was checked again against the proposal packet's
recorded research configuration. Reconstructing the resolved configuration
from `config/research/trade_setup_mtf_reasoning_2m.yaml`, enabling the
candidate-entry context, and applying the recorded
`cache/trade_setup_opportunity_census` cache path reproduces the recorded
SHA-256 identity. A 10-proposal smoke replay completed with 123 bracket rows
(7 resolved and 116 unresolved); this was a config and execution-path check,
not a replacement for the full packet. The full independent packet verifier
then passed on the existing GH200 allocation in 17.10 seconds with 2,116,892
KiB peak RSS. It revalidated all 54,638 proposals and 1,067,731 outcome rows,
including the proposal/bracket key grid, chronology, training cutoff, source,
config, TickBook, status totals, and forced session-close quote coverage. The
13-file candidate outcome packet checksum manifest passes. This remains
structural verification plus a 12-row production-function replay sample, not
an independent full-row recalculation or a policy-value result. Uneven local
quote coverage remains the limiting factor for interpretation, and Stage D
candidate-to-historical-action linkage and broader Stage E parity remain open.

## Configured-profile event-count disposition — 2026-11-04

The configured-profile cardinality register now has a bounded disposition,
superseding earlier statements that left all event cardinality unqualified.
The current packet checksums pass for the candidate census, producer ledgers,
candidate proposals, matched-baseline linkage, and accounting reconciliation;
the register's 13 source/input hashes, the proposal ledger's 18 source hashes,
and the linkage audit's source hash match the current checkout.

For the selected profile, 24 of 108 candidate tuples are supported across
IFVG-retest, IFVG-unretested, PO3, and standard-deviation families. Their
488,008 active candidate-row occurrences map to 109,391 candidate-scoped
source-time identities, with zero missing required source times. The register
keeps producer units distinct: IFVG per-zone confirmations versus scalar
projections, PO3 accepted setup sequences, and standard-deviation source-leg
projections versus candidate identities. It also keeps proposal records,
baseline decision rows, opened positions, fills, and completed trades as
separate units. These measurements do not imply that cross-family or
cross-timeframe identities represent one globally unique market event.

There is no source-backed global logical-event ontology to support a single
ground-truth event count. That global count is therefore a justified no-go;
retain the producer- and candidate-scoped counts and do not synthesize a
cross-family total. Historical PPO decision-to-order/fill attribution also
remains unavailable in the scanned artifacts. The 9,137 candidate events
selected by current matched-baseline actions within proposal-validity windows
are temporal overlaps, not historical PPO linkage or proof that a specific
proposal was ordered. This disposes only the bounded event-count requirement;
the separate historical action-linkage and broader Stage D gates remain open.

## Producer-specific signal-validity disposition — 2026-11-04

The source review in `evidence/research/candidate_validity_semantics/` classifies
the active signal lifetimes for all 24 tuples in the selected local profile.
PO3 eligibility is bounded by replacement of the accepted sweep and the active
IFVG zone; IFVG confirmation/retest pulses are distinct from their zone's
invalidation and age; standard-deviation entries are band pulses anchored to a
confirmed leg that can be latched invalid. The proposal ledger still applies a
common 60-minute hypothetical-order TTL and replay does not cancel a resting
order when its producer signal becomes invalid. This TTL is an analysis
parameter, not a producer rule. The candidate outcome packet therefore remains
conditional label evidence and cannot stand in for executable policy behavior.
This closes source-semantic classification for the selected profile only; a
shared executable validity/cancellation contract, other configurations, and
historical PPO decision-to-order linkage remain open. No proposal or outcome
packet was rebuilt from this review.

## Supplemental archived trace-content search — 2026-11-04

The reusable `scripts/research/analysis/evidence/search_archive_trace_contents.py`
now searches bounded text prefixes inside local ZIP archives without extracting
members. It inspected all 577 archives under `/scratch/work/nguyenl37` and read
11,138,053 prefix bytes from 5,638 CSV/TSV/JSON/JSONL/YAML/text/log members.
It found zero candidate/action/order trace-field leads, zero member read
errors, and 16 unreadable archives (ten small pytest fixtures and six empty
or placeholder MTF benchmark checkpoint files). The report and scanner hash are recorded in
`evidence/research/historical_variant_screen_recoverability/` and
`evidence_manifest.json`.

This narrows, but does not close, external trace recovery. The scans did not
parse Parquet or SQLite schemas, inspect other binary member content, read text
beyond the first 64 KiB, or follow directory symlinks. A 16-byte probe over all
42,902 readable file members found no Parquet/SQLite magic. It found 1,437 ZIP
containers (1,434 `.pth`, one `.vsix`, two nested `.zip`). The reusable
`search_nested_archive_traces.py` follow-up inspected all 1,437 containers
within an 80 MiB per-member limit and found zero candidate/action/order headers
in supported text members. Sixteen outer archives remain unreadable.
Checkpoint payloads were not deserialized, and archive members were not
extracted or hashed. A separate
symlink inventory recorded 5,817 links across scratch and detailed the 41
links under the project, its archive, and the historical academic workspace
name. Existing research links resolve to already-scanned project data/output
trees; three archived data/cache links target the absent
`/scratch/work/nguyenl37/Aalto_MS_Thesis` paths. The report is
`evidence/research/historical_variant_screen_recoverability/scratch_symlink_inventory.json`.
See
`evidence/research/historical_variant_screen_recoverability/nested_archive_trace_search.json`.
The current provenance verifier still marks 132 declared run artifacts missing.
A follow-up hashed all 42,902 direct file members (21.67 GB uncompressed) in
the 577 ZIP archives under the same scratch root. It found no byte-identical
artifact; the same 16 ZIP files could not be opened. No artifact was recovered,
so all 132 remain missing in this bounded search. The result and reusable
scanner are in
`evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/`.
It does not recursively open nested ZIP/checkpoint payloads.
Preserve the external-recovery gate as open until remaining known
backups/manifests and campaign content identities are reconciled; this
bounded search is not global absence proof.

## Local timestamp and quote-chronology disposition — 2026-11-04

`evidence/research/market_data_quality/local_timestamp_and_quote_chronology_limits.json`
cross-checks the selected campaign's four hash-verified tick inputs against
the existing raw-quality and production TickBook carry-forward reports. The
reusable `scripts/research/analysis/market_data/verify_local_timestamp_limits.py`
passes: 172,290,383 rows, 329,471 adjacent millisecond tie groups (328,918
changed-quote groups, 553 groups with a missing quote, and zero identical
quote groups), 371,390 rows with a missing/nonpositive side, all source rows
retained, and zero dropped after carry-forward. The packet also hash-links the
configured `Etc/GMT-3` carrier, declared `ftmo_mt5_us_dst` model, TickBook
source-order tie-break, and session-feature conversion that raises for
ambiguous/nonexistent reconstructed New York wall times.

This resolves the local implementation and observed-data subquestion with a
bounded no-go: equal-millisecond source order is deterministic but does not
establish true sub-millisecond chronology, and carried sides do not establish
simultaneous bid/ask availability. Repository configuration does not
independently authenticate the export's timezone or authoritative schedule.
Provider, license, and external-calendar research remain excluded by the user.
The distinct full pipeline-denominator, historical policy-linkage, and
simulator-parity gates remain open.

## Full-train environment performance profile

The reusable `scripts/research/benchmarks/measure_env_memory.py` now records
source/config identity and preparation, worker-startup, and vector-step timings.
On the existing aarch64 GH200 allocation, the full 2025 train split contained
351,432 rows per configured symbol/timeframe split and ran with CPU affinity
0–47. One measured pass took 128.65 seconds overall: 12.48 seconds to load
config/data/features/split/TickBook, including 8.11 seconds for TickBook build
and coverage. Worker create/reset took 9.08/31.68/62.16 seconds at 2/8/16
workers; the 256-step vector phase delivered 834/2,582/4,489 environment
steps/s. Process-tree PSS was 20.5/49.4/88.0 GiB and cgroup memory was
21.4/50.3/89.0 GiB. The report and exact run fingerprint are
`evidence/research/performance/gh200_environment_full_train_pipeline_profile.json`
and `environment_resource_profile_manifest.json`.

A separate 32-worker measurement on the same full split used 32 of the 48 CPU
affinity slots and completed in 144.45 seconds. Worker create/reset took
124.57 seconds; the vector phase delivered 7,167 steps/s at 165.0 GiB
process-tree PSS and 166.3 GiB cgroup memory. See
`gh200_environment_full_train_profile_32env.json` and the performance README.

A current-source matched comparison now profiles frame-backed and shared
environment-bundle workers on the same full train split in GH200 job
`21390062`. The base config, input identity, benchmark-source hash, and worker
counts match. At 2/8/16 workers, process-tree PSS was 20.5/49.4/87.9 GiB for
frames and 5.6/6.2/7.0 GiB for the shared bundle; throughput was
818/2,546/4,369 versus 838/2,510/4,414 steps/s. Bundle worker startup was
1.7–3.5 seconds versus 9.8–60.9 seconds. The 3.06 GB bundle was built once;
the existing bundle-equivalence module passes 16/16 in the same allocation.
This is measured evidence for a substantial memory reduction with similar
environment throughput. The bundle run preceded the frame run, so feature-cache
preparation times are not compared. Learner, checkpoint, full evaluation,
GPU-use, report, and archive stages remain unmeasured; Stage L is not complete.
See `evidence/research/performance/bundle_worker_scaling/`.

This is a current-source environment component profile. It did not run learner
updates, checkpoints, frozen evaluation, charts/reports, archive writeback, or
CUDA work, so it is not the Stage L end-to-end performance acceptance run.
Training and policy replay remain gated by unresolved upstream science checks.

## Synthetic feature-event timing examples — 2026-11-04

The reusable
`scripts/research/analysis/features/plot_synthetic_entry_timing_examples.py`
now renders seven explicit-UTC synthetic diagrams: PO3/IFVG confirmation and
next-bar fill, invalid same-bar entry, previous-session gating, optional
confirmed retest, swing visibility after right-bar confirmation, order-block
overlap followed by later-close retest confirmation, and SMT forward-fill when
a secondary bar is missing. The focused generator test passes and the packet
checksums verify at
`evidence/research/feature_causality/synthetic_event_timing_examples/`.
These examples explain selected source/test contracts; they are not market
observations and do not close all active-feature causality or runtime gates.

## SMT missing-secondary-bar correction — 2026-11-04

The synthetic missing-bar regression exposed that forward-filled secondary
OHLC rows were being counted as bars by the SMT pivot detector, suppressing a
paired divergence when an observed right-side bar existed after the gap.
`smt_divergence()` now detects pivots on the observed secondary source rows and
maps each confirmation to the first primary row at or after its timestamp;
forward-fill remains for close-based correlation and spread. The new test
reconciles the divergence with and without the missing confirmation row, and
the source-linked feature matrix records the corrected contract. Feature cache
identity is now `v38-smt-observed-pivots`.

The regenerated 215-row matrix has SHA-256
`fee1431cbed28f2285df171e6d5a7779c53ed5bcfc9154e364a99f8e4622440c`; all 96
public feature functions, 108 setup flags, and 11 upstream time/session
functions remain represented with no unassessed metadata fields.

Focused SMT unit tests pass (5/5), including a timestamp-offset regression that
proves a secondary pivot confirmation is not backdated to an earlier primary
row. The MTF feature-builder integration case
passes (1/1) on synthetic bars, timing-example tests pass (1/1), and the cache
version documentation contract passes. The prior 57/57 all-profile prefix
result records the previous SMT source and is no longer current-source evidence
for profiles that use SMT. Rerun it on an eligible GH200 allocation before
closing Stage D; no real-market output change is claimed yet.

To reduce that rerun's repeated data preparation, the reusable prefix auditor
now caches cleaned, price-grid-quantized, session-labeled M1 bars by input path,
timezone, NY session end, and price-grid increment across effective feature
groups. Cache hits return deep copies so downstream feature builders cannot
mutate shared inputs. The focused script suite passes 20/20, including tests
that each cache-key dimension invalidates stale transformed bars, plus one raw
load and independent returned frames. This is a
source-level work reduction; the real-market prefix result still requires the
current-source GH200 run.

## Feature normalization fit scope — 2026-11-04

Source review confirms the configured feature matrix uses `rolling_zscore`
with the supplied train mask; optional D1 technical normalization maps that
mask to source bars whose close is available by the training cutoff; and
walk-forward feature construction uses the `frozen_fold` mode so validation
rows cannot update fitted mean or scale. The focused normalization/cache suite
passes 11/11, including validation-poisoning and D1 source-timeframe regressions.
Feature thresholds are configuration-owned, and the reachability quantile is
computed from prior closed sessions. This establishes current synthetic/source
fit-scope behavior only; it does not close real-profile prefix acceptance,
observation masks, or a project-wide audit of model pretraining.

The prefix auditor now records per-group input/preparation, full-build,
prefix-build, comparison, and total elapsed times, with raw-load and
preprocessed-cache counters. These are instrumentation fields for the next
run; no new market timing or performance claim is available yet.

The reusable launcher
`scripts/research/analysis/features/run_real_market_feature_prefix_audit.sh`
requires an existing Slurm allocation on gpuarm1/gpuarm2, runs four direct
Python shard processes without child `srun` steps, requires exactly one
allocated GH200 with at least 48 CPUs, 512G RAM, and a 12-hour limit, preserves
logs outside the repository, and merges only after every shard succeeds.
`bash -n` and launcher contract tests pass 7/7, covering missing allocations,
wrong nodes, excess GPUs, and undersized resources. On 2026-11-04, the
launcher preflight was adapted to this Triton Slurm version, which reports the
allocated GPU under `AllocTRES` rather than `Gres`; the allocation confirms
exactly one GH200, 48 CPUs, 512G, and 12 hours. The all-profile market-data run
is now active as job `21390062` on `gpuarm1`; its four shard processes write to
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/real_market_feature_prefix_current_source/`.
At the `00:30:30` Slurm runtime check, 14 of 19 profile groups had completed
(shards 0–3 had 4/2/4/4 completed groups). Shard 3 exited 0 and emitted a
125,404-byte report with 12 checks passed, zero failed, and four feature
profiles; its SHA-256 is
`39e085c2a7a4ca41f25567d8a24bc4226c300f4d81a0bd1a3061b027cb547069`.
Shards 0–2 remained active; shard 0 completed the large `base/default` group,
and shard 1 was rebuilding its next group. Shard 3 completed its four assigned
groups and produced its report. No merged audit existed. This is partial shard
evidence, not a completed all-profile audit or final feature result.

## Negative-result handoff prefix-status correction — 2026-11-04

The release `FINAL_READINESS_REPORT.md`, `README.md`, `KNOWN_LIMITATIONS.md`,
and `FUNCTION_TEST_EVIDENCE_INDEX.csv` now classify the 57/57 real-market
prefix result as historical evidence for its recorded source snapshot. The
later `v38-smt-observed-pivots` correction means the all-profile current-source
GH200 rerun remains open; the report no longer claims that the old feature
hashes match current source. This corrects release wording and does not close
the Stage D gate. The release manifest was refreshed and verifies 26 release
files plus 207 source/evidence files; the focused manifest tests pass 2/2.
Strict Sphinx work remains deferred until research stages are complete.

## Selected campaign artifact integrity — 2026-11-04

The reusable `scripts/research/analysis/evidence/verify_selected_campaign_artifacts.py`
now verifies the selected P6 campaign fingerprint, its 1.29 MB source snapshot,
the embedded manifest, and all 590 source-file hashes. It also rehashes both
archived run manifests, configs, and final checkpoints. The campaign snapshot
commit `b93642a` is an ancestor of each run-source commit `0d056dc`, and both
run commits are ancestors of current HEAD. The report is
`evidence/research/releases/negative-evidence-readiness/selected_campaign_artifact_integrity.json`;
four focused tests pass. This is byte-integrity evidence, not model replay.
Each run manifest records one dirty source file, so its full source-tree hash
remains unknown. The feature cache is unavailable at its recorded path and was
not rehashed. Raw input identity remains covered by the separate 39-file
campaign audit. The distinct `replacement18` frozen-checkpoint report is not
used as P6 checkpoint evidence. Campaign evidence inventory remains open for
the unresolved dirty-tree/cache and broader run-inventory gaps.

## Candidate outcome arithmetic verification — 2026-11-04

The candidate-outcome verifier now independently checks every resolved row's
entry and exit prices against exact source TickBook events and recomputes net R
from the stored event prices, selected stop, execution cost, and contract size.
Two focused fixture tests pass, including long/short fills and injected source-
event/return mismatches. This verifies resolved-row arithmetic only; it does
not independently replay entry selection, protective triggers, or censored and
unresolved statuses. The full-packet run on the existing GH200 checked all
259,358 resolved rows: fill and exit source-event prices matched, all net-R
recalculations matched, and there were zero mismatches. Its TickBook hash
matches the packet and all 14 output checksums pass. The verifier's explicit
full-row replay flag remains false because order selection, trigger timing, and
non-resolved statuses were not independently replayed. This closes only the
resolved arithmetic subgate; Stage E and candidate-outcome replay acceptance
remain open.

## Real-order risk boundary — 2026-11-04

The bundled MT5 `RiskManager` reports
`supports_training_account_loss_guardrails=False`: it enforces position-stop
risk but has no trusted restart-safe daily/max-loss account state. The RL and
multi-symbol robot constructors reject real-order mode without an explicit
manager that advertises those guardrails, and the RL robot checks again before
opening. The two focused single-/multi-symbol rejection tests pass. This is a
verified fail-closed boundary, not training/live parity evidence. Given the
current local evidence has no training-equivalent account/session provider,
real-order parity is a bounded no-go for this plan; offline simulator evidence
does not authorize a live-mode claim. Broader Stage E accounting and simulator
lifecycle checks remain active.

## Superseded v38 all-profile feature-prefix audit — 2026-11-04

The earlier GH200 rerun after `v38-smt-observed-pivots` completed across all 19
configured feature-profile groups with 57/57 passing cutoffs. That report is
superseded for current-source acceptance by the later v39 validity-semantics
changes below; preserve it as historical evidence only.

## Recorded v39 feature-validity and prefix audit — 2026-11-04

The source review added an explicit `-1` outside-session `po3_phase` value
(active phases are 0/1/2), so paired `session_progress` distinguishes clipped
pre-/post-session values from active boundaries. Valid zero-range candles now
produce a zero `wick_ratio`; missing OHLC inputs remain nonfinite. The cache
identity is `v39-feature-validity-semantics`. The 130-profile warmup audit
completed 23 observation groups and 15,571 feature rows with no group errors.
The triage summary reports 1,291 feature/timeframe pairs: 206 with interior
missingness, 463 with leading-only missingness, 620 with none, two unavailable
throughout, and 219 finite-zero collision pairs. The source-semantic crosswalk
was regenerated for all 1,291 pairs and 41 producers. Eight leading nonfinite
M1 PO3 rows per feature (one in each affected group) are consistent with the
normalizer's two-observation standard-deviation warmup.

The v39 real-market prefix audit reused GH200 job `21390062`. The strict
four-shard merge covers all 130 profiles across 19 feature-builder groups and
passes 57/57 cutoff comparisons with zero failures and zero maximum absolute
delta. It records 78 source hashes and four local input hashes. This closes
the v39-snapshot real-market prefix-invariance check, not broader causal
feature acceptance: event cardinality, unsupported profiles, feature-level
validity observability, and historical proposal-to-action linkage remain open.

## IFVG missing-ATR distance correction — 2026-11-04

IFVG bull and bear zone distances now retain the 5.0 sentinel when ATR is
unavailable; they no longer divide raw price distance by a unit-price fallback.
The focused current-source PO3-state module passes 23 tests on the existing
GH200 allocation, scoped Ruff checks pass, and the feature cache identity is
`v40-ifvg-missing-atr-distance`. Evidence and source/test hashes are in
`evidence/research/feature_causality/ifvg_distance_atr_availability/`. The
five-group current-source subset passes all 15 registered cutoff comparisons;
the final 130-profile rerun passes all 57 comparisons, and all recorded source,
inventory, and local-input hashes match the current state. Prefix invariance is
closed for this inventory and these three cutoffs; broader event identity,
publication timing, execution, label, and model-selection gates remain open.

## Provenance byte verification — 2026-11-04

The reusable `scripts/research/analysis/evidence/verify_research_provenance_bytes.py`
rehashes manifest-declared files, validates full archived source snapshots,
recognizes artifacts relocated beneath their original campaign directory by
matching declared SHA-256, and distinguishes unavailable historical source
bytes from a true current-byte mismatch. It now also checks hash-addressed
source files against the exact source commits of consuming runs, promoting a
source node only when every linked commit contains the declared blob. Eight
focused tests pass. On the
existing one-GH200 allocation, all 49 manifests and 45 source snapshots verify;
421/553 relocated run artifacts found in the approved archive match their
declared hashes. The report records no observed byte mismatch or blocked path:
`evidence/research/releases/negative-evidence-readiness/PROVENANCE_BYTE_VERIFICATION.json`.

Stage M remains incomplete: 132 declared run artifacts are absent from the
approved archive, four historical data inputs are unavailable, and 15
historical source-file nodes remain unresolved. Two additional source nodes are
now verified from every linked run commit; partial or mismatching commit blobs
remain failures. No byte mismatch or blocked path was observed. These are
preservation and reproduction gaps, not positive research evidence. The
verifier does not discover unmanifested outputs. Provider, license, and
external calendar checks remain out of scope by user direction.

## Guardrail fill-timing parity — 2026-11-04

A consolidated Stage E characterization run exposed one reproducible mismatch:
the environment timestamped guardrail closes at the next bar open but priced
them from that bar's close, while the event-driven backtest used the open. The
environment now prices the guardrail fill from the next bar's open quote. This
removes the lookahead price and aligns the two execution paths. The regression
was included in the five-file focused parity batch; after the fix, 56/56 cases
pass, including multi-target partial exits, risk lifecycle ordering, no-action
account state, and the local tick trace. Touched-file Ruff and `git diff --check`
pass. This closes only the bounded next-open guardrail parity case;
complete simulator/accounting parity remains open.

A second focused execution/accounting batch passed 39/39, covering executable
market and tick quotes, seeded latency and fail-closed tick waits, exactly-once
partial-fill commissions, repeated payout cycles, and account-breach cycles.
The test sources remain the reusable specifications; output is preserved at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/accounting_suite_current/pytest.log`.
Financing treatment, the full cash/equity/position/report ledger, and broader
checkpoint/replay determinism still require explicit coverage.

## Consolidated paired lifecycle characterization — 2026-11-04

The follow-up batch reran seven focused integration modules together on the
existing GH200 allocation: account transitions, multi-target protective
lifecycle, risk lifecycle, repeated payouts, fill accounting, broker quote
parity, and local TickBook traces. All 69 tests passed in 1.01 seconds. The
hash-identified output and exact test command are recorded in
`evidence/research/simulator_execution_parity/paired_lifecycle_characterization/`.
This is a consolidated bounded regression snapshot, not new proof for every
case in the plan. Financing, historical candidate-to-action linkage, complete
cash/equity/report reconciliation, and external tick chronology remain open.

## Active feature-family regression batch — 2026-11-04

Fourteen focused source and research modules passed 137/137 tests in 24.49
seconds inside the same allocation. The batch covers swing and order-block
semantics, FVG/IFVG and PO3 state, SMT alignment, MTF completed-window masks,
candidate event projection, assembled-prefix behavior, and observation
validity classification. Test and production-source hashes are recorded in
`evidence/research/feature_causality/active_family_contracts/`. Two existing
PyTorch transformer nested-tensor warnings remain. This closes these bounded
regressions; it does not complete profile-wide event semantics or add
feature-level validity masks to policy tensors. Historical action linkage also
remains unresolved.

## Observation input nonfinite handling — 2026-11-04

The observation builders used `numpy.nan_to_num` with only a NaN replacement.
Positive and negative infinity therefore became extreme finite `float32`
values. A shared simulation-local sanitizer now maps all three nonfinite
classes to zero in M1 sequences, closed higher-timeframe windows, and legacy or
per-date pre-NY VAE inputs. Observation keys, widths, and temporal masks are
unchanged. The focused observation and schema batch passes 32/32 tests; scoped
Ruff and `git diff --check` pass. The code and exact validation packet are at
`evidence/research/feature_causality/observation_value_sanitization/`.
This prevents extreme invalid inputs, but zero-fill still cannot distinguish
missing from valid-zero features; the per-feature validity-mask gate remains
open.

## Versioned sequence feature-validity channels — 2026-11-04

The environment now has a default-off `env.feature_validity_channels` option.
When enabled, M1 and completed higher-timeframe policy sequences carry all
sanitized feature values followed by matching finite-value indicators. A real
zero has value 0 and validity 1; a missing or nonfinite feature has value 0 and
validity 0. Padding keeps both channels at zero and leaves the existing
temporal mask separate. Default-off observation shapes and the values-only
checkpoint schema remain unchanged. Enabled runs record a distinct sequence
schema, and checkpoint reanalysis rejects a values-only/schema mismatch.

Four focused modules pass 79/79 tests, including M1 and MTF behavior, valid-zero
distinction, padding, config propagation, and schema mismatch. An additional
inference-only check passes with all four registered MTF encoders consuming the
widened sequence inputs and producing finite actions (4/4); no model training
or weight updates were performed. Scoped Ruff and `git diff --check` pass.
Output and current source/test hashes are in
`evidence/research/feature_causality/sequence_feature_validity_channels/`.
This closes the bounded sequence-input representation gate only. No policy has
been trained or evaluated with this new layout; the survival qualification
overlay now requires it for future policy training. VAE context remains on its
separate schema, and research/economic gates remain subject to their own
acceptance criteria.

## Timeframe validity and padding semantics — 2026-11-04

A joined current-source batch of six focused modules passes 119/119 tests.
Coverage spans M1 and all eight HTF sequence tensors, observed all-zero rows,
missing/nonfinite feature indicators, left-padding, empty HTF streams, masked
payload invariance, registered encoder acceptance of versioned widths, and
checkpoint schema mismatch. The test batch ran in 42 seconds on the existing
GH200 allocation. Exact command, test output, and source hashes are recorded in
`evidence/research/feature_causality/timeframe_validity_padding_semantics/`.

This closes tensor-level validity-channel, temporal-mask, and padding behavior
for the tested inputs. It does not prove that upstream producers preserve
warmup as nonfinite: feature producers that fill warmup with finite zero remain
ambiguous to finite-value channels. No policy was trained with the opt-in
validity layout, and VAE/per-feature producer warmup, causal/economic validity,
and historical decision linkage remain open.

## Current-source observation validity and producer crosswalk — 2026-11-04

The 130-profile training-split audit was rerun against the current feature
configuration inventory (`f42df9e3e12116d9de47bff5281fa854756f0a0da517d1d2c42817ce45c1eb2a`).
All 23 effective observation groups completed with zero failures, producing
15,571 feature/profile rows; the runner verified that its source set did not
change during the run. Its output checksums pass. The regenerated priority
summary and producer crosswalk also pass their output checksums and use the
current feature-causality matrix (`eeb771ebed9100144ee4de78d2b72e0642f1a3fdd0637dc7cdeeddcaf84e1b87`).

The crosswalk maps all 1,291 timeframe/feature pairs to 41 reviewed producer
contracts. The measured classes are 620 with no missing values, 463 with
leading-only missingness, 206 with interior missingness, and two unavailable in
all measured profiles; 219 pairs have both nonfinite values and finite zeros.
This closes current-source measurement and source-contract mapping for the
M1/HTF sequence profiles. Finite-zero collisions remain explicit, and the
default-off finite-value channels do not resolve upstream zero-filling. The
results do not establish policy use or economic validity. The separate VAE
pre-NY path is now measured on the same local 2025 training interval. Its
186-step configuration prepends at least one zero row to all 260 daily
sequences, while the configured reconstruction loss has no timestep-validity
mask. The configured 44-sequence `.npy` training array has 228 leading all-zero
rows consistent with padding (not distinguishable from valid zeros), no
date/session identity, and the VAE trainer randomly partitions it 70/15/15
without a chronological key. The VAE candidate therefore has a
bounded no-go disposition until a versioned mask, dated provenance, and
chronological fitting contract exist; this audit does not claim an economic
result. Canonical policy training now rejects `--use-vae`, and standalone VAE
preparation rejects the current input path before reading the undated array or
creating output artifacts. Admission regressions are in the consolidated
release suite and remain unrun. Evidence and reproduction are in
`evidence/research/vae_input_validity/`. Unresolved source-clock details and
broader causal and historical-linkage gates remain open. Current artifacts are under
`evidence/research/feature_causality/observation_validity_across_profiles/`,
`observation_validity_priorities/`, and `observation_validity_semantics/`.

## Early manual reset semantics — 2026-11-04

`TradingEnv.reset()` starts a new episode and clears its account, position,
pending entry, payout/breach counters, and episode ledger. Calling it before a
terminal transition aborts the active episode; it does not create a market
close, payout, or breach event. A focused source-current test opens a position,
resets early with the same seed, and verifies that no episode state carries
over and the new observation matches a fresh environment; it passes 1/1 with
touched-path Ruff checks. Configured data-end and `max_episode_steps` boundaries
use `_record_step_accounting` to liquidate before returning termination or
truncation. Evidence is in
`evidence/research/simulator_execution_parity/early_reset_abort_semantics/`.
This defines manual reset as an abort and keeps it out of realized-result
comparisons. Full-ledger/daily-risk reconciliation remains open. **Bounded
no-go:** deterministic checkpoint replay for the historical A4A/A4B runs is
not supportable from the approved local evidence: their exact feature cache is
unavailable, current feature reconstruction changes model inputs, and the
current no-new-Slurm direction forbids another replay. Preserve the recorded
single-run ledgers without claiming repeatability. Any future
survival-qualification checkpoint must use its hash-verified inputs and pass a
corrected deterministic repeatability comparison. The selected A4A/A4B run manifests both reference
`US100.cash_features_v24-native-source-timeframes_8a037e1d6633f0c4.parquet`,
with recorded file SHA-256
`4a97305f1d4b21c3eca61fab78ad76ea8ec09f586c058094d81877ec8b82aeca`. That
exact cache file is missing from the active checkout, its cache tree, the
preserved research archive, and the local scratch search. Rebuilding with
current feature semantics would not reproduce the model's training inputs and
must not be reported as historical deterministic replay. Recovering that exact
cache, or a byte-identical copy, is required to close this checkpoint-backed
gate; otherwise it needs a bounded no-go disposition.

## Direct local-file hash recovery — 2026-11-04

The reusable
`scripts/research/analysis/evidence/reconcile_missing_artifacts_from_filesystem.py`
extends the bounded ZIP-member search by finding ordinary files with the same
basenames as the 132 run artifacts still marked missing in the current
provenance byte report. It hashed 585 candidate files (3,746,889,603 bytes)
under `/scratch/work/nguyenl37`, with zero read errors and zero SHA-256
matches. All 132 targets remain unresolved. The report and checksummed packet
are in
`evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/`.

The pass does not inspect ordinary files under other roots, differently named
files, nested ZIP/checkpoint payloads, or the 16 ZIPs that failed archive
indexing in the earlier direct-member pass. It adds evidence but does not prove
global absence; Stage A/Stage M recovery remains open. The reusable scanner's
focused tests and the existing ZIP scanner tests pass together (6/6), with
touched-path Ruff and `git diff --check` passing. The test launcher uses
`.venv/bin/python -m pytest` because the `.venv/bin/pytest` shebang points to a
removed secondary checkout. The negative-result release manifest now declares
the local-file report, scanner, and tests; its 26 content and 224 source/evidence
hashes verify.

## Reconciliation of recorded equity and historical gross-loss evidence

The reusable
`scripts/research/analysis/evaluation/audit_recorded_equity_series.py`
independently recalculates endpoint return and maximum drawdown from the saved
`equity.csv` series, validates strict timestamp order and finite rows, and
compares the results with `metrics.json`. The four selected A4 training/testing
reports all match: each training series has 99,493 observations and each
testing series has 79,070, with no invalid rows or chronology failures. The
reports preserve the source input hashes at
`evidence/research/simulator_execution_parity/equity_series_reconciliation/`.

This verifies numerical summaries against their serialized equity series only.
It does not independently reconstruct mark-to-market equity from quotes,
reconcile daily risk state or cashflows to fills, or validate policy value.
No policy replay or training was performed. The equity verifier also compares
each `daily_loss` breach row with its exact equity sample and reads the
configured limit only when its source config hash matches the reanalysis
manifest. In A4A/A4B training, both March 6 event rows equal the same-date
equity minimum. The separate first-sample-to-daily-minimum screen records
$3,004.28/$3,389.32 declines, but those are not gross realized-loss counter
values. Its comparison now distinguishes equality from breach: an exactly
$5,000 observed decline is at the floor and allowed; a strict decline greater
than $5,000 is a crossing. A synthetic boundary regression covers both cases,
and all four hash-linked A4 reports were regenerated; none has an observed
calendar-date decline at or above $5,000.

Source inspection confirms that the historical gross realized-loss counter
accumulates the absolute negative realized PnL passed to
`AccountState.close_trade`. The reusable
`scripts/research/analysis/evaluation/audit_gross_realized_loss_counter.py`
reconstructs this arithmetic from saved close-row `pnl` values and compares
threshold crossings with recorded breach events. Both training ledgers cross
the configured $5,000 gross-loss threshold on March 6: A4A at 17:15:29 UTC and
A4B at 17:31:12 UTC. Their recorded events follow at 17:17:00.118 and
17:33:00.078 UTC, respectively; gross realized loss through those event fills
is $5,017.66 and $5,399.25. Each run has one source-session crossing (session
47) and one matching event. The testing partitions contain no such events.

The equity auditor now maps all saved timestamps to verified supplied M1 date
labels and applies the current 5% initial-equity session-net rule to the
preserved observations. The source row counts, unique timestamps, and bounds
match the processed-bar manifests; all 357,126 equity observations resolve to
session IDs. Exact M1 timestamp matches account for 354,661 observations; the
remaining sub-bar execution times resolve by their verified local date, with
zero unmatched dates. No sampled session reached the $5,000 floor across 259
training sessions per arm and 205 report-period sessions per arm. The largest
observed decline was $4,972.04 for A4A on 2025-04-04; on the gross-counter
event session 47, observed declines were $3,004.28 / $3,389.32 for A4A / A4B.
The dedicated report is
`evidence/research/simulator_execution_parity/equity_series_reconciliation/session_equity_daily_loss_screen.md`.

This is an observed-path screen of historical runs that blocked later entries
under the gross realized-loss counter. It does not reconstruct the trades that
the current session-net rule would have permitted, every tick-level equity
excursion, cashflows against fills, or policy value. The current screen closes
only this bounded historical daily-equity calculation; full Stage E accounting,
cross-engine lifecycle parity, and determinism gates remain open. The equity
audit tests pass 11/11 after adding strict-below boundary coverage, the ledger audit test passes 1/1, scoped Ruff and
`git diff --check` pass, packet checksums verify, and the release registry
verifies its current content and source/evidence hashes.

## Structural action and entry contract — 2026-11-04

Current-source checks for no-trade/inactive setup decisions, delayed decision-ID
carryover, structural long/short entry behavior, invalid direction, and forced
structural-stop execution first passed 76/76 across three focused modules. One
stale test horizon was corrected: the delayed fill occurred on the terminal
step, so the environment correctly liquidated before the test inspected the
position; the test now leaves one nonterminal step, with no production behavior
change. A follow-on 98/98 batch adds a fail-closed regression for unknown `M99`
source labels in both stop and target menus, plus exact-$100,000 payout
principal-boundary coverage. Payout eligibility already requires a target above
operating capital, and payout amount is clamped to realized balance minus
operating capital. The user rule is explicit: neither losses nor principal can
be withdrawn. The run log, metadata, and current source hashes are in
`evidence/research/simulator_execution_parity/structural_action_contract/`.
Exhaustive all-candidates-empty-mask parity, historical action linkage, and
authoritative quote chronology remain open. That packet preserves its original
test scope; its current-scope addendum links the later mask and limit
implementations.

## Setup-mask and event-backtest action boundary — 2026-11-04

A focused paired characterization first showed that with all setup-candidate
feature bits zero, `TradingEnv` rejects a selected M1 FVG-retest setup while the
default scalar `run_backtest` action `+1` opens a long. The user chose an
opt-in mask-aware action path. `run_backtest(trade_setup_actions=True)` now
passes the canonical setup mask to the policy, decodes the shared
`TradeSetupActionSchema`, rejects masked candidates, and preserves selected
candidate identity through immediate and delayed opens. `NO_TRADE` holds an
open position. The default scalar API and its behavior remain unchanged.
The five-module compatibility batch passes 82/82, including the mask cases,
no-action account state, scalar execution/entry, and repeated payout backtest;
scoped Ruff passes. Outputs and source hashes are in
`evidence/research/simulator_execution_parity/setup_mask_engine_boundary/`.
This closes only candidate-mask enforcement and identity. The mask-aware
callback receives the default `TradingEnv` observation branches: a
session-clipped, left-padded `seq`, its `seq_mask`, normalized account-state-v1,
and the candidate mask. A follow-up added explicit account-state-v2 and
repeated-payout-v3 selection through `observation_schema`; results record the
resolved account/action schemas. V2/v3 fields include account limits,
remaining risk capacity, protective levels, TP progress, management modes, and
position age. Entry-state visibility fails closed because the event backtest
has no entry-state machine. The 46-test action/observation batch passes,
including expected-vector comparisons for v2 and v3.

The setup-policy callback now also has opt-in parity for the environment's
completed-D1 regime vector/mask, causal closed multi-timeframe windows, and
per-feature validity channels. A same-index integration comparison checks all
emitted arrays against `TradingEnv`, including validity and padding behavior;
the returned metadata records the regime schema, timeframe windows/calendar,
feature columns, and channel selection. The same optional path also accepts the
frozen VAE plus per-date or legacy pre-NY inputs and emits the same latent mean
as `TradingEnv`; the parity test checks this branch too. These switches require
the schema-aware setup callback and do not affect scalar callers. Entry-state
visibility remains fail-closed as a scoped no-go for this event-backtest
bridge: that engine does not run the entry-state lifecycle, while supported
checkpoint evaluation uses `TradingEnv`. Duplicating only its state encoding
without the evidence/transition machine would create a false parity claim.
An additional unrun setup-mask fixture compares every observation in a
multi-decision all-inactive rejected-entry trace and the first observation with
an active candidate. Keep the wider parity gate open until the consolidated
implementation batch runs.
Historical PPO action linkage, broader account lifecycle parity, and
authoritative quote chronology remain open, so this does not establish full
cross-engine parity.

## Agent-selected market and limit entries

The user requires the policy to choose between two entry execution ideas:
market entry under the existing market-fill contract, or a resting limit entry
whose price and time-to-live (TTL) are selected by the policy. Do not treat
`fill_latency_bars` as a limit order; it only delays a market fill. The next
action contract must represent an execution-type choice and, conditionally for
limit orders, bounded price and TTL controls. `TradingEnv` and the mask-aware
event backtest must consume the same versioned action schema and preserve order
submission, executable-quote fill, expiry/cancel, and account-failure events.
A limit that does not fill before expiry produces no position. Limit fills must
use observed executable quote chronology; OHLC touch alone is not fill
evidence. Evaluation must fail closed if it requests limit actions without a
quote source that can establish the fill rule. Keep fill assumptions,
parameterization, and TTL range explicit in config/provenance, and compare
conservative fill assumptions before model selection or training.

Implementation is now present in both `TradingEnv` and the mask-aware event
backtest. A versioned action selects market or limit and exposes bounded ATR
offset and TTL coordinates. TickBook quotes establish limit fills; exact-touch
versus trade-through is configurable for conservative sensitivity, and
unfilled orders expire without a position. Missing TickBook data fails closed.
Seven integration cases cover market selection, cross-engine limit fill
behavior, expiry without an OHLC-only fill, and the environment's single
pending-order lifecycle, with missing TickBook data blocking limit orders but
not market orders. The focused 147-test batch passes with scoped Ruff checks.
This closes the limit
entry implementation box, while Stage E's broader risk/geometry/exit/observation
parity and the conservative fill-assumption comparison remain open. It does
not authorize a new policy campaign while the selected P6 arms fail the hard
survival gate.

The event backtest now applies the selected stop/target geometry to the opened
position, including multi-target fractions and the EMA-21 exit after its
one-risk favorable-travel threshold. Review of EarnForex's Apache-2.0
PositionSizer source at commit `dadf3d5c869c34cac40db3fb6858b188cf101a25`
confirmed its portable sizing principles: value stop distance in account
currency, include round-trip costs, respect min/max lot and volume-step bounds,
and size pending orders from their intended entry price. Both simulators now
size and anchor protection at the requested limit price while recording PnL
from the actual executable fill. No source code was copied. The fill audit then found that modeled
adverse slippage was applied after backtest sizing and could worsen a resting
limit past its price cap. Both `TradingEnv` and the event backtest now apply
market tick slippage before geometry and sizing, and do not apply adverse
market slippage to limit fills. The focused geometry, order, account-parity,
tick, and sizing batch passes **169 tests** with scoped Ruff checks. The market
and limit fills are still simulator models: no broker queue position or
authoritative local feed chronology is inferred, and Stage E plus the wider
research gates remain open.

The event-backtest setup action now decodes its continuous risk coordinate
through an explicit risk-fraction range; pending market and limit orders retain
the risk choice made at submission. For structural-stop sizing, both the
environment and event backtest reserve modeled round-trip commission and
adverse stop slippage inside the requested risk budget, size market entries
from their modeled executable quote and limit entries from their intended
price, round size down to the configured broker volume step, and reject a
budget that cannot support the minimum lot. The shared calculation accounts
for contract and point value; `risk.lot_step` defaults to `0.01` and is passed
through config-driven environment and backtest construction. This applies the
portable sizing concepts inspected in EarnForex PositionSizer (cash risk
budget, stop distance valued through contract and point value, round-trip
commission, adverse stop-slippage reserve, broker lot bounds, and downward
volume-step rounding); no source code was copied. The pinned MQL5 source uses
stop distance times symbol tick value divided by tick size plus two one-way
commissions, and optionally caps volume by available margin. Its optional
spread-adjusted stop distance widens risk; when it converts an instant order
to a pending order to satisfy an entry/stop-distance fuse, it recalculates
volume against the revised stop distance while retaining the cash risk budget.
Our margin path currently rejects an unaffordable position rather than
applying that optional cap. These platform-specific mechanics do not establish
our simulator's execution quote or fill price. This is an interim defect check
for the implemented market/limit paths. After every implementation checkbox
closes, repeat the complete submission-to-fill review across order time,
executable quote/time, slippage, sizing inputs, and protective levels. Full
Stage E account, observation, and action-mode parity remains open.
The focused account-transition, repeated-payout, risk-sizing, and action suites
pass 225/225, including volume-step rounding, risk-coordinate variation,
delayed-order risk retention, evaluation construction, and saved sizing
metadata. This closes only that bounded sizing slice. Other selected stop,
target, exit, observation, and full action-schema parity remains open.

The execution review identified that config-built market fills defaulted to
zero extra adverse slippage even though `costs.slippage_points` is 5.0. The
configured amount now defaults onto market entries and market exits for both
bar and tick quotes; explicit zero remains available for historical replay.
Protective OHLC fills retain their existing cost adjustment without a second
charge, and limit fills remain within their submitted price bounds. The user
approved this future-simulation behavior; saved historical run evidence is
unchanged. The final submission-to-fill review is being repeated against this
resolved cost contract.

The user also decided that a pending limit cancels when its source setup
expires or is replaced. Both simulators now check source-event timestamps and
producer validity before accepting a fill; missing or ambiguous state fails
closed. A source-driven cancellation allows the current policy decision to
submit a newly selected setup, while account, risk, and overnight-session
blocks remain in force. Cancellation rows retain candidate and source-event
identity. Limit-latency randomness is now keyed by submission time, side,
candidate ID, and exact limit price so simulator-local order counters cannot
break paired latency draws. The cross-engine invalidation/replacement,
same-decision resubmission, session, and latency regressions pass in the
consolidated implementation gate: 3,484 tests pass with five documentation
tests deselected. Full-tree Ruff format/check and `git diff --check` pass.
Full-tree Mypy remains failing at 374 errors across 51 files; repository-wide
typing remains a release limitation.

That interim fill review traced action submission, quote resolution, sizing,
limit-price bounds, entry geometry, protective levels, discretionary exits,
and terminal liquidation through both simulators. It corrected market-open
timestamps to preserve separate decision-bar and submission times, and found
terminal bar-close liquidation had missed the configured market slippage. The
terminal close now applies it once; protective OHLC fills do not receive a
duplicate charge. A follow-up classified bar-open account-breach
`forced_close` events as market fills while leaving protective OHLC stop/target
events untouched. The execution/order/account-parity/risk-lifecycle batch
passes **81 tests**; the forced-close classification batch passes **53 tests**.
Scoped Ruff and `git diff --check` pass. The final full submission-to-fill
rereview remains open until all implementation checkboxes close.

The setup action's stop anchor, target selections, simplex coordinates, and
exit choice now share one decoder between `TradingEnv` and the event-backtest
policy adapter. The event backtest retains those selected coordinates across
market/limit submission and delayed fill, and records them on the resulting
open event. The event backtest now installs structural geometry, multi-target
fractions, EMA-21 exit state, and learned SL/TP management modes on the
position. Management choices survive delayed market submission and fill; the
same geometry-choice object is retained by pending limit orders. Deferred
modes advance from excursions and confirmed swings; explicit choices stay
locked to the selected mode. TP changes become effective on the next bar and
preserve target ordering. A focused decoder, environment, event-backtest, and
protective-lifecycle batch passes **98 tests** with scoped Ruff checks. This
closes the learned management-mode slice. The account-transition,
tick-lifecycle, and event-contract regression batch adds **68 passing tests**.
Broader action/account/observation parity and the full cross-engine replay gate
remain open. The full
submission-to-fill rereview remains queued until every implementation checkbox
closes.

## Saved-equity mark-to-market source identity — 2026-11-04

The initial cache-only preflight found a fingerprint mismatch between
Parquet-loaded frames and the A4 in-memory `train_bars`/`test_bars` frames. The
reusable `scripts/research/analysis/evaluation/audit_saved_equity_bar_identity.py`
now rebuilds the saved splits directly from their configured raw M1 sources,
saved configs, price-grid transform, cleaning, session labels/IDs, and split
dates. The exact historical frame hashes reproduced for all four A4
partitions, and both original run manifests agree with their reanalysis
manifests. The current Parquet-loaded frame hashes remain different; use the
verified raw-rebuilt frames for subsequent equity calculations. The original
feature cache is absent, but it is not needed to reconstruct the saved bar
frames. Machine evidence is at
`evidence/research/simulator_execution_parity/equity_series_reconciliation/source_reconstructed_bar_identity.json`
with interpretation at the adjacent `source_reconstructed_bar_identity.md`.
The follow-on `scripts/research/analysis/evaluation/reconcile_saved_equity_to_fills.py`
uses these exact source-rebuilt bars and the archived fill ledger to reproduce
all 357,126 saved equity rows for A4A/A4B training and report-period testing.
All four partitions match within $0.000000001; the maximum close-fill PnL
arithmetic difference is below $0.000000000001. It calculates cash from fill
prices and quantities, and follows source-confirmed environment timing and
broker quote-side marking. Machine evidence and interpretation are in
`evidence/research/simulator_execution_parity/equity_series_reconciliation/equity_fill_reconciliation.json`
and its `README.md`; packet checksums link the output and analysis source.
This closes the serialized saved-path cash/position/mark-to-market accounting
slice only. Tick-by-tick excursions, current-rule counterfactual policy replay,
historical action-to-eligibility linkage, external feed/calendar parity, and
policy quality remain open. The pass ran in the existing GH200 allocation
without a new Slurm job or step.

## Daily-limit breach outcome — 2026-11-04

The user's daily-limit formula is fixed at 5% of initial equity, anchored to
each supplied session's opening equity, and includes open PnL. The user decided
that equality at the daily floor is allowed and a breach occurs only below it;
any such breach permanently fails the full account/evaluation. Static maximum-
loss equality is also allowed, and a breach occurs only below its floor. Payouts
can withdraw only realized profit above initial operating balance.
The shared guardrail scope now latches that failure in the environment and
event backtest; new evaluation reports count daily breaches against survival.
Focused guardrail, rollout, and paired risk-lifecycle checks pass 66/66. The
two-session TickBook trace and independent verifier pass with matching engine
events and zero same-session or later-session opens after breach. Evidence is
at `evidence/research/simulator_execution_parity/daily_breach_full_evaluation_failure/`.
The earlier recovery behavior remains preserved in its historical packet and
is superseded for new evaluations. The saved A4 equity screen had zero 5%
session-net floor crossings, but those historical runs used a gross
realized-loss counter that blocked later actions; they do not settle the
counterfactual.

The saved-equity verifier has now been aligned with the equality-allowed
boundary: a sampled value breaches only when it is strictly below the session
floor. Its focused regression covers exact equality and a below-floor value;
all four retained A4 path reports were regenerated from the same saved runs.
Each still has zero sampled breaches. This corrects the audit boundary label;
it does not change the historical policy or establish the current-rule
counterfactual path.

## Payout profit-boundary audit — 2026-11-04

The selected-policy lifecycle summarizer now emits a separate check that each
payout is positive and its pre-reset realized balance is above operating
capital, in addition to verifying `payout = balance_before_reset -
operating_balance`. Synthetic reports accept a valid positive withdrawal and
fail closed for negative, zero, and below-operating-balance withdrawals. The
summary and packet suite passes 20/20.

The current-source summarizer was rerun from the four hash-linked A4 training
and report-period partitions. The aggregate packet matches all four partition
input/report manifests and cashflow reconciliations. Each partition has zero
payout rows, so the selected historical policy supplies no observed payout
cycle. Current-source reports and packet checksums verify at
`evidence/research/selected_policy_trade_lifecycle/payout_profit_boundary/`.
This closes only the payout-boundary audit slice; it does not establish an
empirical payout outcome or close broader Stage E account/report reconciliation.

## User-home recovery search — 2026-11-04

The missing-artifact scanner also searched `/home/nguyenl37` for same-basename
files matching the 132 currently unresolved run-artifact hashes. The read-only
walk traversed 9,417 directories with zero traversal errors; it hashed one
2,515-byte candidate and found zero exact matches. The report and metadata are
in `evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/`.
This adds one bounded search root but does not establish global absence; the
Stage A recovery gate remains open for differently named files, remaining
roots, and the unreadable archive payloads.

## Temporary-root recovery search — 2026-11-04

The same-basename missing-artifact scanner also searched `/tmp` and `/var/tmp`
for the 132 unresolved run-artifact hashes. It traversed 62 and 1 directories,
respectively, without walk errors; six candidates totaling 10,740 bytes were
hashed under `/tmp`, and `/var/tmp` had no candidates. Both reports contain zero
exact matches, leaving all 132 targets unresolved. This is bounded coverage of
two temporary roots only; Stage A recovery remains open.

## Selected-run maximum-loss event reconciliation — 2026-11-04

The reusable saved-equity auditor now reconciles each recorded `max_drawdown`
event against the pinned $100,000 initial balance and $10,000 hard maximum-loss
allowance. It accepts equality at the floor and requires the first breach below
$90,000. Across four selected A4 partitions, all saved metrics and chronology
match; three breach events match an exact equity observation and the first
sampled floor crossing, while A4A training has no event or crossing. The
reported post-close equity matches either the event bar timestamp or the
liquidation `fill_time`, depending on the saved event. Focused tests pass 11/11,
Ruff passes for the analyzer and test, and exact input/output hashes are in
`evidence/research/simulator_execution_parity/max_loss_event_reconciliation/`.
The pinned historical configs omit `max_drawdown_mode`, so this closes only the
initial-equity floor/event slice; EOD/intraday peak references, full daily-risk
state, and policy replay remain open.

## Active feature event-family semantics — 2026-11-04

The current-source synthetic event contracts were rechecked in the existing
GH200 allocation. Nine focused suites passed 157/157 cases covering swing
confirmation, order-block confirmation/retest, FVG/IFVG retest and invalidation,
PO3 sweep/reclaim/readiness, completed higher-timeframe visibility, liquidity
sweeps/BOS, and SMT secondary-symbol timing with missing bars. The packet maps
each family to the tests and records exact source/test hashes at
`evidence/research/feature_causality/active_event_family_semantics/`. This closes
those synthetic event-order and state-transition subcases only. It does not
establish market event prevalence, economic impact, all-profile validity and
padding semantics, or historical PPO candidate linkage; overall Stage D stays
open.

## Versioned evaluation account-state trace — 2026-11-05

`TradingEnv` and the event backtest now attach `account_state_trace.v1` rows to
their valuation marks. Rows preserve decision and valuation times, an explicit
pre-action/post-action phase, session anchors, hard/soft daily and maximum-loss
limits, drawdown mode and floors, payout totals, position geometry, pending
market/limit order lifecycle fields (including limit price and expiry), and
breach reason. Terminal backtest liquidation refreshes the final trace row to
match returned equity and payout-aware economic value. Evaluation writes traces
to `account_state_trace.csv`;
diagnostics record schema, row count, phases, and trace completeness. An
alternate environment that omits snapshots produces no partial trace.

A controlled account-transition fixture confirms shared equity marks, but not
same-timestamp cash-ledger equality: `TradingEnv` reports post-action state and
the event backtest reports pre-action state, so balance and open PnL may differ
at their common mark time. The phase is explicit in each row and in diagnostics.
The controlled fixture confirms matching close-fill timestamps and PnL, and
that each observed balance delta equals the realized close cashflow at that
boundary; its strengthened four-case regression passes. Per the user's
decision, preserve both phases and reconcile through fill chronology rather
than normalizing the reported states.
The focused rollout, artifact-export, snapshot, account-transition,
repeated-payout, and engine-execution batch passes 85/85; the full market/limit
execution integration module passes 12/12. Both pass with scoped Ruff checks.
Historical backfill, action-to-fill/reported-
account reconciliation, cash-ledger timing, and Stage E acceptance remain
open. No training or new experiment was started.

## Event-backtest decision-to-order lineage — 2026-11-05

The event backtest now returns `event_backtest_policy_decision.v2` rows in
`policy_decisions`, including the selected action, setup identity and
eligibility, eligible-candidate count, selected market/limit execution and
limit parameters, risk fraction, and geometry choice. Stable decision IDs are
carried onto market/limit order submissions, delayed limit fills and
cancellations, selected-setup rejections, and opened positions. Setup identity
is checked across rejection, submission, fill, cancellation, and open events.
Rejection direction is reconciled to its selected action.
Open-to-close attribution uses the position ID. Decision rows also snapshot
the open-position direction and ID, pending-order ID, and decision timestamp
so reconciliation can distinguish an
intentional hold from a missing entry outcome and verify that the referenced
position or pending order was live at that timestamp. Evaluation artifact
output writes this ledger to
`policy_decisions.csv` and records schema, row count, and completeness in
`evaluation_diagnostics.json`.

Focused backtest lifecycle, account-transition, payout, and report-export checks
pass 60/60, with scoped
Ruff checks. This closes the event-backtest decision-ID instrumentation slice;
historical PPO decision linkage and full Stage E accounting/eligibility
reconciliation remain open. The account snapshots keep their distinct
pre-action and post-action phases and are reconciled through fill chronology.

## Account-state trace reconciliation v2 — 2026-11-05

The account-state trace now carries `account_state_trace.v2` rows with an exact
trade-event prefix, contract size, and the position's actual mark price. The
reusable verifier independently replays entry commissions, close cashflows,
payout resets, and legacy gross closed-loss totals; it checks balance/equity,
marked open PnL, payout-aware economic value, session-net daily loss, daily
floor anchors, maximum-loss floors by mode, and peak-to-trough drawdown. Payout
records must reconcile both to the replayed pre-reset cash balance and to the
post-payout operating balance. Unsupported or mixed historical schemas are
reported as incomplete rather than passing.

The report writer exports `account_state_reconciliation.json` and adds status
and check counts to evaluation diagnostics. The controlled synthetic account
transition reconciles both environment post-action and event-backtest
pre-action traces against their own event chronology. Shared equity marks,
close fill timestamps/PnL, and timestamped realized cashflow deltas agree; the
two reported phases remain distinct by design. The focused snapshot,
reconciliation, rollout, report-export, account-transition, payout,
setup-mask, and execution suites pass 83/83; a subsequent payout-corruption
regression passes 4/4. Scoped Ruff and `git diff --check` pass. This closes
trace reconstruction and this synthetic numeric reconciliation slice only;
it does not establish historical backfill, financing/charge coverage, full
action-to-eligibility replay, or overall Stage E acceptance. No training or new
research run was started.

## Current stop-menu checkpoint diagnostics — 2026-11-06

The selected A4 checkpoints record a three-timeframe stop menu, while the
current configuration selects M3/M5/M10/M15/M30/H1/H4/D1. The user chose to
evaluate the current eight-timeframe menu as a changed-policy diagnostic.
Reanalysis explicitly opts into that menu and labels its outputs
`changed_policy_train_only_diagnostic`; report-period rows are not evaluated.

Two A4A diagnostic replays completed. Both report matched account-state and
policy-decision reconciliation, complete eight-artifact ledgers, identical
artifact hashes across all eight artifacts, and identical training metrics:
623 trades, -9.22% return, -21.16% maximum drawdown, and Sharpe -0.621. One
A4B diagnostic replay `21439459` completed with exit 0 on 2026-11-06. Its
99,492-step training-only ledger has matched account-state and policy-decision
reconciliation, each with zero failures. Independently recalculated SHA-256
and row counts for all eight artifacts; they match the report. It recorded 628
trades, -10.06% return, 18.68% maximum drawdown, Sharpe -0.711, and full-period
survival false at `2025-12-29 13:54:00.017 UTC`. The 2026 test split was not
evaluated. This is a current-source, eight-frame changed-policy diagnostic,
not a same-policy checkpoint replay, repeatability proof, selection result, or
authorization to train.

A4A job `21439662` has produced its first full-ledger output at
`deterministic_replay_01/`. The saved report says action mode is stochastic,
despite the worker's deterministic label; all eight ledger hashes and row
counts match its report, and account-state and policy-decision reconciliation
both have zero failures. It records 421 trades, -10.115% return, 16.24% maximum
drawdown, Sharpe -0.897, and one static `max_drawdown` breach at equity
$89,869.835 on `2025-09-05 14:15:00.205 UTC`; daily loss at that valuation is
$73.72. The ledger's close-event accounting attributes -$67,883 to 209 stop
closes and about +$57,987 to EOD, target, and EMA exits, plus a -$219 forced
close. This explains the breach as accumulated negative realized value
crossing the static floor in this replay; it is accounting decomposition, not
a causal feature analysis or repair. The source A4A/A4B checkpoints were each
trained for 2,000,000 steps with `env.reward_mode: dsr`, not the implemented
survival objective. Their failed survival diagnostics therefore do not test
whether survival-first training can qualify. Saved A4A/A4B configurations include the
$900 sizing cap, $5,000 / 5% daily loss, and $10,000 / 10% static maximum loss,
but still contain repeated-evaluation payout settings; these ledgers report no
payout events. **Bounded no-go:** deterministic repeatability of the historical
A4 checkpoints will not be established under the current user direction
forbidding a rerun. A4A's first replay is stochastic and cannot count as a
deterministic repeat; A4B has only one current-source diagnostic replay. Job
`21439662` then FAILED with exit 2 after 27:49, before the second replay or
comparator. I edited the worker file while it was executing; Bash reported a
syntax error after the first output. No cancellation signal was sent. The
corrected external worker now passes `bash -n`, passes `--deterministic`, and
writes to fresh paths so it cannot overwrite this stochastic result. Preserve
both A4 outputs and logs, and do not describe either checkpoint as
repeatability-verified. This no-go does not close Stage E's broader full-ledger
and daily-risk reconciliation or establish repeatability for a future
survival-trained checkpoint; any such campaign must use the corrected worker
and comparator. The previous interrupted A4B output and log also remain
preserved. Evidence is under
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/checkpoint_replay_a4_pinned_0d056dc/current_8frame_stop_menu_changed_policy_diagnostic/`.

## Date-split feature fitting scope — 2026-11-06

Review found that the production event-backtest runner, rule-baseline runner,
and bars-to-features path for the LSTM supervised baseline applied date splits
after feature construction without passing a train mask. They now use the
shared `training/runner/feature_preparation.py` builder, which creates the
configured inclusive training-date mask and includes it in feature-cache
identity. The event backtest and rule baseline also honor configured
`train_start` when splitting primary and secondary bars. A focused contract
test is included in the consolidated release suite but has not run. The shared
date split now represents the inclusive last training date as the next local
calendar midnight, exclusive, so subsecond rows are included without crossing
the wrong date at daylight-saving boundaries. Regressions cover subsecond
precision and a DST transition in both the split and normalization mask; they
remain unrun until the consolidated implementation gate. The historical
seed-50 open-rate diagnostic also now uses the shared split-scoped feature
builder, including configured `train_start`, rather than truncating its fit mask
at midnight on `train_end`. Training-only feature-analysis ledgers, observation
warmup analysis, configured action-contract construction, bundle/variant-space
audits, and environment-memory profiling now use the same date-mask helper;
replay rescore uses the configured train start as well. Baseline/named cache
rebuilds, replacement-fold and tick-coverage audits, decision-schedule
fingerprints, and defense-figure feature fitting now also honor `train_start`.
The central split tests cover the new boundary behavior and remain pending the
consolidated gate.
A follow-up
call-site sweep also routed stochastic seed-variance evaluation and the
strategy-feature verification utility through the same train-mask builder.
Caller-supplied LSTM `--features-csv` matrices must now match a canonical local
rebuild under identical bars/config/train dates, including row/column identity
and all values; mismatch regressions are included but unrun. The rolling
normalizer also rejects non-boolean, duplicate-index, incomplete-coverage, and
empty training masks in both its direct transform and fit-state capture; the
new regression cases are selected by the feature test suite and remain unrun.
A current-source sweep of direct `build_features` call sites found that model,
evaluation, and training-only analysis paths pass date/fold masks or a saved
train-fitted state. The two deliberately unmasked prefix-invariance builds
compare causal full-history and truncated-history outputs; they are not model
fit paths. The current source inventory found no fitted feature selector,
imputer, scaler, or transform pipeline outside the rolling normalizer. The
reachability cutoff uses only previously completed NY sessions; descriptive
D1 regime thresholds lag volatility by one completed session; opportunity-
census terciles are computed on their training-only slice. Other `quantile`
calls found in metric and plotting code summarize observed outputs rather than
fit policy thresholds. These are source-level dispositions only. Runtime
call-site regressions and project-wide active-feature causality remain open.
Remaining unmasked builds serve full-versus-prefix causality comparisons or
visualization-only chart regeneration. Refresh release hashes after
implementation settles.

## Same-basename recovery search across scratch

On 2026-11-06, the retained-file scanner hashed 589 ordinary files (3,746,898,205
bytes) under `/scratch` whose basenames matched the 132 currently missing run
artifacts. It found zero exact matches and had zero file-read errors. All 132
targets remain unmatched. The scan returned `incomplete_walk_errors` with 3,516
permission-denied directory walks outside `/scratch/work/nguyenl37`; that user
tree had zero walk errors. The inaccessible trees remain unverified, so this
does not establish global absence. The scan is limited to ordinary files with
matching basenames; archive members and differently named files are outside
its scope. The report, metadata, and checksums are in
`evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/`.

Reviewing the prior 16 archive errors showed ten tiny pytest fixtures and six
zero-byte MTF benchmark checkpoint ZIP paths. They have no readable ZIP members;
the raw same-basename search still included them. No evidence was removed or
modified. Stage A recovery remains open.

## Scratch recovery search completeness update

The 2026-11-06 same-basename scan across `/scratch` completed under the existing
GH200 allocation. It hashed 589 ordinary files totaling 3,746,898,205 bytes,
with zero file-read errors and zero exact matches for the 132 unresolved
artifacts. Its `incomplete_walk_errors` status is deliberate: 3,516 directory
walks were denied outside `/scratch/work/nguyenl37`; the user's research tree
had zero traversal errors. Those inaccessible trees remain unverified, and the
scan does not establish global absence or cover differently named files or
nested archive payloads. Ten tiny pytest ZIP fixtures and six zero-byte MTF
checkpoint paths account for the prior 16 ZIP parse failures; their raw files
were included in the ordinary same-basename hash set. The report and metadata
are checksummed in the historical recovery packet. No training or new research
run was started.

## Live per-symbol sizing ceiling — 2026-11-06

Source review found that the RL paper/live adapter sized at 1% of balance
($1,000 on the initial $100,000 account), while training's configured total
per-trade sizing budget is $900. The adapter now derives an absolute per-symbol
total-risk budget from `ftmo.risk_sizing_limit_usd` and applies it during
both sizing and order validation. It now reads `costs.slippage_points` and
`costs.commission_per_lot` and converts them with the MT5 symbol tick
size/value. New-order sizing and risk checks reserve adverse entry and
protective-stop slippage plus round-trip commission; open-position exposure
reserves remaining stop slippage and the exit-side commission. Entry commission
is already reflected in the account balance after opening. This covers the unknown
broker entry fill, while the training simulator sizes from its already
slippage-adjusted executable entry. The canonical config's five-price-point
slippage is active in the RL live entrypoint; other MT5 managers retain
zero-cost constructor defaults. Regression cases and the consolidated gate
entry are updated but unrun. The manager still lacks
training-equivalent daily/max-loss account state; real-order mode remains
fail-closed and live/account parity remains open.

The numeric-input source sweep also found Python booleans could pass as `1.0`
through the MT5 risk manager, including ATR-derived scaling, account snapshots,
and broker position/quote metadata. These paths now fail closed, and regression
cases are in `tests/unit/live/test_risk_manager.py`. AST parsing and scoped
`git diff --check` pass; the tests remain deferred to the consolidated
implementation gate. This does not close live/training account-state parity or
authorize real-order mode.
