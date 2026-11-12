# Final readiness report

**Snapshot date:** 2026-11-03
**Source:** `3c30030ace717974d32a697395de4e0a32ac943b` (`main` baseline; work is
on `codex/final-research-evidence-release`)
**Verdict:** **BLOCKED — preserve as a negative, exploratory research result;
do not label this snapshot a final thesis or public release.**

## Scientific verdict

On the declared 2025 development interval, both arms of the selected matched
selected campaign failed its strict zero-breach training risk-survival gate; both
evaluations nevertheless reached the end of the configured data split
(`completed_data_split=true`, `episode_end_reason=data_end`). The generic gate
reason `max_loss_stopped_trading` does not identify the underlying breach type.
The A4A treatment recorded 987 positions and −2.154%, with aggregate ledger
equity ending at $97,845.69 (above the $90,000 floor). Its matched A4B control
recorded 825 positions and −10.056%, with aggregate ledger equity ending at
$89,943.95, $56.05 below that floor. These aggregate endpoints do not override
the per-episode risk-gate failure. Exposed 2026 report-period replays also
failed for both arms and are descriptive only. The evidence does not
demonstrate that any tested policy has an economic edge, nor that the tested
setup-conditioning factor caused the difference.

The first breach event occurred on 2025-03-06 at 20:16 for A4A and 20:32 for
A4B (broker wall clock, UTC+03). Both were `daily_loss` events under
`trading_policy.mode=legacy`. At the pinned campaign source SHA, that mode
accumulated gross negative closed-trade P&L without offsetting winning closes
or using mark-to-market daily equity. The closes through the events sum to
$5,017.66 gross losses / −$3,004.28 net for A4A and $5,399.25 / −$3,389.32
for A4B. Thus the events establish failure of the configured historical
counter, not a net FTMO-style daily-equity breach. A4B had a separate
`max_drawdown` event on 2025-10-28. The stored `fail_time` is the first breach
timestamp, not a terminal episode stop: the rollout separately records
`episode_end_reason=data_end`. The trade trace identifies how the gross-loss
counter tripped but does not explain the policy's stop-out sequence. See the
[risk-gate trace](gross_realized_loss_counter_breach_trace.md).

## Gate matrix

