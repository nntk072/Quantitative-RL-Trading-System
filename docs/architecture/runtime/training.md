# Training runtime

Training resolves configuration and input identity, builds environment
workers, then alternates policy rollout collection with learner updates. It
records optimization diagnostics, account behavior, checkpoint state, and run
provenance. See the [training module guide](../../modules/training.md) and
[local package guide](../../../training/README.md).

```mermaid
sequenceDiagram
    participant C as Configuration resolver
    participant T as Training workflow
    participant D as Data/features
    participant E as Environment workers
    participant L as Learner
    participant A as Artifact store
    C->>T: resolved run settings
    T->>D: verify prepared inputs/cache
    D-->>T: aligned feature inputs
    T->>E: construct independent environments
    loop until declared budget or stop condition
        L->>E: policy for rollout
        E-->>L: transitions and diagnostics
        L->>L: update policy
        L->>A: checkpoint and training record
    end
    T->>A: final run status and provenance
```

Worker concurrency, rollout size, update geometry, and resume behavior are
algorithm- and run-specific. A smoke or throughput probe must be labeled as
such; it is not a full training result.
