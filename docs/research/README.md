# Research results and methods

This section organizes results by research question, not run directories. Read each finding alongside its evidence packet, evaluation method, limitations, and reproduction status.

## Policy architecture and decision structure

| Finding | Status | Result class | Evidence and interpretation | Reproduction |
| --- | --- | --- | --- | --- |
| [Setup-conditioned replay](setup_conditioned_policy_replay) | Exploratory | Negative screen: both policies breach loss limits in the recorded 100k-step comparison | [Method/protocol](setup_conditioned_reasoning_benchmark_protocol); [tracked evidence](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/setup_conditioned_reasoning_replay/README.md); [limitations](limitations) | [R1 evidence explorer](../reproduce/setup_conditioned_evidence) |
| [Encoder architecture comparison](encoder_architecture_comparison) | Benchmark | Bounded engineering and short-policy screen | [Methodology](evaluation_methodology); [limitations](limitations) | Evidence report and configs; no new training here |
| [Sustainable equity growth](sustainable_equity_growth) | Exploratory | Reward/risk behavior analysis | [Validation protocol](validation_protocol); [limitations](limitations) | R1 report; source per-arm outcome package is incomplete |
| [P6 monthly entry/exit decomposition](p6_monthly_entry_exit) | Negative viability screen | Paired monthly trade decomposition; both arms fail survival gate | [Tracked paired-trade evidence](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/p6_monthly_entry_exit_20261025/p6_monthly_entry_exit_decomposition.md) | [R2 aggregate recomputation](../reproduce/p6_monthly_exit_decomposition.ipynb); not a raw-tick replay |

## Execution semantics and costs

| Finding | Status | Result class | Evidence and interpretation | Reproduction |
| --- | --- | --- | --- | --- |
| [Exit-action semantics](exit_action_semantics) | Exploratory | Frozen decoder replay and selected common-entry cohort; no economic superiority claim | [Method and limitations](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/archive_2026/evidence/exit_action_semantics_20261024/exit_semantics_findings.md) | [R2 cohort recomputation](../reproduce/exit_action_semantics.ipynb); full replay inputs are incomplete |
| [Execution and costs](../concepts/execution_and_costs) | Method | Fill, spread, latency, and slippage assumptions | [Evaluation methodology](evaluation_methodology) | See deterministic software trace and tick tutorial |
| [Entry-idea opportunity counts](entry_idea_opportunity_counts) | Descriptive engineering measurement | Family and timeframe episode counts from a tracked aggregate export | [Tracked aggregate package](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_idea_opportunity_counts/entry_idea_opportunity_counts.md) | [R2 aggregate recomputation](../reproduce/entry_idea_opportunity_counts.ipynb); source feature rows are absent |

## Market representation and context

- [Regime attribution](regime_attribution): exploratory attribution and its limits.
- [Daily regime feature normalization](regime_context_comparison): matched comparison that did not establish improvement.
- [Order block and multi-timeframe context](order_block_and_multitimeframe_context): definitions and engineering limits.

## Engineering performance

Training throughput is an engineering measurement, not trading performance. See [GH200 throughput audit](gh200_throughput_audit) for measured rates, hardware conditions, and bottlenecks.

## Methods and claim boundaries

- [Evaluation methodology](evaluation_methodology)
- [Validation protocol](validation_protocol)
- [Limitations](limitations)
- [Finding card template](finding_card_template)
- [Reading list](references)
- [Negative and inconclusive findings](negative_results)

The [active research execution plan](../operations/research_execution_plan.md) is an operational queue, not evergreen methodology. Historical evidence remains in the [research archive](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research).

```{toctree}
:hidden:

references
negative_results
p6_monthly_entry_exit
entry_idea_opportunity_counts
```
