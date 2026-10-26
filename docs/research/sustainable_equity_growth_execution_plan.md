# Sustainable Equity Growth PPO Execution Plan

**Repository:** `nntk072/Quantitative-RL-Trading-System`
**Working branch:** `codex/risk-constrained-growth-reward`
**Updated:** 2026-10-25
**Purpose:** Preserve the scope, decisions, evidence, and next steps for the
PPO reward-alignment research so work can resume without reconstructing context.

**Current run state and latest results:** See
[`sustainable_equity_growth_status_20261026.md`](sustainable_equity_growth_status_20261026.md).
That dated handoff supersedes any older run-state statements below; this file
continues to define the research protocol and gates.

## Research objective

Test whether PPO trained on after-cost log-equity growth performs differently
from the existing PPO + Differential Sharpe Ratio (DSR) baseline. Keep the
environment, observation/action contracts, execution path, hard account limits,
PPO architecture, and training budget matched. Treat the outcome as empirical;
do not assume the growth reward improves trading.

The first experiment is a **2M-step, single-seed development screen**. It is not
the full 20M campaign and does not establish statistical superiority. The 2026
period has been inspected before and is report-only. Do not tune against it or
call it a fresh holdout.

## Current state

- The optional `equity_log_growth` reward is implemented in the working tree.
  Its current form is `100 * (log(E_after) - log(E_before))`, using account
  equity after the environment transition. DSR remains the default.
- Resolver, manifest, environment wiring, and focused reward/variant tests are
  present. **The new tests and full CI gate have not yet been run for this
  change set.** Do not treat implementation presence as a passed correctness
  gate.
- DSR, log-growth PPO, log-growth PPO + Q5, and log-growth SAC variants are
  registered. Only the matched DSR/log-growth PPO pair belongs in the first
  campaign. Q5 and SAC stay deferred until their prerequisites pass.
- The first-campaign YAML now selects **stochastic final evaluation**, matching
  the stochastic PPO action mode used in training. This corrects the former
  deterministic setting. Verify that the resolved manifest records both modes
  and the evaluation action seed before accepting results.
- No sustainable-growth PPO campaign has started.
- The completed historical TCN/MTF 2M run exposed a training-coverage failure
  that must be corrected before interpreting its late-year decline as a learned
  regime failure. Each environment resets to the first eligible training bar.
  The run used 2,007,040 aggregate steps across 64 environments, or 31,360
  steps per environment. The full 2025 replay requires 99,492 steps; the
  31,360th replay row is 2025-04-25 17:20 local time. Campaign reporting
  confirms zero completed full-split episodes. The TCN policy therefore saw
  only the early part of 2025 in training, then was replayed through later
  training months it had not encountered. Its gate failed on 2025-09-18 at
  $89,386.41; its DSR reward sum was +5.50 despite net PnL of -$10,613.59.
  This supports inadequate chronological coverage plus reward/economic
  misalignment; it does not identify entry, exit, or cost as the cause of the
  later losses.
- The matched `sustainable_growth_ppo_dsr` and `sustainable_growth_ppo_log`
  variants already request 8 environments each. At 2,000,000 aggregate steps,
  that gives 250,000 steps per environment, about 2.5 complete 2025 traversals
  if the effective run config honors the request. Confirm `n_envs` in both
  resolved manifests and verify full-split episodes before accepting results.
  Because this differs from the historical 64-environment TCN/MTF run, do not
  attribute differences from that run to reward mode alone.
- The coverage-corrected TCN/DSR campaign
  `rq_tcn_a4a_seed50_train2025_20261025_2m_normal_fullspan_n8_v1` is terminal
  with a failed worker; its campaign manifest keeps fingerprint
  `44cb5f1e7583a861059848cd750ca62c3b3acc448bc47be34bc880ab2263265f`. It is
  not an active training run and does not establish full-year policy viability.
  Preserve its logs and report as diagnostic evidence.
- The old TCN path gained through April, then lost equity from May through
  September and breached the $90,000 floor. Do not require each month to be
  profitable. For the growth screen, report survival, whether final equity is
  above its prior peak, full-window net growth, and drawdown size and duration.
  Keep the currently agreed peak-trailing policy disabled in this first pair.
- A prior 2M dollar-band run demonstrates an unresolved risk-floor mismatch.
  Its recorded configuration specifies a $100 hold-below threshold and a $900
  ceiling, yet the Q5-off training ledger contains 90 of 644 open events below
  $100 (minimum requested risk $2.17). The matching Q5-on ledger has the same
  count and minimum. Example open records preserve raw action, decoded risk,
  and requested dollars, so execution reserve does not explain this. The
  source-level action decoder appears to implement the threshold, but the
  observed fills contradict it. Treat this as a **blocking runtime discrepancy**
  until the effective environment path and exact run source are reconciled.
  Do not use those runs as clean sizing controls or infer that the configured
  floor was enforced.
- The checkout contains substantial uncommitted MTF, data, reporting, campaign,
  and PPO work. Preserve all of it; do not reset, stash, or commit unrelated
  changes as part of this plan.
