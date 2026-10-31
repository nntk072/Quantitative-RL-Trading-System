# Package dependency model

This graph is generated from direct Python imports among the production
packages. An arrow means the package at the tail imports the package at the
head. External libraries and imports within a package are omitted. The
analysis follows the same AST-based import rule as the architecture tests;
dynamic imports assembled from strings are not represented.

The graph is factual, not a complete design prescription. The architecture
tests separately enforce prohibited edges, public cross-package imports,
backend boundaries, and acyclicity. Regenerate with
`python tools/documentation/package_dependency_model.py --write`; check with
`--check`.

<!-- GENERATED PACKAGE IMPORT GRAPH: START -->

```mermaid
flowchart LR
    configuration[`configuration/`]
    artifacts[`artifacts/`]
    market_data[`market_data/`]
    features[`features/`]
    trading[`trading/`]
    decisioning[`decisioning/`]
    simulation[`simulation/`]
    models[`models/`]
    learning[`learning/`]
    training[`training/`]
    evaluation[`evaluation/`]
    experiments[`experiments/`]
    live[`live/`]
    integrations[`integrations/`]
    compute[`compute/`]
    orchestra[`orchestra/`]
    market_data -->|imports| artifacts
    market_data -->|imports| configuration
    features -->|imports| configuration
    features -->|imports| decisioning
    features -->|imports| market_data
    trading -->|imports| features
    simulation -->|imports| decisioning
    simulation -->|imports| features
    simulation -->|imports| market_data
    simulation -->|imports| trading
    models -->|imports| decisioning
    learning -->|imports| artifacts
    learning -->|imports| compute
    learning -->|imports| decisioning
    learning -->|imports| market_data
    learning -->|imports| models
    training -->|imports| artifacts
    training -->|imports| compute
    training -->|imports| configuration
    training -->|imports| decisioning
    training -->|imports| evaluation
    training -->|imports| features
    training -->|imports| learning
    training -->|imports| market_data
    training -->|imports| models
    training -->|imports| simulation
    training -->|imports| trading
    evaluation -->|imports| artifacts
    evaluation -->|imports| configuration
    evaluation -->|imports| decisioning
    evaluation -->|imports| features
    evaluation -->|imports| learning
    evaluation -->|imports| market_data
    evaluation -->|imports| simulation
    evaluation -->|imports| trading
    experiments -->|imports| artifacts
    experiments -->|imports| compute
    experiments -->|imports| configuration
    experiments -->|imports| evaluation
    experiments -->|imports| features
    experiments -->|imports| learning
    experiments -->|imports| market_data
    experiments -->|imports| models
    experiments -->|imports| training
    live -->|imports| configuration
    live -->|imports| decisioning
    live -->|imports| features
    live -->|imports| trading
    integrations -->|imports| live
    compute -->|imports| artifacts
    orchestra -->|imports| artifacts
```

| Package | Imports production packages |
|---|---|
| `configuration` | None |
| `artifacts` | None |
| `market_data` | `artifacts`, `configuration` |
| `features` | `configuration`, `decisioning`, `market_data` |
| `trading` | `features` |
| `decisioning` | None |
| `simulation` | `decisioning`, `features`, `market_data`, `trading` |
| `models` | `decisioning` |
| `learning` | `artifacts`, `compute`, `decisioning`, `market_data`, `models` |
| `training` | `artifacts`, `compute`, `configuration`, `decisioning`, `evaluation`, `features`, `learning`, `market_data`, `models`, `simulation`, `trading` |
| `evaluation` | `artifacts`, `configuration`, `decisioning`, `features`, `learning`, `market_data`, `simulation`, `trading` |
| `experiments` | `artifacts`, `compute`, `configuration`, `evaluation`, `features`, `learning`, `market_data`, `models`, `training` |
| `live` | `configuration`, `decisioning`, `features`, `trading` |
| `integrations` | `live` |
| `compute` | `artifacts` |
| `orchestra` | `artifacts` |

<!-- GENERATED PACKAGE IMPORT GRAPH: END -->

## Directional constraints

The dependency graph must remain acyclic. In particular, reusable feature,
trading, model, decision, and simulation packages must not acquire reverse
dependencies on workflow or backend internals. Evaluation and live runtime
consume backend-neutral decision interfaces; the legacy checkpoint adapter is
isolated as a compatibility composition root.

See [`tests/architecture/test_dependency_rules.py`](../../tests/architecture/test_dependency_rules.py)
for executable import constraints. The tests are authoritative when this
generated graph or explanatory text becomes stale.
