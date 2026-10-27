# Sustainable equity growth research status

**Updated:** 2026-10-26
**Purpose:** Current handoff for reward-alignment work and the regime-aware
research plan. This file records the current run state and latest results.

## Repository validation before handoff

On 2026-10-26 the current tree passed the required commit gate on `gpuarm1`
(aarch64/GH200): full-tree Ruff format check, full-tree Ruff lint, and full-tree
Mypy (763 source files), plus 169 relevant tests (9 warnings). The first pass
identified four format changes, a Mypy return annotation issue, a test typing
issue, and two stale variant-resolver expectations; these were corrected before
the passing gate. The full pytest suite was not run.

## Latest completed matched 2M screen

Campaign `sustainable_growth_seed50_train2025_20261025_2m_normal_v1` compared
PPO + DSR with PPO + log-equity growth, seed 50, 8 environments, normal data,
and no peak-EOD or percentage trailing-drawdown rule. Results below are the
observed campaign report, not claims of generalization.

| Variant | Split | Net return | Net PnL | Max drawdown | Sharpe | Profit factor | Win rate | Trades | Outcome |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| DSR PPO | 2025 train | -10.15% | -$10,152.53 | 36.69% | -0.371 | 0.965 | 42.8% | 1,110 | Hard floor reached Nov 13; 209/259 days |
| Log-growth PPO | 2025 train | -10.18% | -$10,179.02 | 33.66% | -0.336 | 0.962 | 41.0% | 847 | Hard floor reached Sep 29; 177/259 days |
| DSR PPO | 2026 report-only | -10.07% | -$10,066 | 29.04% | -0.495 | 0.947 | — | 683 | Hard-floor stop Jul 23 |
| Log-growth PPO | 2026 report-only | -10.16% | -$10,158 | 30.67% | -0.400 | 0.941 | — | 512 | Hard-floor stop Jun 18 |

Both policies failed the full-period survival screen. The first-quarter
positive path followed by a later decline remains an empirical failure to
explain; these results do not isolate entry, exit, regime, reward, or execution
cost as the cause. The 2026 split was previously exposed and is report-only,
not confirmatory OOS evidence.

## Earlier log-growth EOD diagnostic

Campaign `sustainable_growth_seed50_train2025_20261025_2m_eod_dd10k_v1`
compared log-growth PPO with the EOD policy disabled and enabled. The enabled
arm completed 2M training steps and reported train return +28.57%, +$28,567.71,
10.21% maximum drawdown, and 519 trades. Its EOD drawdown reached $10,660.88,
so the configured $10,000 policy was **missed**, even though it did not stop
training. Its report-only test showed +10.74%, +$10,743.91, 10.96% drawdown, and
315 trades; the maximum EOD drawdown was $11,449.77. That test report covered
64/205 days and must not be represented as a completed full-period evaluation.

The prior report incorrectly labeled the EOD policy disabled by reading the
unrelated percentage peak-drawdown training gate. `training/artifacts/metrics.py`
now derives EOD status from the train/test replay results and reports the
observed value and PASS/MISS independently from hard-loss survival. A focused
regression test covers that distinction.

## Regime-aware matched screen completed

The completed 2M DSR replay is the R0 control. Its reproducible report is
`docs/research/regime_attribution_20261026.md`; the report generator saves
machine-readable trade, regime, and entry-intent tables beside it.

The D1 technical normalization repair is implemented as the opt-in feature
`features.normalize_d1_technical_on_source`. On the actual matched dataset, a
new cache rebuild changed the seven D1 technical channels from 0/1,110 finite
entry values to 990–1,096/1,110 finite values (84.4%–98.7%). It used the
completed-D1 as-of alignment and training-mask boundary. The cache identity is
`15a7206755fde49b`; detailed source hashes and counts are in
`docs/research/regime_attribution_20261026/d1_feature_rebuild_check.json`.
This proves feature availability, not improved policy performance.

The first R1 startup attempt failed before PPO training because the treatment
feature-cache Parquet footer was corrupted; it completed zero PPO steps and
created no checkpoint. Its campaign fingerprint, manifest, log, and attempt
provenance are preserved in
`docs/research/regime_attribution_20261026/r1_startup_recovery.json`. The
corrupted derived cache was rebuilt from the same saved config and data, and
the retry completed the 2M development screen. Its exact train/test metrics
and pairwise deltas are in
`docs/research/regime_attribution_20261026/matched_r0_r1_results.md`; the full
training/testing report, including figures, is
`docs/research/regime_attribution_20261026/r1_project_results_report.md`.
Trade-level D1 availability and regime attribution are in
`docs/research/regime_attribution_20261026/r1_regime_attribution.md`.
The 2026 interval remains previously exposed and report-only.