- The separate all-timeframe MTF campaign has two terminal failed variants
  (both hit the $10,000 maximum-loss guard) under Slurm allocation
  `21199478`, with fingerprint
  `dfc22a795f0715395064875e6de6ad73b8dfbedd36843898e568cb8a57a225f2` and
  supervisor session `thesis-mtf-tcn-20261025`. Its workers are terminal, but
  the two-node GH200 allocation is still running until its scheduled limit.
  Preserve its allocation, controller, logs, checkpoints, and fingerprint.
  The approved growth/DD supervisor waits for that allocation to end before
  requesting its single sequential successor; it does not overlap the jobs.

## Experiment contract

| Item | Matched setting |
|---|---|
| Variants | `sustainable_growth_ppo_dsr` vs `sustainable_growth_ppo_log` |
| Algorithm / encoder | PPO / TCN |
| Seed | 50 |
| Requested training budget | 2,000,000 steps |
| Reward intervention | DSR vs scaled log-equity growth; no other planned difference |
| Train interval | 2024-12-30 through 2025-12-31 (the initial date supplies sequence context) |
| Test interval | 2026-01-01 through available 2026 data; report-only |
| Account | $100,000 initial equity; $5,000 daily loss; $10,000 maximum loss |
| Position risk | Dollar-band sizing up to $900; $100 configured hold-below threshold; $1,000 per-idea hard cap |
| Peak trailing drawdown | Disabled; retain the $10,000 maximum-loss guardrail |
| Execution | Normal dataset; raw tick execution; 0 ms added randomized latency; retain configured spread and slippage |
| Evaluation policy | Stochastic actions, matching training; record action RNG seeds |

The two resolved configurations must differ only in the declared reward mode
and its log-growth scale. Check resolved YAML/manifests rather than relying on
variant labels. Preserve the account guardrails in both arms.

## Approved follow-up: fixed-dollar EOD peak drawdown

After rendering the full training/test report for the completed TCN-versus-MTF
2M pair, plus evidence-availability reports for the earlier incomplete MTF
attempts, run a separate matched 2M seed-50 pair using the log-growth PPO policy. The control
keeps EOD peak drawdown disabled; the treatment uses a **$10,000 fixed-dollar
drawdown from the highest completed NY-session equity**. Evaluate the limit at
NY session end, close any open position at that boundary if the limit is met,
and block entries until a later EOD equity makes a new high. This is separate
from the existing $10,000 initial-equity maximum-loss rule. The experiment
isolates the EOD behavior rule; it does not replace or weaken the hard account
limits.

Both arms use normal data, seed 50, 2M steps, PPO/TCN, eight environments,
the same dollar-band sizing, stochastic evaluation, and zero added randomized
latency. The 2026 replay remains report-only. Report training and report-only
test results for both arms, including EOD peak drawdown observed, the configured
limit, lock/recovery behavior, equity path, survival, trade activity, and full
configuration provenance. The earlier 5,000-dollar draft value is superseded;
the treatment value is $10,000.

The corresponding campaign is
`sustainable_growth_seed50_train2025_20261025_2m_eod_dd10k_v1`. Its sequential
supervisor waits for allocation `21199478` to finish before requesting one
successor two-GH200, six-hour allocation. It generates the full saved-artifact
report for the completed TCN/MTF pair and evidence reports for earlier
incomplete attempts, then runs focused guardrail tests before starting the
matched pair. It does not reuse old MTF checkpoints. Existing reports and
source evidence are retained; only obsolete `ppo_*.zip` files in those MTF 2M
campaigns are removed after their reports validate.

## Execution sequence and gates

### Gate 0 — Preserve live work

Before each run, inspect the campaign supervisor, scheduler, worker state, and
allocation. Reuse the currently approved GH200 allocation when its controller
is available. Keep the aggregate 2-GH200 cap. Do not submit duplicate campaigns,
create per-worker Slurm steps, or use `scancel`.

**Pass evidence:** campaign status report, matching fingerprint, active worker
and allocation state, and a confirmed reuse path.

### Gate 1 — Reward correctness and baseline preservation

Review the changed reward and all training/evaluation call paths. Run the
focused reward, environment, resolver, manifest, and default-DSR regression
tests inside the suitable existing GPU-node allocation. Confirm positive,
negative, and zero equity changes; telescoping without discounting; no second
cost deduction; nonfinite/nonpositive handling; reset behavior; and DSR output
unchanged. Run required full-tree Ruff/Mypy plus relevant pytest paths before
committing or launching the growth campaign.

**Pass evidence:** test output, clean Ruff/Mypy results, and manifest evidence
that reward mode, reward scale, action mode, and action RNG seed are recorded.

### Gate 2 — Matched 2M PPO screen

Run only the DSR/log-growth pair at seed 50. Use the same resolved environment,
data bundle, action contract, risk policy, and evaluation procedure. Keep
stochastic final evaluation aligned with PPO training. Do not advance to Q5,
SAC, extra seeds, or 20M steps while this gate is incomplete.

**Pass evidence:** both runs have usable final checkpoints, finite learning
diagnostics, completed training and test replays, complete equity/trade ledgers,
and explicit survival/breach outcomes. If an account guardrail stops trading,
report the gate failure; do not classify it as a successful growth result.

