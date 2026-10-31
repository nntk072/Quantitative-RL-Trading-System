# Data and feature preparation

```mermaid
sequenceDiagram
    participant S as Source files
    participant L as Data loader
    participant T as Transforms/session/split
    participant F as Feature pipeline
    participant C as Cache
    participant R as Training or evaluation
    S->>L: timestamped bars and optional ticks
    L->>T: normalized, validated data
    T->>T: resample and align completed candles
    T->>F: chronological partition and train mask
    F->>F: causal features and train-only fitted statistics
    F->>C: matrix, schema, and content identity
    C-->>R: validated reusable feature input
```

Data transformation must preserve timestamp ordering and source identity.
Feature calculation must not expose incomplete higher-timeframe candles or
future rows. Fitted normalization uses training rows only. Session labels are
eligibility/context flags; they are not permission to silently discard data.

See [`market_data/README.md`](../../../market_data/README.md),
[`features/README.md`](../../../features/README.md), and the
[validation protocol](../../thesis/validation_protocol.md).
