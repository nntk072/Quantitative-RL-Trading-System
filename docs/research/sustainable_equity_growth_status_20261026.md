# Sustainable equity growth research status

**Updated:** 2026-10-26
**Purpose:** Current handoff for reward-alignment work and the regime-aware
research plan. This file records the current run state and latest results.

## Skipped DSR 1-env attempt

The user chose to skip this experiment and proceed to the regime-aware plan.
The run was interrupted before its first checkpoint and is not a result:

- Campaign: `sustainable_growth_dsr_peak_eod_dd10k_seed50_train2025_20261026_2m_normal_1env_v1`
- The 1-env campaign YAML and variant list were removed after the user asked to delete the idea.
- Variant: `sustainable_growth_ppo_dsr`
- Job `21206675` on `gpuarm1`, one GH200, 48 CPUs, 512 GB RAM, six-hour allocation.
- Reached 310,000 / 2,000,000 steps; interrupted before any checkpoint. Do not report it as a completed benchmark or resume it.
- Fingerprint: `e0b215578736a6a17d167e6b19aa3e712801d99d56e4c6b4471d2cb689e1dcb0`.
- Logs, attempt metadata, and the allocation are preserved. No `scancel` was used. At the latest check, the allocation remained RUNNING with no active trainer; reuse it for independent work.

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

## Regime-aware work now in progress

The completed 2M DSR replay is the R0 control. Its reproducible report is
`docs/research/regime_attribution_20261026.md`; the report generator saves
machine-readable trade, regime, and entry-intent tables beside it. The
interrupted 1-env attempt is not a prerequisite and must not be relaunched.

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
corrupted derived cache was rebuilt once from the same saved config and data;
its regenerated SHA-256 matches the earlier valid rebuild and the treatment
availability counts are unchanged. A retry campaign with the same scientific
settings passed dry-run preflight and has not started. Use that retry as the
single R1 development screen; the failed startup is not a result or a second
seed. `matched_pair.json` records R0, the failed startup, and the preflighted
retry. Keep 2026 report-only.

The regime-attribution implementation and cache treatment passed the full
agent gate on `gpuarm1` (aarch64/GH200): full-tree Ruff format, full-tree Ruff
lint, full-tree Mypy across 766 files, and 85 scoped campaign, replay, feature,
and research tests. `git diff --check` also passed. The full pytest suite was
not run. The D1 cache rebuild and the gate establish feature-path availability
and code correctness; R1 training and its matched replay are still required to
measure any policy effect.
