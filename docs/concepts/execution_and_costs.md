# Execution and costs

Execution converts a proposed trade intent into simulated orders and fills.
The result depends on the selected quote source, timing, spread, slippage,
commission, and protective-level rules. A backtest result is meaningful only
when those assumptions are recorded with the run.

## Execution stages

```mermaid
sequenceDiagram
    participant P as Policy
    participant E as Environment
    participant Q as Quote source
    participant X as Execution logic
    participant A as Account
    P->>E: action
    E->>X: validated entry/management intent
    X->>Q: request bar or tick quote at fill time
    Q-->>X: bid/ask quote or unavailable-data result
    X->>A: fill, costs, and position update
    A-->>E: equity and realized/unrealized PnL
```

Entry, market exit, stop, and target fills may follow different configured
paths. Tick fills can use actual bid/ask quotes. Bar-based paths rely on candle
prices and ambiguity rules. Do not describe them as equivalent without replay
parity evidence.

Config-driven market entries and exits apply `costs.slippage_points` adversely
to the transacted side for both bar and tick quotes. An explicit
`tick_fill_slippage_points=0.0` override supports historical zero-slippage
replay. Resting limit fills do not receive this market adjustment and remain
bounded by their submitted limit. Protective OHLC fills use their separate
level-fill adjustment, once.

Costs should be applied once at the execution/accounting boundary. Reward
calculation should consume the resulting account change rather than subtract
the same spread or slippage again. Evaluation reports should distinguish
gross/mid-price outcomes from realized outcomes after configured costs.

## Limits

Historical quote availability, timestamp conversion, latency assumptions,
spread models, and within-bar event ordering can all affect fills. These are
simulator assumptions, not guarantees about a broker. See the
[simulation guide](../modules/simulation.md) and the
[operations guide](../operations/triton.md) for reproducible runs.