### Gate 3 — Interpret the paired screen

Report training and report-only test metrics together: net return, log growth,
drawdown, breach/survival, trade expectancy and count, win rate, profit factor,
monthly performance, transaction costs, action distribution, risk sizing,
reward/equity reconciliation, and model-learning diagnostics. Audit that
summary metrics reconcile to saved ledgers before drawing conclusions.

**Pass evidence:** a provenance-linked report that labels the single-seed
screen as exploratory and identifies any metric or ledger mismatch.

### Gate 4 — Constrained PPO (Q5)

Only after the reward comparison is correct, compare growth PPO with Q5 off vs
on. Keep hard account limits enabled in both. Record Q5 cost units, completed
episodes, multiplier updates, checkpoint state, and any action collapse. The
current setup does not restore partial environment/account state on resume;
run an uninterrupted bounded pilot or first implement and validate complete
resume state.

**Pass evidence:** at least one completed episode and multiplier update, cost
accounting in declared units, and a demonstrable policy response that does not
collapse to always-flat behavior.

### Gate 5 — SAC comparison and generalization

Evaluate SAC only after PPO reward semantics and action compatibility pass.
Match the observation, reward, action schema, account limits, execution, and
evaluation protocol as closely as the implementation permits; document
optimizer differences. Multi-seed and untouched chronological testing are
required before making a generalization claim. No untouched period is currently
established, so a confirmatory RQ4 claim is unavailable.

## Blocking, deferred, and removed scope

### Blocking for the first PPO screen

1. Correct reward-to-equity wiring and unchanged DSR behavior, demonstrated by
   focused tests.
2. Matched resolved configurations, including stochastic train/test actions
   and recorded action RNG seeds.
3. Explain and resolve the demonstrated $100 dollar-band floor discrepancy.
   Compare the source snapshot, instantiated environment values, decoded
   action, pending order, and fill record at a failing example. Minimum pass:
   a regression test proves requests below $100 cannot create an open order or
   fill, requests at/above $100 remain eligible subject to other gates, and
   the training/test ledgers contain no under-floor risk requests when the
   policy config enables the floor. If the desired policy is to permit all
   $0--$900 sizing, remove the floor consistently in the experiment contract
   instead of claiming it is enforced.
4. Usable checkpoint recovery, finite diagnostics, and complete result ledgers.
5. Preserved hard account-risk limits and an explicit survival outcome.
6. Safe access to the existing GH200 allocation without disturbing the active
   MTF campaign.

### Deferred until after the paired screen

- Q5 training and multiplier diagnostics.
- SAC algorithm comparison.
- More training seeds and robustness/stress studies.
- Search for and use an untouched chronological holdout.
- CVaR or distributional critics, after the basic episode-return and cost
  accounting are established.
- 20M-step training, which needs separate explicit authorization.

### Removed from this workstream

- Replacing or silently changing the DSR baseline.
- New multi-asset portfolio scope.
- CPO, distributional RL, or architecture expansion as prerequisites for the
  first reward comparison.
- Re-running broad data-provenance audits that do not address the defined
  experiment inputs or a demonstrated integrity issue.
- Treating the previously inspected 2026 period as a fresh confirmatory holdout.

## Current next actions

1. Preserve job `21199478`, its allocation, logs, and fingerprint. The old
   TCN/MTF supervisor exited; the allocation is being reused by the single
   coverage-corrected TCN/DSR run recorded above. Do not start a second worker
   or campaign in this allocation while that run is active.
2. Trace the under-floor ledger example against the exact snapshot and runtime
   config; add a focused regression test and correct only the confirmed defect.
3. Finish the old TCN monthly trade-ledger decomposition: separate trade count
   and expectancy, cost contribution, entry/exit outcomes, and whether losses
   came from trades opened before or during declining months. Use the saved
   ledger; do not rerun training to answer this.
4. Review reward call timing, DSR compatibility, Q5 normalization/resume
   behavior, and growth variant config parity.
5. Once the existing allocation console is free, run the focused correctness
   tests and required Ruff/Mypy gate on the GH200 node; do not make another
   Slurm request while the current allocation can be reused.
6. Fix any demonstrated failures and rerun only affected validation, then the
   required gate.
7. Finish and report the coverage-corrected old TCN/DSR run first. Confirm its
   completed episodes and full-split ledgers, and distinguish this result from
   the earlier 64-environment undercoverage run.
8. Before the growth screen, confirm both matched arms use the same effective
   8 environments, action mode/seeds, data, risk and execution config, and
   full-split training coverage. Then start the authorized 2M DSR vs
   log-growth screen through the existing campaign supervisor.
9. Publish train and report-only test results, monthly path, drawdown recovery,
   survival, reward/equity reconciliation, and trade-ledger decomposition
   before proceeding to Q5 or SAC.

## Result record

No PPO growth-vs-DSR campaign result exists yet. This plan records the proposed
screen and implementation state; it does not claim that correctness, training,
survival, Q5, SAC, or generalization gates have passed.
