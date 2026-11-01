# Supervised reference learner

`learning/supervised/` contains a small Torch learner and provider that exercise
the backend-neutral `Learner` and `DecisionProvider` contracts. The reference
classifier demonstrates checkpoint loading, schema metadata, fitting, and
inference without making this package the owner of a production training
workflow.

Use it to test the learner/provider boundary and serialization expectations.
It is not an RL algorithm or a trading-performance baseline. Focused tests are
in `tests/unit/learning/` and `tests/unit/decisioning/`.
