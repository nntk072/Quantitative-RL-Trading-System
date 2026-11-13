# Research methodology

The research framework separates scientific questions from their technical
implementations. Each experiment references shared component implementations
and selects variants through declarative configuration; named assemblies
express a compatible set of variants without multiplying experiment scripts.

The authoritative sources are
[`config/research/experiments.yaml`](../../config/research/experiments.yaml)
for executable definitions,
[`config/research/prospective_research_protocol.yaml`](../../config/research/prospective_research_protocol.yaml)
for prospective scientific constraints, and
[`config/research/history.yaml`](../../config/research/history.yaml)
for preserved historical evidence.

## Reader guide

| Topic | Reference |
|---|---|
| Components, assemblies, execution, resume, metrics | [Research workflow](workflow.md) |
| Existing evidence and withdrawn findings | [Historical evidence](historical_evidence.md) |
| Data availability and causal semantics | [Feature causality](feature_causality_and_availability.md) |
| Evaluation and matched comparisons | [Evaluation methodology](evaluation_methodology.md) |
| Holdout protection and statistical validity | [Validation protocol](validation_protocol.md) |
| Action and observation contracts | [Model semantics](model_observation_and_action_semantics.md) |
| Execution simulation and broker behavior | [Execution fidelity](mt5_ftmo_execution_fidelity.md) |
| What findings cannot support | [Limitations](limitations.md) |
| Scholarly sources | [References](references.md) |

Results are observations linked to a reproducible execution, not names of
report directories. Current consolidated outputs use `results.json`,
`results.csv`, and `metrics.csv`. Historical source artifacts remain
immutable; only their catalog descriptions and scientific interpretation
may be rewritten.

```{toctree}
:hidden:

workflow
historical_evidence
evaluation_methodology
validation_protocol
feature_causality_and_availability
multitimeframe_data_alignment
model_observation_and_action_semantics
candidate_geometry_feature_contract
mt5_ftmo_execution_fidelity
result_identity_and_evidence
negative_results
entry_and_exit_attribution
entry_idea_opportunity_counts
fill_quote_availability
quote_coverage_sensitivity
selected_policy_trade_lifecycle
limitations
references
```
