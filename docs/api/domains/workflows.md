# Workflow APIs

Training creates policy artifacts from a resolved experiment configuration; evaluation rolls a declared provider through a defined protocol; artifact services preserve run identity and outputs; experiment services manage variants, provenance, recovery, and comparisons.

## Contracts and lifecycle

Resolve and persist configuration before execution. Bind data/cache identity, source revision, and seed to the run. Training artifacts should be marked incomplete until finalization has written required outputs and a manifest. Evaluation should validate the policy schema, use the declared split/protocol, and record the transition series from which metrics are computed. Experiment comparison should match budgets and evaluation conditions before making treatment claims.

The package boundary separates run orchestration from scientific interpretation. A completed run is not automatically a successful result; a report should state evidence level, missing inputs, and limitations. The [result registry](../../reproduce/result_registry) tracks reproducibility status.

## Entry points

Read [training and experiments](../../framework/training_and_experiments), [evaluation and artifacts](../../framework/evaluation_and_artifacts), the [evaluation tutorial](../../learn/tutorials/05_evaluation.ipynb), and [experiment design](../../concepts/experiment_design). Generated references: {doc}`training <../generated/training/index>`, {doc}`evaluation <../generated/evaluation/index>`, {doc}`experiments <../generated/experiments/index>`, and {doc}`artifacts <../generated/artifacts/index>`.