| Area | Disposition | Evidence and remaining work |
|---|---|---|
| Source and active-work freeze | Partial pass | Baseline SHA and current branch/worktree are captured. The v2 profile and full inventory check completed: all 140 inventory paths (64 distinct targets, 16,325,449,095 unique bytes) verify, and all 38 selected-pair data files match campaign-observed hashes. The inventory hasher normalizes repository-local path identities. The 49-manifest provenance DAG was regenerated. The refreshed function/test navigation map covers 613 production files and 3,567 definitions, with 965 direct static test references (421/1,355 P0, 511/2,083 P1, 33/129 P2). It records name-convention visibility and static production references; these are not API, call-graph, execution-coverage, or dead-code claims. The ignored 27,800-file `outputs/` tree is preserved outside the checkout with a same-path symlink and metadata inventory. Nested caches and other external outputs remain incompletely enumerated. |
| Selected campaign lineage | Partial pass | The current artifact-integrity verifier rehashes the campaign fingerprint and source snapshot, its embedded 590-file manifest, both run manifests, both configs, and both final checkpoints. The campaign snapshot commit `b93642a` is an ancestor of both run-source commits `0d056dc`, which are ancestors of current HEAD. All 39 campaign input files were separately rehashed and matched; the result-manifest verifier passes. No checkpoint was loaded or replayed. Each run manifest records one dirty source file and the complete run source-tree hash remains unknown; the recorded feature cache is absent at its run-manifest path and was not rehashed. See [`CHECKPOINT_REGISTRY.json`](CHECKPOINT_REGISTRY.json) and [`selected_campaign_artifact_integrity.json`](selected_campaign_artifact_integrity.json). |
| Evidence organization and preservation | Bounded pass | Dated/archive research outputs were moved only after external checksum verification: 255 historical files and 40 benchmark outputs have external manifests, and semantic findings remain in concept-named packets. Reusable analyzers are grouped under `scripts/research/analysis/` by evidence, feature, market-data, evaluation, or model domain. The [migration ledger](../../../../docs/architecture/migrations/research_evidence_moves.json) preserves original paths and hashes; the [release manifest](RELEASE_MANIFEST.json) records external locations. No unique source snapshots or experiment results were intentionally discarded. |
| Research result identity | Partial pass | Added the v2 manifest contract and a hash-verified record for both arms of the selected seed-50 negative pair. All plan-required identity fields are present; unavailable historical values carry explicit reasons, so the result remains draft. Archived run manifests/configs resolve only through the designated sibling research archive. The focused verifier suite passes 14 tests. This does not upgrade the scientific evidence grade or make the pair confirmatory. |
| Research result | Negative, bounded | Both full data splits completed and failed the predeclared strict zero-breach gate under historical gross realized-loss counter semantics. The March `daily_loss` labels are not FTMO-style net equity breaches; A4B also had an October max-drawdown event. The trace explains the gross realized-loss counter crossing, not the policy's stop-out sequence. One seed is not positive viability evidence. The fixed-entry EMA21 decomposition is accounting attribution, not a causal intervention. |
| Failure diagnosis | Partial pass | The train-only entry funnel shows 88.3% of treatment and 91.1% of control entry requests were rejected while the entry state machine was unarmed. Selected fill-to-tick analysis matched all 3,698 tick-backed events; 16 shared changed-quote timestamp groups and 86 were in groups missing a required side, with the parser's first valid quote carrying that side. The saved alignment packet contains no quote prices, carried-side age, or within-timestamp ordering, so it identifies no no-carry/next-quote price or economic sensitivity. A bounded reread could report observed timestamp-group extrema, but those would not establish executable prices or fill validity. A separate historical fixed-entry v2 exit shadow on 1,062 eligible entries reports mean structural-minus-EMA ΔR 0.0070 with a 95% paired bootstrap interval [−0.0416, 0.0528]; it is not the selected A4 pair and does not identify its losses. The retained A4 training rows reconcile decision, order-submission, fill, and exit records by position ID, and a separate timestamp-bounded MFE/MAE analysis is descriptive rather than a feasible exit counterfactual. Candidate/event linkage is now measured only for the matched random and structure-priority baseline traces: 39,566 random and 43,974 structure-priority decision rows fall inside proposal validity windows, but historical A4 PPO proposal-to-action linkage remains unavailable. These results do not establish quote chronology or isolate a causal loss mechanism. See the [selected policy lifecycle packet](../../selected_policy_trade_lifecycle/README.md), [candidate action linkage](../../candidate_action_linkage/README.md), [fixed-entry shadow findings](../../exit_action_semantics/fixed_entry_shadow_findings.md), and [fill quote availability](../../../../docs/research/fill_quote_availability.md). |
| Data source and quality | Blocked | The stable-source v2 profile hashes all 39 campaign inputs (8,162,529,858 bytes across 34 bars, four tick exports, and the configured schedule); all 39 are present and hash-matched. It accounts for 172,290,383 tick rows, 371,390 rows missing a required quote side, 329,471 adjacent timestamp ties (328,918 changed-quote pairs; 553 missing-quote pairs), zero timestamp parse failures or reversals, and 23 training M1 minutes per instrument without ticks; test M1 minutes all overlap at least one tick. These are source-quality counts, not order-arrival validity. The final 140-path check verifies every inventory entry with zero file differences, and the concept-named monthly quality CSV/figure are hash-linked to the profile. A separate candidate quote audit finds 40,330 raw-row count mismatches and 93,326 of 351,432 M1 minutes failing its conservative local completeness rule; only 24,064/28,787 market fill minutes and 5,543/25,851 full pending-limit windows pass. This is local export consistency, not tape completeness or executable-fill proof. The flag cross-tab does not establish provider flag semantics. The [configured timeframe parity report](configured_timeframe_parity.json) finds exact timestamp and OHLCV parity on all 532,350 training and 423,018 exposed-report native bar rows; native spread differs from both tested M1 references. Fifteen final higher-timeframe rows per period lack a later M1 observation. Schedule authority remains unestablished. Provider/license assessment is out of scope by user direction; no raw data or rights claim is included. See the [v2 profile](local_market_data_quality.json), [detailed tick diagnostic](current_market_input_diagnostic.json), [candidate quote coverage](../../candidate_outcome_coverage/README.md), [flag cross-tab](tick_quote_side_flag_cross_tab.json), [data checksum manifest](RAW_DATA_SHA256_MANIFEST.json), [data provenance dossier](DATA_PROVENANCE_AND_ACCESS.md), and [interpretation](../../../../docs/research/multitimeframe_data_alignment.md). |
| Candidate conditional outcomes | Partial pass with bounded unresolved-data result | The full training replay contains 54,638 proposals and 1,067,731 conditional bracket rows: 259,358 filled/resolved, 39,186 unfilled/expired, and 769,187 unresolved. The packet verifier confirms IDs, the complete proposal/bracket grid, chronology, training cutoff, source/config/TickBook hashes, status totals, and 43,615 locally covered session-close exits. Most unresolved rows come from incomplete local quote intervals. The unresolved share is 84.8%–94.2% from 2024-12 through 2025-08, then 15.9% in 2025-12; this variation is coverage/trigger-horizon dependent and makes resolved-only outcomes time-selected. The verifier validates structure and recorded totals; it does not independently recompute each fill and return. A deterministic audit exactly reproduced 12 rows, one per observed entry-type/status/reason stratum, through the versioned production execution function; it is a replay sample, not a separate algorithm or full-row numeric recalculation. The disposition table and figure are in the [candidate outcome packet](../../candidate_outcomes/README.md). These rows are not policy outcomes, and no return or edge claim is promoted. |
| Causality and normalization | Partial pass | The current v39 all-profile real-market prefix report resolves 130 configurations into 19 feature-builder groups and passes 57/57 comparisons across three cutoffs with zero maximum absolute delta. The strict merge verified 78 source hashes and four local input hashes. The source reconciliation, including the superseded v38 snapshot, is at `../../feature_causality/prefix_source_reconciliation.md`. Current matrix schema v2 contains source-contract metadata for all 107 feature/upstream candidates, with fixture, timing, and configuration limits. The 130-profile warmup-validity audit and semantic crosswalk identify 206 interior-missing pairs, 463 leading-only pairs, 219 finite-zero collisions, and two features unavailable throughout; eight leading nonfinite M1 PO3 rows per feature (one in each affected group) are consistent with the normalizer's two-observation standard-deviation warmup. All 108 setup flags have an M1 output-row availability record and source-level producer review. The selected overlay enables 24 flags; the other 84 are disabled and have no active candidate rows or measured identity counts in this census. Source review identifies scalar/latest-zone event collapse for FVG/IFVG, single-active-zone state for order blocks, and PO3 tuple reuse across disconnected state episodes; these limits preclude logical event-cardinality claims. The training-only identity census resolves 488,008 active rows to 109,391 candidate-scoped source-time IDs. Descriptive lifecycle counters report 115,863 identified identity-episode starts, 13,758 adjacent active identity changes, and 5,719 IDs reused across separate active-mask episodes; none is logical event cardinality. `trade_setup_mask` reads the current `step_idx` feature row, and the environment applies the action using that row before the next-index fill. Normalization fit-scope source review and focused tests pass 11/11; this does not complete the project-wide pretraining audit. Publication latency, authoritative calendar semantics, untested configurations, and end-to-end availability across all feature families remain open. See the [current all-profile prefix report](../../feature_causality/real_market_feature_prefix_invariance_all_profiles.json), [feature timing matrix](../../feature_causality/README.md), and `simulation/environment/observation_runtime.py` / `simulation/environment/episode_runtime.py`. |
| Setup/action contract | Partial pass | The current scoped suite passed the 12 setup catalog/property checks, 22 observation/environment/integration checks, and nine CPU hybrid-actor checks. A newer regression found and fixed a stale-observation defect: after advancing to the next decision row, TradingEnv now returns that row's setup mask. Ten mask/rollout tests and the current regression pass; prior campaign outputs predate this fix and cannot be replayed without the selected checkpoint. One CUDA/ROCm round-trip test was skipped because no accelerator allocation was available. A training-only census covers 351,432 M1 decisions and all 108 setup categories: 24 are supported and 84 are disabled by the selected overlay. It counts contexts, not trades, and does not resolve calendar validity or the price-geometry challenger. See [the census](../../trade_setup_opportunity_census/README.md). |
| Execution, risk, accounting | **Blocked** | Same-bar protective-first ordering is aligned for the characterized stop/target versus account-guardrail case. The initial Tier 0 bar-3,854 mismatch was a checker false positive: the diagnostic compared bid OHLC with a short ask-side target; side-aware checks and tick-only no-candle-fallback behavior now pass focused tests. Subsequent corrections cover entry-bar chronology, post-partial-target stop updates, and float64 source-quote equality. The completed local random-reference trajectory is recorded in the matched baseline packet, but it does not establish a validated policy fill model. Broad account parity, within-bar market chronology, authoritative reset-clock equivalence, and comprehensive real-feed lifecycle coverage remain open. The historical matched pair used historical gross realized-loss counter semantics, not net daily-equity semantics. See the [account-transition characterization tests](../../../../tests/integration/backtest/test_account_transition_parity.py) and [risk-lifecycle tests](../../../../tests/integration/backtest/test_risk_lifecycle_characterization.py). |
| Baselines and model selection | Blocked | The verified three-arm bundle covers 351,432 bars and 99,492 decisions per arm. The flat control remained at $100,000 with no breaches; the single-seed random reference returned -10.16%, and the fixed structure-priority rule returned -10.03%; each trading arm recorded 25 breach events. Per-arm intervals and both step-aligned paired comparisons are hash-bound in the draft bundle. These are negative accounting/sanity results, not RL or model-selection comparisons. The separate legacy MTF screen is withdrawn from current comparative evidence; its packet retains provenance and protocol identity only. Supervised, common-risk, independent-seed, and untouched validation gates remain incomplete; no model is selected. |
| Statistics and untouched validation | Blocked | The entire 2026-01-01 through 2026-10-16 interval is exposed. No untouched confirmatory holdout is available in this evidence package. The selected pair is one seed; no robust multi-seed claim is supported. |
| Metric and report definitions | Partial pass | `evaluation.metrics.performance.compute_metrics` is documented as the canonical aggregate implementation; new serialized results carry `qrl.performance_metrics.v2` and `periods_per_year`. Version 2 distinguishes undefined all-breakeven profit factor and unavailable sweep-delay observations from numeric zero. Standard summaries, matched-run comparisons, baseline output, variant-detail tables, and training dashboards label counts as completed positions and render undefined no-position statistics as `N/A`. Standard metric JSON writes unavailable/non-finite values as `null` with a reason and rejects non-standard `Infinity`; the legacy M1 annualization overflow now resolves to an explicit non-finite report value without a runtime warning. Per-idea/per-timeframe win rate and profit factor reuse the canonical trade-PnL calculation and preserve explicit availability reasons. Focused metric/report/dashboard tests pass (83), with the setup-policy metric contract tested separately. The legacy G3 reader renders missing/non-finite Sharpe, drawdown, and breach values as `N/A` and fails closed. Other historical schemas, daily return, time-to-ruin, cost decomposition, and figure QA remain to be audited. |
| Evidence reproducibility | Partial pass | Tracked R2 findings can regenerate bounded tables/figures; recovered selected external artifacts have a separate hash report. The result registry correctly has no R3/R4 research findings. The release manifest does not claim raw-data R3 or training R4. |
| Software release and docs | Partial pass | The latest full-tree source gate after the shard tooling passed format and Ruff checks on 1,042 files, Mypy on 1,028 source files, and 931 scoped tests with two existing PyTorch warnings. The generated documentation inventory and evidence sufficiency audit have been refreshed; the final strict Sphinx build and release-hash checks are recorded in `RELEASE_MANIFEST.json`. Full GitHub CI and final thesis figure/table regeneration remain; this evidence package is an internal negative-result handoff, not a positive trading or public-release claim. |
| Compute and allocation | No training | Existing allocation 21376798 on gpuarm2 provided one GH200, 48 CPUs, and 512 GB host RAM for the four parallel CPU-bound feature-audit processes; all 57 comparisons passed. The full-tree source gate also used this existing allocation. No training, checkpoint replay, new Slurm allocation, or extra Slurm step was launched. Earlier data jobs and diagnosed gate attempts remain recorded in the external progress ledger. |

