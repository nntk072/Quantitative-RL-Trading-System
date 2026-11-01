# Architecture and research visuals

This index links the curated diagrams and plots by the question they answer. The diagrams live beside the implementation explanations so updates stay close to their concepts.

| Visual | What it explains | Source page |
| --- | --- | --- |
| System overview | Configuration through data, features, environment, learning, evaluation, and evidence | [Home](../index) |
| Data and feature pipeline | Ingestion, transforms, features, train-only normalization, and cache | [Data and features runtime](runtime/data_and_features) |
| Multi-timeframe causal alignment | When completed M5/H1 values become visible on an M1 spine | [Causal alignment tutorial](../learn/tutorials/advanced/multi_timeframe_features.ipynb) |
| Observation/action boundary | Versioned inputs and outputs between policy and simulator | [Observation and action concepts](../concepts/observations_and_actions) |
| Environment step | Market advancement, protection, action validation, fills, accounting, and reward | [Environment step](runtime/environment_step) |
| Trade lifecycle | Costs and execution from decision through close | [Execution and costs](../concepts/execution_and_costs) |
| Model and policy architecture | Encoder, policy, and action interfaces | [Model architecture](model_and_policy_architecture) |
| Training workflow | Configuration, environment, learner, checkpoint, and evaluation handoff | [Training runtime](runtime/training) |
| Experiment lifecycle | Resolution, identity, execution, and recovery states | [Experiment run](runtime/experiment_run) |
| Artifact and evidence lineage | Evaluation outputs and the evidence needed to interpret a result | [Evaluation runtime](runtime/evaluation) |

Quantitative notebook figures include titles, units, legends where useful, and adjacent text that states what the figure shows and how to interpret it. Research figures link to their frozen source evidence or state when they are regenerated from machine-readable inputs.
