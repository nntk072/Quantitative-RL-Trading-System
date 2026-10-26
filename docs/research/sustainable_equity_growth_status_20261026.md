# Sustainable equity growth research status

**Updated:** 2026-10-26
**Purpose:** Current handoff for an agent continuing the reward-alignment and
peak-EOD-drawdown experiments. The dated execution plan remains the research
protocol; this file records the current run state and latest observed results.

## Active DSR + peak EOD drawdown run

The current experiment is a 2M-step, seed-50 PPO + DSR training run with a
**$10,000 peak EOD trailing drawdown policy**:

- Campaign: `sustainable_growth_dsr_peak_eod_dd10k_seed50_train2025_20261026_2m_normal_v1`
- Campaign specification: `config/campaigns/sustainable_growth_dsr_peak_eod_dd10k_seed50_train2025_20261026_2m_normal_v1.yaml`
- Variant: `sustainable_growth_ppo_dsr`
- Data profile: normal; training dates 2024-12-30 through 2025-12-31; 2026 is
  previously inspected and report-only.
- Training and final evaluation use stochastic PPO actions. Added randomized
  fill latency is zero.
- The $10,000 EOD rule is applied at NY session end. If the peak-to-EOD-equity
  loss reaches the limit, it closes any open position and blocks new entries
  until equity exceeds the prior EOD peak. This rule does **not** terminate
  training or a full replay. The separate $10,000 maximum-loss rule against
  initial $100,000 equity is the $90,000 hard stop.
- Scheduler state at the time of this note: job `21204379` holds the two-GH200
  allocation and is due to end at 02:57 EET. It has no active training workers.
  Job `21206400` is queued with `afterany:21204379`, requesting one GH200,
  48 CPUs, 512 GB RAM, and six hours. Do not submit a duplicate or cancel either
  job. The batch script validates the corrected EOD report and then starts the
  campaign once the dependency and allocation permit it.
- Campaign logs and generated outputs are under `outputs/gpu_campaigns/`; that
  directory is ignored by Git. The campaign YAML and variant definition are
  tracked so the run can be understood from the repository.

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

## Handoff sequence

1. Preserve the dependency chain and wait for job `21206400` to start; do not
   launch another campaign while it is pending.
2. Confirm the full-tree Ruff format/lint and Mypy gate and focused pytest gate
   pass before committing this repository state.
3. When the DSR campaign finishes, report actual train and report-only test
   results, EOD policy fit, hard-loss survival, completed data coverage, and
   episode-end reasons. Do not treat the EOD policy as an episode stop.
4. Keep 2026 report-only. The single-seed 2M screen is diagnostic, not a
   superiority or generalization claim.
