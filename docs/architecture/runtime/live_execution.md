# Live and paper execution

The live path adapts broker events to broker-neutral strategy and risk
contracts, obtains a schema-validated decision, and translates an intent to
broker operations. Broker behavior, order rejection, partial fill, and
connection state must be recorded explicitly.

```mermaid
sequenceDiagram
    participant B as Broker/data adapter
    participant S as Live strategy
    participant P as Decision provider
    participant R as Risk manager
    participant X as Broker execution adapter
    B->>S: completed bars/account snapshot
    S->>P: schema-bound observation
    P-->>S: schema-bound decision
    S->>R: proposed intent
    R-->>S: accepted or rejected intent
    S->>X: broker-specific order request
    X-->>B: submit and observe broker result
```

The current live and historical training paths are not automatically
execution-equivalent. Keep paper mode as the default and consult the
[deployment protocol](../../operations/DEPLOYMENT.md) before any live
promotion.
