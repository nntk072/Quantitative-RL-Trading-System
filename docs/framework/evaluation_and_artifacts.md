# Evaluation and artifacts

Evaluation applies a declared policy or inference provider to a defined market sequence and records the resulting transitions. Artifact storage preserves the inputs and outputs needed to inspect that run. These layers make results auditable; they do not make an evaluation statistically conclusive by themselves.

## Evaluation path

1. Load the provider and verify its observation/action schema against the environment.
2. Select the evaluation data and protocol explicitly. Preserve chronological ordering and the split boundary.
3. Roll out transitions through the shared environment contract. Record actions, fills, equity, trade events, reward components, and risk events where available.
4. Compute metrics from the recorded series with documented definitions. For example, drawdown is measured relative to the running equity peak; a scalar return does not describe path risk.
5. Write the report, plots, logs, and manifest under one run identity.

```{mermaid}
flowchart LR
    O[Observation t] --> P[Policy or provider]
    P --> A[Action t]
    A --> E[Environment transition]
    E --> R[Reward t]
    E --> N[Observation t+1]
    E --> B{Episode ended?}
    E --> L[Record transition, fills, and risk events]
    L --> M[Run manifest and report]
    B -->|no| N
    N --> P
    B -->|yes| M
```

Each recorded transition links the observation, proposed action, environment
result, reward, and next observation. Episode termination ends that sequence;
the manifest identifies the inputs used to produce it.

The curated [workflow API guide](../api/domains/workflows) links to the backend-neutral episode rollout reference. The [trained policy rollout](../architecture/runtime/evaluation) adapts model/provider evaluation to TradingEnv. The [evaluation tutorial](../learn/tutorials/05_evaluation.ipynb) computes path metrics from a small deterministic curve.

## Artifact identity and trust

An artifact manifest should identify the resolved configuration, source revision, data/cache identity, seed, evaluation protocol, and output files. Missing identity fields constrain what can be reproduced. Never infer a research result from a plot alone or treat a software trace as a strategy result.

The [artifact reference](../reference/artifacts) describes storage formats, while [metrics](../reference/metrics) defines reported quantities. The [result registry](../reproduce/result_registry) states which findings can be regenerated and their evidence level. Reproduction levels distinguish an executable workflow from a result independently confirmed from complete source evidence.

See [Research](../research/README), [Reproduce](../reproduce/index), and the curated [workflow API guide](../api/domains/workflows), which links to generated evaluation and artifact references.
