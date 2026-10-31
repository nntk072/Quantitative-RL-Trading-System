# Environment step

One environment decision consumes the current observation and action,
advances the simulated market/account, and emits the next observation plus
reward and diagnostics. The detailed lifecycle and component map are in the
[environment package guide](../../../simulation/environment/README.md).

```mermaid
sequenceDiagram
    participant P as Policy
    participant E as TradingEnv
    participant M as Market and quote state
    participant I as Intent and entry lifecycle
    participant G as Guardrails and position manager
    participant A as Account/reward
    P->>E: action
    E->>M: advance to decision/fill point
    M->>G: mark open position and test protective levels
    E->>I: decode action and resolve intent
    I->>G: validate risk and execute or reject
    G->>A: fills, costs, realized PnL and equity
    A-->>E: reward, next observation, info, termination state
    E-->>P: transition
```

The current order matters: market advancement and protective processing occur
before a new action is executed. A new position is therefore not exposed to
price movement that happened before its fill. Exact bar/tick ordering and
execution assumptions are part of the run configuration.
