# Function usage and context

This guide connects every exported callable to its owner, workflow context, and the strongest source-backed usage evidence available. Examples are real call-site excerpts from implementation code, tutorials, or tests; fixture-dependent excerpts link to their source test. An explicit no-call-site label means repository analysis found no direct invocation, so the page gives the owning lifecycle and complete contract without inventing a recipe.

Current source call-site coverage: 525 of 726 callable records.

```{toctree}
:maxdepth: 1

artifacts/index
compute/index
configuration/index
decisioning/index
evaluation/index
experiments/index
features/index
integrations/index
learning/index
live/index
market_data/index
models/index
simulation/index
trading/index
training/index
```

## Coverage

This generated index contains 726 callable records. Rebuild and verify it with `python -m tools.documentation.api_usage --write` and `--check`.
