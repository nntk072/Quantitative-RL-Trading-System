# Negative and inconclusive findings

Research decisions should preserve outcomes that failed to show the intended
benefit. A negative screen is evidence about the tested configuration and
protocol; it does not prove the idea can never work.

| Question | Recorded outcome | What it does not establish | Evidence route |
|---|---|---|---|
| Did the setup-conditioned policy replay pass the configured account loss limits? | The tracked 100k-step comparison is classified as a negative screen; both policies breach the limits. | It does not establish a general result across seeds, data eras, or a complete OOS protocol. | [Finding](setup_conditioned_policy_replay.md), [protocol](setup_conditioned_reasoning_benchmark_protocol.md), [evidence explorer](../reproduce/setup_conditioned_evidence.md). |
| Did daily regime feature normalization improve the matched result? | The recorded matched comparison did not establish improvement. | It does not justify selecting an encoder from the locked holdout. | [Regime comparison](regime_context_comparison.md), [limitations](limitations.md). |
| Did the exit-action replay establish economic superiority? | No. It recomputes a selected common-entry cohort and makes no superiority claim. | It is not a full closed-loop replay because raw ledgers and tick inputs are incomplete. | [Finding](exit_action_semantics.md), [R2 cohort notebook](../reproduce/exit_action_semantics.ipynb). |

The result registry currently records R2 for the bounded cohort recomputation
and deterministic environment trace, R1 for inspectable setup-conditioned
evidence, and no R3/R4 result. See the
[registry](../reproduce/result_registry.md) for exact artifact boundaries.

## Preserve the decision trail

For future work, keep the question, predeclared decision rule, matched factors,
source/data/config identities, status, supporting evidence, limitations, and
the reason to continue or stop together. The active research execution plan
records the current operational queue; it is not a place to rewrite historical
findings.
