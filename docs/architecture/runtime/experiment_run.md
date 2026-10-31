# Experiment run

An experiment coordinates declared variants and run identities while leaving
data, model, learning, and execution semantics to their owning packages.

```mermaid
sequenceDiagram
    participant U as Researcher or CLI
    participant X as Experiment resolver
    participant C as Configuration
    participant T as Training
    participant E as Evaluation
    participant A as Artifacts
    U->>X: comparison and run request
    X->>C: resolve variant and overrides
    C-->>X: validated configuration identity
    X->>A: reserve run identity/provenance
    X->>T: execute training
    T->>A: checkpoint and training result
    X->>E: evaluate compatible checkpoint
    E->>A: ledger, metrics, plots and report
```

The generated [variant catalog](../../model_variants.md) explains what each
configured arm represents. It is not a runtime settings source. Frozen run
records preserve the settings and identity actually used.
