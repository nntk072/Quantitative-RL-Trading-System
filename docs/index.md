# Quantitative RL Trading System

A research framework for studying reinforcement-learning trading policies through causal market features, explicit trading rules, controlled simulation, and traceable evaluation.

```{warning}
Historical simulation is not a broker guarantee. A smoke run is a software check,
not evidence of trading value. See [Limitations](research/limitations.md).
```

::::{grid} 1 2 3 3
:gutter: 2

:::{grid-item-card} Learn the framework
:link: learn/index
:link-type: doc
Start with the guided path from market data to evaluation.
:::

:::{grid-item-card} Explore framework concepts
:link: framework/index
:link-type: doc
Understand data, features, trading, learning, and evaluation by subject.
:::

:::{grid-item-card} Find the API
:link: api/index
:link-type: doc
Browse stable contracts first, then the full generated reference.
:::

:::{grid-item-card} Read research findings
:link: research/README
:link-type: doc
See the question, evidence, status, and limitations behind each result.
:::

:::{grid-item-card} Read the research evidence report
:link: research/research_evidence_report
:link-type: doc
Review the current evidence synthesis, negative findings, and unresolved gates.
:::

:::{grid-item-card} Reproduce recorded results
:link: reproduce/index
:link-type: doc
Inspect reproducibility levels and run CPU-sized evidence notebooks.
:::

:::{grid-item-card} Develop and operate Quant
:link: develop/index
:link-type: doc
Find extension, testing, architecture, deployment, and operations guides.
:::
::::

## How the system fits together

```{mermaid}
flowchart LR
    C[Resolved configuration] --> D[Prepared market data]
    D --> F[Causal features]
    F --> S[Simulation environment]
    S -->|observations and rewards| L[Policy training]
    L -->|actions| S
    L -->|saved policy| E[Evaluation replay]
    F --> E
    E --> A[Run artifacts and report]
    A --> R[Research claims and reproduction]
```

## Choose a path

- **I am new:** [Quick learning path](learn/index) → [Market data tutorial](learn/tutorials/01_market_data.ipynb) → [Environment tutorial](learn/tutorials/04_environment.ipynb).
- **I need exact behavior:** [Framework guides](framework/index) → [API reference](api/index).
- **I want to check a finding:** [Research questions](research/README) → [Result registry](reproduce/result_registry) → [Reproduction notebooks](reproduce/index).
- **I want the research synthesis:** [Evidence report](research/research_evidence_report), with the current evidence limits and reproduction routes.
- **I want to contribute:** [Developer guide](develop/index) → [Testing](development/testing) → [Documentation](development/documentation).

## Documentation map

```{toctree}
:maxdepth: 1
:caption: Start here

learn/index
framework/index
api/index
research/README
research/research_evidence_report
reproduce/index
develop/index
```

```{toctree}
:hidden:

internal_page_index
```