## Subsequent diagnostic checkpoint replay

After this snapshot, both selected A4 seed-50 checkpoints were replayed on the
2025 training split only, using stochastic actions and the recorded seed 50.
The replay reports match their saved training metrics and both arms fail the
survival gate. The 2026 report split was not evaluated, and no policy was
trained. This later diagnostic does not change the snapshot's negative release
verdict or authorize resuming the failed campaign. Evidence is indexed at
[`selected_checkpoint_train_replay`](../../selected_checkpoint_train_replay/README.md).

## Verification run in this snapshot

The following focused command completed with **54 passed, 2 warnings** using
the checkout's x86 Python module entry point:

```text
.venv-x86/bin/python -m pytest \
  tests/unit/features/test_causal_features.py \
  tests/unit/features/test_htf_alignment.py \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py -q
```

The warnings were PyTorch nested-tensor notices in transformer tests. The
installed `pytest` script had a stale shebang pointing to another checkout;
using `.venv-x86/bin/python -m pytest` ran the suite with Python 3.12.14,
PyTorch 2.14.0+cu130, SB3 2.9.0, x86_64, and CUDA unavailable on this host.

A combined 44-test command for setup contracts, properties, hybrid actor,
observation schema, and integration was started. It stopped producing output
after six hybrid actor tests and yielded no pytest summary. The isolated setup
catalog/property command (12 tests) and the separate observation-schema,
simulation, and integration command (22 tests) then completed successfully.
The earlier hybrid-actor attempts were incomplete and are not counted as
current passes. The later CPU-node quality job below supersedes them for the
CPU-available test cases.

