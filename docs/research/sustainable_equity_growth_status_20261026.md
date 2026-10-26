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

## Regime-context implementation in progress

The implementation defines the optional `tcn_regime` architecture. Its
separate seven-value input uses the last completed D1 return, EMA-distance,
ADX, and realized-volatility channels with per-feature validity masks. It
requires D1 source-index train-only normalization, leaves existing TCN behavior
unchanged, and keeps the action, execution, and account-risk contracts fixed.
The matched two-arm screen is prepared in
`config/campaigns/regime_tcn_context_r2_seed50_train2025_2m.yaml`; it must wait
for a suitable GH200 allocation after the currently active allocation ends.
The current implementation passed full-tree Ruff format, full-tree Ruff lint,
and full-tree Mypy (772 files), plus 73 focused environment/model/config tests
and 7 D1 source-normalization tests on the existing GH200 allocation. The
checkpoint test verifies deterministic action parity after saving and loading
the new PPO architecture. R2 has not started; no training result is claimed.
