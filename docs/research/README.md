# Research results and methods

This section organizes results by research question, not run directories. Read each finding alongside its evidence packet, evaluation method, limitations, and reproduction status.

The current end-to-end synthesis is the
[research evidence report](research_evidence_report.md). It
preserves the negative findings and makes the remaining scientific gates
explicit; it is not a release verdict.

## Policy architecture and decision structure

| Finding | Status | Result class | Evidence and interpretation | Reproduction |
| --- | --- | --- | --- | --- |
| [Setup-conditioned replay](setup_conditioned_policy_replay) | Exploratory | Negative screen: both policies breach loss limits in the recorded 100k-step comparison | [Method/protocol](setup_conditioned_reasoning_benchmark_protocol); [tracked evidence](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/setup_conditioned_reasoning_replay/README.md); [limitations](limitations) | [R1 evidence explorer](../reproduce/setup_conditioned_evidence) |
| [Encoder architecture comparison](encoder_architecture_comparison) | Benchmark | Bounded engineering result plus a one-seed negative MTF survival screen; exposed-period replay only | [Methodology](evaluation_methodology); [limitations](limitations); [screen evidence](../../evidence/research/model_observation_and_action_semantics/mtf_architecture_screen.json) | Evidence report and configs; screen is not a model ranking or fresh holdout; no new training here |
| [Model observation and action semantics](model_observation_and_action_semantics) | Architecture audit | Source/configuration description; no economic claim | [Evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/model_observation_and_action_semantics); [model catalog](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/releases/negative-evidence-readiness/MODEL_AND_BASELINE_CATALOG.md) | Source inspection and existing run-specific manifests |
| [Sustainable equity growth](sustainable_equity_growth) | Exploratory | Reward/risk behavior analysis | [Validation protocol](validation_protocol); [limitations](limitations) | R1 report; source per-arm outcome package is incomplete |
| [Monthly entry and exit attribution](entry_and_exit_attribution) | Negative viability screen | Paired monthly trade attribution; both arms fail survival gate | [Semantic evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/entry_and_exit_attribution) | [R2 aggregate recomputation](../reproduce/entry_and_exit_attribution.ipynb); not a raw-tick replay |
| [Selected policy trade lifecycle](selected_policy_trade_lifecycle) | Historical descriptive reconciliation | 987 A4A and 825 A4B training positions link to fill events; separate tick packet derives timestamp-bounded MFE/MAE, with candidate-action linkage and causal attribution still open | [Semantic evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/selected_policy_trade_lifecycle) | Reusable lifecycle and excursion analyses; historical 2025 training evidence, associated 2026 holdout already inspected |

## Execution semantics and costs

| Finding | Status | Result class | Evidence and interpretation | Reproduction |
| --- | --- | --- | --- | --- |
| [Fill quote availability](fill_quote_availability) | Local source diagnostic | Selected recorded fills aligned to tick timestamp groups; not a fill-validity claim | [Concept-named evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/fill_quote_source_alignment) | Streamed analyzer and fixture test; source clock and tie chronology remain open |
| [Exit-action semantics](exit_action_semantics) | Exploratory | Frozen decoder replay and selected common-entry cohort; no economic superiority claim | [Semantic evidence packet](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research/exit_action_semantics) | [R2 cohort recomputation](../reproduce/exit_action_semantics.ipynb); full replay inputs are incomplete |
| [Execution and costs](../concepts/execution_and_costs) | Method | Fill, spread, latency, and slippage assumptions | [Evaluation methodology](evaluation_methodology) | See deterministic software trace and tick tutorial |
| [Entry-idea opportunity counts](entry_idea_opportunity_counts) | Descriptive engineering measurement | Family and timeframe episode counts from a tracked aggregate export | [Tracked aggregate package](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/main/evidence/research/entry_idea_opportunity_counts/entry_idea_opportunity_counts.md) | [R2 aggregate recomputation](../reproduce/entry_idea_opportunity_counts.ipynb); source feature rows are absent |

## Market representation and context

- [Regime attribution](regime_attribution): exploratory attribution and its limits.
- [Daily regime feature normalization](regime_context_comparison): matched comparison that did not establish improvement.
- [Order block and multi-timeframe context](order_block_and_multitimeframe_context): definitions and engineering limits.
- [Configured multi-timeframe data alignment](multitimeframe_data_alignment): exact native/M1 timestamp and OHLCV parity, separate spread differences, and unresolved schedule classification.
- [Feature causality and availability](feature_causality_and_availability): source-function and setup-flag inventory with unassessed timing fields clearly marked.

## Engineering performance

Training throughput is an engineering measurement, not trading performance. See [GH200 throughput audit](gh200_throughput_audit) for measured rates, hardware conditions, and bottlenecks.

The [survival runtime correctness smoke](survival_runtime_correctness_smoke_20261110)
records a bounded synthetic check of the configured policy, checkpoint, and
evaluation path. It is implementation evidence, not an economic result or
scientific-training authorization.

The [candidate-geometry feature contract](candidate_geometry_feature_contract)
defines the causal formula, unit, source, decision-time availability, and
missingness behavior for every model-facing geometry feature.

## Methods and claim boundaries

- [Result identity and evidence](result_identity_and_evidence): versioned
  finding/run identities, reasoned unknowns, and hash-verified artifact links.
- [Evaluation methodology](evaluation_methodology)
- [Validation protocol](validation_protocol)
- [Limitations](limitations)
- [Finding card template](finding_card_template)
- [Reading list](references)
- [Negative and inconclusive findings](negative_results)

The [active research execution plan](../operations/research_execution_plan.md) is an operational queue, not evergreen methodology. Historical source lineage is summarized in the `evidence/research/historical_source_provenance/README.md` packet; archived run outputs remain checksum-preserved outside the repository.

```{toctree}
:hidden:

references
negative_results
exit_action_semantics
entry_and_exit_attribution
selected_policy_trade_lifecycle
entry_idea_opportunity_counts
multitimeframe_data_alignment
feature_causality_and_availability
candidate_geometry_feature_contract
survival_runtime_correctness_smoke_20261110
model_observation_and_action_semantics
mt5_ftmo_execution_fidelity
quote_coverage_sensitivity
fill_quote_availability
result_identity_and_evidence
```