The bounded CPU-node verification job 21340375 ran the command listed in
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/verify_release_cpu_20261101.sh`;
it completed with 109 passed and two PyTorch nested-tensor warnings. The
following strict Sphinx build rendered all documentation pages and notebooks,
then failed because the operational plan cross-referenced the readiness README
outside the docs source tree. The path was changed to literal repository text;
the corrected strict build passed on job 21340616.

Additional isolated commands completed successfully: 12 setup catalog/property
tests; 22 observation-schema, environment setup-observation, and setup
integration tests; and two fixture tests for the new current-input audit.
Their exact commands are recorded in [the manifest](RELEASE_MANIFEST.json)
and [function/test index](FUNCTION_TEST_EVIDENCE_INDEX.csv).

The complete local checksum job 21341683 rehashed all 140 inventory entries
(64 distinct resolved files, 16,325,449,095 unique bytes) and confirmed that
all 38 selected matched pair data inputs match their campaign-observed hashes. The
inventory-entry byte sum is 32,650,507,987 because symlink aliases appear at
multiple declared paths. Hashes and metadata are recorded in
[`RAW_DATA_SHA256_MANIFEST.json`](RAW_DATA_SHA256_MANIFEST.json); no raw data
was copied into the release.

The final verification job 21341946 rechecked the checksum manifest, then ran
full-tree Ruff format/check and Mypy plus the scoped suite. Ruff passed for 920
files, Mypy passed for 906 source files, and pytest completed with 153 passed,
one skipped, and two warnings in 26.38 seconds.
The skipped test is explicitly accelerator-only (`requires CUDA or ROCm`); no
GPU allocation was available, and no short diagnostic GPU job was created.
Strict Sphinx job 21342115 completed after the final documentation edits with
`build succeeded` and exit code zero. Its 2,587
rendered HTML files are at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261101_latest`.
The tree manifest is at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261101_latest.manifest.json`
with SHA-256
`3411537e1b3fea142b97b3fce53a5b0dbe34f3a03eab8c28c3ae152bc85f37b9`.

The risk-contract clarification also passed the complete focused policy file:
18 tests passed in
`.venv-x86/bin/python -m pytest tests/unit/trading/test_repeated_payout_policy.py -q`.
Scoped Ruff format/lint and Mypy passed for the new provenance-DAG builder and
the policy test file. The manifest-declared DAG builder indexed all 49
discovered run manifests with zero parse issues (2,848 nodes, 30,391 edges);
it records declared hashes but does not rehash large data/checkpoint files.

The configured native-versus-M1 timeframe audit and expanded release gate ran
sequentially in job 21345323 on csl8 (4 CPUs, 16 GiB requested, 6:04 elapsed,
6,395,532 KiB peak RSS). The parity report contains 32 entries: 30 native
symbol/timeframe series and two explicitly M1-derived US100 D1 views. All
native timestamps and OHLCV agree exactly; spread and first-M1 availability
differences are reported separately. Full-tree Ruff passed on 931 files,
Mypy on 917 source files, pytest completed with 225 passed/1 accelerator-only
skip/2 warnings, and strict Sphinx succeeded. The report's interpretation is
documented in
[`multitimeframe_data_alignment.md`](../../../../docs/research/multitimeframe_data_alignment.md).

The final stable-source check and earlier software gate ran sequentially in CPU job
21347604 on csl42. The full 140-path data inventory verified with zero file
differences; 64 distinct resolved targets cover 16,325,449,095 unique bytes,
and all 38 selected-pair data inputs match the campaign-observed hashes. The
function-to-test map and documentation inventories were regenerated. Full-tree
Ruff passed on 950 files, Mypy passed on 936 source files, and the expanded
scoped suite completed with 613 passed, one accelerator-only skip, and two
PyTorch nested-tensor warnings. The gate's strict Sphinx pass found three
references to README files outside the docs source root. Those references were
corrected, and docs-only job 21347682 completed a forced fresh strict build with
warnings treated as errors, followed by release-manifest hash verification.
The rendered site has 2,611 files; its per-file SHA-256 manifest is recorded in
`RELEASE_MANIFEST.json`. The documentation inventory reports 354 pages and no
orphans; the evidence sufficiency audit passes. Full GitHub CI was not run.

After the backtest annual-failure latch and selected-policy trade-lifecycle
evaluator were added, final CPU quality job 21348506 passed full-tree Ruff on
952 files, Mypy on 938 source files, and the expanded scoped suite with 615
passed, one accelerator-only skip, and two existing warnings. The later strict
Sphinx job 21348541 passed with warnings treated as errors and rendered 2,615
files; its per-file manifest SHA-256 is
`d99665a333d442213978105f35b7b8edd8aac219f269f085bef7dd2893cc434c`. The
documentation inventory reports 355 pages and no orphans. The evidence
sufficiency audit and release hash checks pass. Full GitHub CI remains unrun.

The first combined attempt, job 21345295, ended after 25 seconds because the
format gate found one unformatted provenance-DAG builder. That file was
formatted, full-tree Ruff was checked before relaunch, and the complete
sequential gate then passed in job 21345323. The failed attempt and its log
remain recorded; no retry was made before diagnosing the cause.

The final current-source code gate ran in existing GH200 allocation 21376798
after the research-analysis and sharding changes stabilized. Full-tree Ruff
format/check passed across 1,042 files; full-tree Mypy passed across 1,028
source files; the scoped release suite completed with 931 passed and two
existing PyTorch transformer warnings. The current all-profile market audit
and updated source/test map are summarized above. Documentation inventory,
evidence sufficiency, strict Sphinx, and release hash results are recorded in
the current `RELEASE_MANIFEST.json` verification section.

## Release decision

This snapshot is suitable as a transparent internal negative-result handoff.
It is not ready for public release or a final thesis evidence claim. At the
user's direction, use only the current local data; do not seek or add an
external export, provider/license record, or authoritative external schedule.
No raw data is bundled and no rights claim is made. The local quote defects,
timestamp ties, and configured timezone are reported as observed assumptions;
the saved fill-alignment evidence cannot identify executable quote chronology
or a counterfactual fill sensitivity. Keep feature and execution claims within
those limits. Do not train a successor before the active plan's scientific
gates are satisfied. A new matched experiment needs a registered mechanism,
control, factor, acceptance rule, and non-exposed validation plan.