The final current-tree agent gate passed on `gpuarm1` (aarch64/GH200): full-tree
Ruff format check, full-tree Ruff lint, full-tree Mypy across 768 files, and 90
scoped campaign, replay, feature, and research tests. `git diff --check` also
passed. The full pytest suite was not run. The D1 cache rebuild and the gate
establish feature-path availability and code correctness. R1 training and
evaluation are complete; both matched arms fail the training survival gate at
the hard $10,000 maximum-loss floor. The detailed R0/R1 interpretation is below.

### Matched R0/R1 finding

Both arms used DSR PPO, seed 50, eight environments, 2M requested steps,
stochastic evaluation, the same normal dataset and account policy. R1 changed
only source-index normalization for selected D1 technical features. On the
training split, R1's terminal loss was $174.66 smaller and maximum drawdown was
5.55 percentage points lower than R0, but it made 231 fewer trades, had lower
Sharpe, profit factor, win rate and expectancy, and stopped trading 32 days
earlier. On the report-only 2026 split, terminal result was $4.60 worse and it
had lower drawdown, but also lower Sharpe, profit factor, win rate and
expectancy, 100 fewer trades, and 12 fewer trading days. Neither arm survived
the full training period. This one-seed result does not support D1 source
normalization as a fix for sustainable equity growth; it also does not prove
that D1 information is useless or identify a unique cause of the equity decline.

The R1 report confirms that selected D1 technical values were available at
most observed entry decisions after the change. Availability alone does not
show whether PPO used the channels effectively. Regime/side cells are
descriptive, single-seed in-sample evidence with early-stop censoring; the
previously exposed 2026 interval is not confirmatory evidence. Do not tune to
that interval. A next experiment needs a specific falsifiable hypothesis from
the observed regime/trade evidence before changing policy architecture or
adding another reward/control mechanism.

The added entry-action-by-regime tables show a short-intent majority across
the logged regimes in both arms (about 58–71% in R0 and 55–67% in R1). R1 also
used materially lower action-risk values and produced fewer trades, consistent
with its lower drawdown; that did not improve full-period survival or net
expectancy. These tables cover only saved `open`/`reject` events, not every
policy action, and their open-event share is not a learned abstention rate.
They support a bounded finding that input normalization changed entry-intent
behavior without repairing the negative edge, not a causal explanation of why
performance falls after the early training months.

The D1 outcome table shows conditional performance differences by trend state
and side, while the recorded entry direction mix changes only modestly across
those states. This does not prove that PPO adapts to regime: the action ledger
omits no-op and in-position decisions, several cells are small, and the runs
stop early at the account floor. It is sufficient to test the separate
representation hypothesis with an opt-in completed-D1 input branch.

## Regime-context implementation and R2 recovery

The implementation defines the optional `tcn_regime` architecture. Its
separate seven-value input uses the last completed D1 return, EMA-distance,
ADX, and realized-volatility channels with per-feature validity masks. It
requires D1 source-index train-only normalization, leaves existing TCN behavior
unchanged, and keeps the action, execution, and account-risk contracts fixed.
The matched two-arm screen is defined in
`config/campaigns/regime_tcn_context_r2_seed50_train2025_2m.yaml`.
The current implementation passed full-tree Ruff format, full-tree Ruff lint,
and full-tree Mypy (772 files), plus 73 focused environment/model/config tests
and 7 D1 source-normalization tests on the existing GH200 allocation. The
checkpoint test verifies deterministic action parity after saving and loading
the new PPO architecture.

