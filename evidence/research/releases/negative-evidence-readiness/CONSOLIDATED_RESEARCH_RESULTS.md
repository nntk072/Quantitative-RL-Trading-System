# Consolidated research results

## Research question and scope

The current research asks whether causal multi-timeframe market context and a
setup-conditioned sequential policy can improve decisions under the project's
execution and account-risk constraints. Existing results are development and
exploratory evidence; they do not establish an untouched out-of-sample claim.

## Selected matched pair

The recovered selected pair is seed 50, 2 million training steps, and 32
environments on the 2024-12-30 through 2025-12-31 training interval. Both arms
failed the campaign's strict zero-breach training risk-survival gate, but both
evaluations reached `data_end` and completed the configured data split. The
generic gate reason `max_loss_stopped_trading` does not name the underlying
breach type.
The A4A treatment recorded 987 positions and −2.154% net return. Its aggregate
ledger endpoint, $97,845.69, is above the $90,000 floor. The A4B control
recorded 825 positions and −10.056%, ending at $89,943.95, $56.05 below that
floor. These total-ledger endpoints and the per-episode gate answer different
questions; the campaign risk gate failed for both arms.

The first breach events occurred on 2025-03-06 at 20:16 (A4A) and 20:32 (A4B),
in broker wall-clock UTC+03. The campaign used `trading_policy.mode=legacy`:
its `daily_loss` counter accumulated gross negative closed-trade P&L without
offsetting profitable closes or measuring net daily equity. Through those
events, the close ledgers show gross negative P&L of $5,017.66 / $5,399.25 and
net realized close P&L of −$3,004.28 / −$3,389.32 for A4A / A4B. These are
breaches of the configured historical counter, not evidence of a net
FTMO-style daily-equity breach. A4B also had a separate `max_drawdown` event on
2025-10-28. The stored `fail_time` is the first breach timestamp, not a
terminal stop: both evaluations separately record that they reached the end
of the configured data split. The trace explains how the gross realized-loss counter
crossed its threshold, but not why the policy entered the stopped trades; see
the [risk-gate trace](gross_realized_loss_counter_breach_trace.md).

The training entry funnel adds a separate mechanism trace: 88.3% of treatment
entry requests and 91.1% of control requests were rejected because the entry
state machine was not armed. Downstream cooldown, stop, reward/risk, and
session-boundary rejections are recorded separately. This localizes substantial
action-interface attrition but does not explain the losing equity path or
establish whether a different action mask would improve economics; see the
[entry-action funnel diagnosis](entry_action_funnel_diagnosis/entry_action_funnel_diagnosis.md).

The paired March-to-April gross-mean-R change was −0.2177 for A4A and −0.2238
for A4B. The month-stratified 95% intervals were [−0.5837, 0.1429] and
[−0.5656, 0.1118], respectively. Both include zero. The fixed-entry EMA21
reference decomposes arithmetic across saved cohorts; it does not simulate a
new policy or identify a causal entry/exit effect.

## Earlier policy screens

The tracked 100k-step hybrid and setup-conditioned full-training-period
replays both breached the configured $10,000 maximum-loss gate. The hybrid
control ended at $90,003.73 over 308 positions; the setup-conditioned policy
ended at $90,026.53 over 1,031 positions. These were one-seed negative screens,
not 2M results or confirmation. Their full-year ledgers record no new opens
after the breach.

## Current-source Tier 0 setup reference

The matched setup evaluator completed the 2025 development split for the
always-no-trade control, one seeded random-eligible reference, and one fixed
structure-priority rule. Each arm processed 351,432 bars and 99,492 decisions
from the same bar, feature, and TickBook inputs. The control remained at
$100,000 with no fills or breaches. The random reference completed 1,854
positions, returned −10.16%, and recorded 25 breach events; the fixed rule
completed 1,169 positions, returned −10.03%, and also recorded 25 breaches.
Per-arm and step-aligned paired within-trajectory intervals are retained in
the [matched setup baseline packet](../../matched_setup_baselines/README.md).
These are negative Tier 0/Tier 1 accounting results, not a comparison with the
historical RL checkpoint, multi-seed estimates, or viable strategy claims.

## Exposed report period

2026-01-01 through 2026-10-16 was already inspected and is report-only. The
recovered pair's report-period replays ended at −10.0016% for A4A and −10.3679%
for A4B; both failed the account floor. They cannot be relabeled as a fresh
holdout by rerunning them.

## Configured multi-timeframe data

The configured native-versus-M1 bar audit found exact timestamp and OHLCV
parity across 30 native symbol/timeframe series: 532,350 development rows and
423,018 exposed-report rows. US100 D1 is an M1-derived fallback in each split,
so those two views are not independent native comparisons. Native spread
differs from both M1 mean and last-value references; the audit does not infer
which spread definition is authoritative. The first-M1 availability report
records 15 final higher-timeframe rows per period without a later M1 row and
does not classify delayed rows against an authoritative schedule. This bar
result does not resolve tick-side missingness, same-time quote chronology,
feature-prefix coverage, or execution parity. See
[configured multi-timeframe data alignment](../../../../docs/research/multitimeframe_data_alignment.md)
and its [machine report](configured_timeframe_parity.json).

## Candidate outcome-data feasibility

The training-only conditional replay covers 54,638 statically eligible
proposals across the 24 candidate categories enabled by the recorded profile,
with 1,067,731 proposal/bracket combinations. It verified 259,358
filled/resolved rows, 39,186 unfilled/expired limit rows, and 769,187
unresolved rows. Most unresolved outcomes reflect incomplete local quote
coverage before exit resolution (355,861 rows) or order disposition (319,870);
89,609 more have no market-entry quote within the configured wait. The
remaining unresolved rows retain invalid realized stop/target geometry,
session-close boundary, or quote-order failures.

Coverage is strongly unequal by signal month: unresolved shares are 84.8%–94.2%
from 2024-12 through 2025-08, 53.0% in September, 45.4% in October, 32.1% in
November, and 15.9% in December. The candidate-by-month and monthly reason
tables preserve their exact denominators. This pattern is a coverage and
trigger-horizon limitation; it does not identify an economic regime effect.
The stratified replay audit exactly reproduces 12 rows through the same
versioned execution function, not an independent implementation. The packet is
conditional fixed-entry evidence and excludes policy actions, account state,
portfolio contention, and policy value. The current resolved subset is not a
representative basis for candidate calibration, model fitting, or a return
claim. See the [candidate outcome packet](../../candidate_outcomes/README.md).

## Conclusion

No tested model has demonstrated a robust economic edge under the recorded
risk constraints. There is one selected seed-50 pair, no untouched confirmatory
period, and bounded current-source tick and configured-bar audits rather than
an exhaustive data/feature/execution audit.
The underlying provider and license were not investigated at the user's
direction; raw data is excluded and no rights claim is made. The defensible
conclusion is negative and bounded: the
tested policies did not establish viability. Differences between arms remain
descriptive, not causal.

## Canonical result routes

- [Research findings map](../../../../docs/research/README.md) (research-wide)
- [Monthly entry and exit attribution](../../../../docs/research/entry_and_exit_attribution.md)
- [Setup-conditioned 100k replay](../../../../docs/research/setup_conditioned_policy_replay.md)
- [Result registry](../../../../docs/reproduce/result_registry.md)
- [Operational evidence and gates](../../../../docs/operations/research_execution_plan.md)
