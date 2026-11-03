# Risk and execution contracts

Risk approval, order intent, execution price, and account mutation are separate
steps. A policy request is not a fill. The simulation broker and the MT5
integration implement broker-specific execution behind their respective
adapters; shared sizing and account rules stay in `trading/`.

## Backend-neutral risk decision

`trading/risk/contracts.py` defines immutable `RiskState` and `RiskDecision`
values and the `RiskPolicy` protocol:

| Contract | Fields | Meaning |
|---|---|---|
| `RiskState` | `equity`, `daily_pnl`, `open_risk`, `daily_loss_limit` | Current account state and committed open-position risk; monetary fields use account currency. |
| `RiskDecision` | `allowed`, `risk_amount`, optional `reason` | Whether the request is accepted and the approved risk amount. A denial or reduction should explain the policy result where possible. |
| `RiskPolicy.decide(state, requested_risk)` | input state and requested amount | Returns a decision without requiring a broker or policy-model dependency. |

This protocol does not calculate order size, select prices, or guarantee that a
broker can fill an approved trade. Domain-specific constraints are implemented
by `trading/risk/`, `trading/account/`, and the configured account policy.
The current training environment and event-driven backtest do not yet consume
this protocol: both use `AccountState`, `FTMOGuardrails`, and the existing
sizing helpers. The live path has its MT5 risk adapter. Contract unit tests
verify the v1 value shape only, not runtime integration or parity; see the
[risk package API](../api/generated/trading/risk/index) and
`trading/risk/README.md`.

## Sizing and risk limits

`trading/risk/sizing.py` converts stop distance, account equity, risk limits,
contract size, point size, and execution reserve into a lot size. Monetary risk
is measured in account currency; stop distances and prices use instrument
price units. `compute_lots_with_execution_reserve` accounts for configured
spread/slippage/fees before sizing. Invalid or too-tight protective levels are
rejected or tightened according to the selected policy; callers must not infer
that a requested percentage is the final dollar risk without checking the
resolved config and sizing result.

Training/simulation risk is configured under `ftmo`, `risk`, and
`quality_execution`; live overrides are declared under
`live_risk_overrides`. The current MT5 adapter uses percentage-of-balance
sizing and does not enforce the training environment's FTMO daily-loss or
maximum-loss dollar limits. On the default $100,000 account, the configured
1% per-symbol sizing is numerically comparable to the $1,000 training
per-trade sizing cap; this scale relationship is not runtime risk parity.
`FTMOGuardrails` runs in the current environment and backtest paths. In
non-episodic chronological evaluation, daily-loss breaches block the supplied
session ID, while maximum-loss and trailing-drawdown breaches latch for the
remainder of the rollout. Same-bar protective-exit versus account-guardrail
precedence remains different between the environment and backtest pending a
shared contract. Risk-contract unit tests verify the v1 value shapes only;
separate guardrail, environment, and backtest tests cover their respective
paths. These tests do not establish live parity or equivalence to an external
account's reset clock.

## Quote and fill semantics

`trading/execution/broker.py::Broker` accepts a `(bid, ask)` quote and validates
that both prices are finite and positive and `ask >= bid` before mutating the
account. The executable side is:

| Operation | Price side |
|---|---|
| Open long | Ask |
| Close long | Bid |
| Open short | Bid |
| Close short | Ask |
| Mark long to market | Bid |
| Mark short to market | Ask |

`trading/execution/costs.py` owns spread, slippage, and commission inputs.
Simulation results therefore depend on the configured quote/cost model and
fill contract. `integrations/mt5/` translates these broker-neutral values to
MetaTrader APIs; it does not redefine account or action semantics.

## Environment ordering

The event order is documented in the
[environment step reference](../architecture/runtime/environment_step.md):
advance the market, mark and protect existing positions, decode the action,
check eligibility and risk, execute valid entries, update accounting/reward,
then build the next observation and termination flags. This order means an
existing protective exit is evaluated before a newly requested entry. Changing
it changes the simulated contract and requires fill-parity and golden-trace
tests.

See [execution and costs](../concepts/execution_and_costs.md),
[account limits](../concepts/risk_and_account_limits.md), and
[checkpoint compatibility](checkpoint_compatibility.md) for related concepts
and versioned model inputs.