The first R2 campaign, `regime_tcn_context_r2_seed50_train2025_2m_normal`,
started on 2026-10-26 and failed before completing the matched pair. The
control reached its hard maximum-loss floor; the treatment stopped at 1.528M
steps because an EMA exit requested a tick quote 138.8 seconds after the
nominal next-minute timestamp, outside its 60-second quote tolerance. The
validated training tick cache contains 56,245,046 ticks and preflight found
next-observed-bar quote coverage for all 99,492 M1 decision bars. The failure
was an execution-time anchor mismatch: preflight used the next observed market
bar, while tick-only EMA exits used `bar time + one minute`, which can land
inside a market-data gap. `simulation/environment/ema_exit_runtime.py` now
anchors such exits to the next observed bar; its regression test covers a
timestamp gap. The old manifest, fingerprint, checkpoints, and failure logs
remain preserved.

The corrective matched R2 campaign
`regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1` ran as
Slurm job 21210220 on gpuarm1. It used seed 50, 2M requested steps per variant,
eight environments, the same data split and execution settings, and one GH200
sequentially through the persistent worker manager. Both arms reached
2,007,040 PPO steps (whole rollout batches), saved final checkpoints, and
completed their final stochastic replays. The controller marked both variants
failed because each breached the hard-loss survival gate; the campaign summary
records two failed variants and no active workers. The R2 corrective run's
fingerprint and provenance are in its campaign manifest.

On the 2025 training replay, control ended at -$9,977.86 (-9.98%), with 31.13%
maximum drawdown, Sharpe -0.465, profit factor 0.949, and 879 trades; it traded
177/259 days. Treatment ended at -$10,084.22 (-10.08%), with 33.47% maximum
drawdown, Sharpe -0.390, profit factor 0.964, and 1,124 trades; it traded
192/259 days. Treatment's terminal PnL was $106.36 lower and drawdown 2.34
percentage points higher, while Sharpe and profit factor were slightly better.
This is mixed, single-seed in-sample evidence and does not establish a benefit
or explain the equity decline.

On the previously exposed 2026 report-only replay, control ended at
-$10,070.91 (-10.07%), with 21.59% maximum drawdown, Sharpe -0.576, profit
factor 0.929, and 583 trades; it traded 115/205 days. Treatment ended at
-$9,200.14 (-9.20%), with 23.41% maximum drawdown, Sharpe -0.465, profit factor
0.941, and 585 trades; it traded 102/205 days. Treatment ended $870.77 higher,
but both replays failed full-period survival. Since this interval was already
exposed, it is descriptive only and cannot establish a benefit or be used for
selection.

The matched campaign results are in
`outputs/gpu_campaigns/regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1/reports/campaign_results_summary.md`;
per-run evaluations, checkpoints, logs, and the campaign source snapshot are
preserved beneath that directory. The corrective run's full-train evaluation
is at
`outputs/gpu_campaigns/regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1/runs/attempts/regime_d1_norm_tcn_control__seed50/attempt1/regime_d1_norm_tcn_control__seed50/20261026_111806_381670_rl_train_seed50_tcn/evaluations/summary.md`.

Resolved configuration comparison confirmed that control and treatment match
on seed, data, PPO budget, risk policy, execution, and source-normalized D1
inputs. The only behavioral changes are the treatment's `tcn_regime`
architecture and enabled regime observation. The final campaign snapshot and
per-run evidence are preserved under
`outputs/gpu_campaigns/regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1/`;
the generated matched metrics are in `reports/campaign_results_summary.md`.
The generated live status is
`outputs/gpu_campaigns/regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1/reports/campaign_status_live.md`.

### Matched R2 interpretation

The matched R2 screen answers the narrow representation question with a
negative survival result: adding the separate completed-D1 context branch did
not keep either policy alive through 2025, and the treatment had slightly
worse terminal training equity and drawdown. Its higher activity and mixed
secondary metrics are descriptive, not evidence of a stable advantage. On the
previously exposed 2026 interval the treatment's terminal loss was smaller,
but both policies stopped early; this is not confirmatory evidence. Do not
promote `tcn_regime` from this one seed or use the 2026 interval to tune it.
R2's full chronological coverage, matched configuration, and failure gates
are useful engineering evidence. Any next experiment needs a separate,
falsifiable hypothesis from the saved train-period trade/regime evidence and
must be evaluated on unexposed evidence before a benefit claim.

### R2 saved-trade diagnostics and next-question decision

The two evaluation ledgers contain 879 control and 1,124 treatment completed
positions, each keyed to a matching position record. Every accepted trade is
tagged `trend_regime=flat` (879/879 and 1,124/1,124), so that legacy field does
not distinguish slow trend states in this screen. The available volatility
label is more varied, but remains a post-hoc, policy-selected grouping:

| Volatility state | Control N / net PnL | Treatment N / net PnL |
|---|---:|---:|
| Mid | 225 / -$9,362 | 297 / -$13,509 |
| High | 636 / -$100 | 806 / +$1,201 |
| Low | 18 / -$516 | 21 / +$2,224 |

Both long and short entries lost in the mid-volatility group: control long
87 / -$4,972 and short 138 / -$4,390; treatment long 110 / -$8,120 and short
187 / -$5,389. Low-volatility counts are too small to interpret. This pattern
does not establish that a volatility gate would help; the action policy chose
both the entries and their risk, and evaluation stops at the hard-loss floor.

Open-event actions show a larger risk and exit-profile shift under treatment.
Median approved risk was about $644 for control and $829 for treatment
(median risk fractions 0.007 and 0.009); median action-risk was 0.431 and
0.842, while median action-intensity was 0.082 and -0.496. Direction mix
changed modestly: control opened 448 shorts / 431 longs; treatment opened
588 shorts / 536 longs. These summaries describe logged opens, not every PPO
decision. The ledger omits no-op and in-position actions; 53,966 control and
55,777 treatment reject events were tagged `entry_state_not_armed`, so reject
counts are not an abstention rate.

Exit-mode outcomes also differ sharply, but they are not paired comparisons.
Control selected EMA21 on 590 trades (net -$275) and structural exits on 289
(net -$9,703). Treatment selected EMA21 on 373 (+$20,882) and structural
exits on 751 (-$30,967). The action also selects entries, sizing, and stops,
so these cohort totals cannot show that changing the exit rule would improve
the same positions. An earlier fixed-entry exit shadow on a different frozen
2025 cohort estimated mean structural-minus-EMA delta R of 0.007 with a 95%
paired bootstrap interval [-0.0416, 0.0528]; that result does not transfer to
the R2 entries. Together these findings support investigating a treatment-
specific paired exit replay if exit attribution is pursued, but do not justify
an exit override, a mid-volatility filter, or a risk cap.

No defensible policy or architecture intervention hypothesis emerges from
the current one-seed R2 evidence. Its strongest signals are confounded shifts
in selected entries, action risk, and exit mode; the legacy trend label is
uninformative, the exposed 2026 interval cannot be used for selection, and no
unexposed evaluation interval is established here. Do not launch another
campaign or alter policy behavior on this basis. The R2 result and these
limits are the current stopping point; further causal work requires a
source-verified R2 fixed-entry replay or a newly specified unexposed protocol.

Both arms completed 16 full-split training episodes: every one of the eight
environments traversed the full 99,492-bar training split twice. All episodes
ended at `data_end`; the recorded `breach_reason` was `max_drawdown` in all 16
control episodes and in 14 treatment episodes, `daily_loss` in one treatment
episode, and empty in one. This confirms chronological training coverage; it
does not override the separate final replay survival gate or establish a
performance improvement. The treatment's positive prefix-monitor readings are
interim diagnostics, not its full-split training or test result.
Controller and per-variant logs are under
`outputs/gpu_campaigns/regime_tcn_context_r2_seed50_train2025_2m_normal_ema_nextbar_fix1/logs/`.

The earlier DSR PPO 1-environment attempt
(`sustainable_growth_dsr_peak_eod_dd10k_seed50_train2025_20261026_2m_normal_1env_v1`)
was interrupted at 310,000/2,000,000 steps with exit code 143 and produced no
checkpoint. Its failure record and partial diagnostics remain preserved as
historical evidence. At the user's direction, the proposed 1-environment DSR
rerun is removed from the active plan and will not be launched. The staged
rerun config, variant list, and launcher were removed. This does not remove
DSR as the matched R0 control in the regime-aware screen; that experiment is a
separate plan item.

The saved R1 trade records have also been rendered into a static gallery at
`outputs/reports/r1_all_trade_images_20261026/index.html`: 879 train trades and
583 previously exposed 2026 report-period trades. The single-file figure book
`outputs/reports/r1_all_trade_images_20261026/R1_complete_figure_book_20261026.pdf`
contains all 1,470 saved PNGs (the 1,462 trade charts and eight aggregate
diagnostics) plus a cover. These re-render saved trade records for visual
inspection; they do not run training or evaluation.
