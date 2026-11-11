# Observations and actions

The policy receives a causal snapshot of market and account state, then
returns a schema-defined action. The observation describes what was available
at the decision point; the action describes a proposed intent. The simulator
still applies eligibility, execution, and risk checks before changing the
account.

Observations may combine a current M1 sequence, completed multi-timeframe
sequences, account state, and optional regime or setup-eligibility branches.
Masks distinguish valid data from padding and ineligible choices from
eligible ones. Their ordering and meaning are part of checkpoint identity.

Actions may use a discrete menu, a continuous scalar, or named overlay
coordinates. Coordinate meaning is configured and versioned. Changing only
the policy's output width is insufficient evidence of compatibility.

## From observation to order

```mermaid
flowchart LR
    D[Timestamped market data] --> F[Causal features]
    F --> O[Observation branches and masks]
    A[Account and open position] --> O
    O --> P[Policy distribution]
    P --> S[Decode schema-defined action]
    S --> I[Proposed trading intent]
    I --> V{Eligibility, execution, and risk checks}
    V -->|rejected| R[No order; record rejection reason]
    V -->|approved| X[Submit order and resolve fill]
    R --> N[Next observation and diagnostics]
    X --> U[Update position and account state]
    U --> N
```

The policy output is a proposal. It becomes an account change only after the
environment accepts the intent and processes its execution path.

See the exact [observation schema](../reference/observation_schemas.md) and
[action schema](../reference/action_schemas.md).
