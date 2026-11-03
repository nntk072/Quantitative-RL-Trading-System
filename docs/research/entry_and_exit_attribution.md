# Monthly entry and exit attribution

## Research question

For the selected matched policy pair, how did each arm's monthly trade
outcomes compare with a fixed-entry EMA21 exit reference, and how did the
March-to-April gross expectancy change decompose between the entry cohort and
actual-versus-reference exit outcome?

## Method and status

This is a historical, single-seed analysis of the A4A and A4B policy arms. It
uses the configured 2024-12-30 through 2025-12-31 training interval, actual
tick-fill outcomes, and a conditional frozen-entry EMA21 reference. The
reference does not run a new policy, compound a counterfactual account, or
read the exposed 2026 period. Both arms failed the account-survival gate; this
decomposition does not change that disposition.

## Result

The two tracked arms contain 987 and 825 paired position rows. In March to
April, A4A actual gross mean R changed by −0.2177; the decomposition assigns
−0.1276 R to the changed monthly entry cohort and −0.0901 R to the change in
actual-versus-EMA21 outcomes. Its 95% paired month-stratified interval for the
total change is [−0.5837, 0.1429]. A4B changed by −0.2238 R, decomposed into
−0.1595 R for the entry cohort and −0.0642 R for the exit outcome; its interval
is [−0.5656, 0.1118]. Both intervals include zero.

The point estimates are an accounting decomposition of paired monthly means.
The EMA21 path is a conditional reference, not a causal intervention or a
portfolio counterfactual. The finding does not isolate a general entry or exit
effect and does not establish policy viability.

## Evidence and reproduction

Tracked per-entry paired-trade CSVs and their analysis summary support an R2
recomputation of monthly counts, means, medians, PnL sums, bootstrap intervals,
the March-to-April decomposition, and its figure in the
[reproduction notebook](../reproduce/entry_and_exit_attribution.ipynb).
The notebook writes the versioned
[`monthly_entry_exit_attribution.png`](../../evidence/research/entry_and_exit_attribution/monthly_entry_exit_attribution.png)
figure into the evidence packet.
The full run ledgers, raw ticks, checkpoints, and training environment are not
in this tracked packet. The claim is therefore limited to the saved paired
rows; it is not an R3 frozen-checkpoint replay or R4 training reproduction.

[evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/entry_and_exit_attribution),
[result registry](../reproduce/result_registry.md), and the
[active research gate](../operations/research_execution_plan.md).
