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
of the configured data split. The trace explains how the legacy counter
crossed its threshold, but not why the policy entered the stopped trades; see
the [risk-gate trace](P6_RISK_GATE_SEMANTICS_AND_BREACH_TRACE.md).

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

## Exposed report period

2026-01-01 through 2026-10-16 was already inspected and is report-only. The
recovered pair's report-period replays ended at −10.0016% for A4A and −10.3679%
for A4B; both failed the account floor. They cannot be relabeled as a fresh
holdout by rerunning them.

## Conclusion

No tested model has demonstrated a robust economic edge under the recorded
risk constraints. There is one selected seed-50 pair, no untouched confirmatory
period, and a bounded current-source input audit rather than a full data audit.
The underlying provider and license were not investigated at the user's
direction; raw data is excluded and no rights claim is made. The defensible
conclusion is negative and bounded: the
tested policies did not establish viability. Differences between arms remain
descriptive, not causal.

## Canonical result routes

- [Research findings map](../../../../docs/research/README.md) (research-wide)
- [P6 monthly entry/exit decomposition](../../../../docs/research/p6_monthly_entry_exit.md)
- [Setup-conditioned 100k replay](../../../../docs/research/setup_conditioned_policy_replay.md)
- [Result registry](../../../../docs/reproduce/result_registry.md)
- [Operational evidence and gates](../../../../docs/operations/research_execution_plan.md)
