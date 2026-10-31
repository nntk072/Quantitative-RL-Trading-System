# Evaluation runtime

Evaluation freezes a saved provider, presents chronological observations,
replays the configured execution model, and derives all report outputs from
the resulting ledger. See the [evaluation module guide](../../modules/evaluation.md).

```mermaid
sequenceDiagram
    participant C as Evaluation config
    participant R as Rollout runner
    participant P as Decision provider
    participant E as Environment
    participant L as Ledger
    participant O as Metrics and plots
    C->>R: period, schema, costs and risk rules
    R->>P: observation with schema
    P-->>R: action with schema
    R->>E: decoded action
    E-->>L: fills, equity, reward and diagnostics
    L-->>O: trades and equity path
    O-->>R: report and machine-readable evidence
```

The checkpoint and environment must agree on observation/action schemas. Train,
validation, exploratory test, and untouched test roles are distinct. A period
used to make design decisions is not an untouched confirmation period.
