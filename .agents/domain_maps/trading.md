# Trading Domain

## Ownership

`trading/` owns account state, risk policies, order intent/geometry, execution
cost and fill contracts, position lifecycle, and strategy semantics. The current
FTMO and structural SL/TP behavior are implementations of those concepts, not
the package boundary.

## Primary Files

| File | Role |
|---|---|
| `trading/account/account_state.py` | Account and session accounting state |
| `trading/risk/guardrails.py` | FTMO guardrail policy |
| `trading/risk/sizing.py` | Position sizing and stop/target math |
| `trading/orders/entries.py` | Structural stop/target construction |
| `trading/orders/stops.py` | Structural stop candidates, filtering, and rejection provenance |
| `trading/orders/targets.py` | Structural target candidates and market-level selection |
| `trading/orders/selection.py` | TP-mode, menu selection and fraction decoding |
| `trading/execution/broker.py` | Broker-neutral fill and position transitions |
| `trading/execution/costs.py` | Spread, slippage and commission semantics |
| `trading/execution/quotes.py` | Canonical bar, protective-level, and stop-gap quote calculations |
| `trading/risk/budget.py` | Risk-budget calculation and dynamic approval |
| `trading/positions/multi_tp.py` | Multi-target position lifecycle |
| `trading/policy/config.py` | Resolved policy configuration |
| `trading/strategies/strategy_contract.py` | Broker-neutral entry-strategy contract |
| `trading/strategies/` | Entry-strategy implementations |
| `trading/baselines/step_indexed_strategy.py` | One-action-per-bar baseline policy contract |

## Dependency Direction

- **May depend on:** configuration, artifact contracts where needed, market-data
  values, and stable simulation contracts.
- **Must not depend on:** `simulation/environment/` runtime modules, model
  implementations, training workflows, or broker SDKs.
- Simulation may compose trading account/order/risk contracts into a state
  transition; trading must remain usable without a particular simulator.

## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Add an order target policy | target construction | `trading/orders/targets.py` | order geometry; `tests/test_simulation/test_backtest/test_entry_levels.py` | target policy and execution regression | simulation action decoding internals |
| Change risk policy | risk decision | `trading/risk/contracts.py` | `RiskPolicy`; `tests/test_trading/test_risk_policy_contract.py` | policy and contract tests | model and broker implementation |

## Axis of Change

- **Axis:** account policy, risk policy, order intent/target selection, execution
  costs/fills, and position lifecycle.
- **Stable boundary:** public `trading` package APIs for account state, policy,
  execution quotes, risk calculations, order geometry, and position lifecycle.
- **Expected edit radius:** one policy or execution implementation plus its
  focused order/fill tests.
- **Must stay independent from:** the learner/provider family and environment
  runtime details.

## Focused Tests

- `tests/test_simulation/test_backtest/test_entry_levels.py`
- `tests/test_simulation/test_backtest/test_engine_execution_contract_unittest.py`
- `tests/test_trading/test_risk.py`
- `tests/test_trading/test_guardrails.py`
- `tests/test_simulation/test_environment/test_tp_action_contracts.py`
- `tests/test_simulation/test_environment/test_tp_mode_state.py`
- `tests/test_simulation/test_environment/test_tp_execution.py`
- `tests/test_simulation/test_environment/test_tp_action_decode.py`
- `tests/test_simulation/test_environment/test_sl_tp_fill.py`
- `tests/integration/test_position_fill_accounting.py`
## Verified Source Paths

- `trading/__init__.py`
- `trading/account/account_state.py`
- `trading/execution/quotes.py`
- `trading/orders/entries.py`
- `trading/orders/timeframes.py`
- `trading/orders/stops.py`
- `trading/orders/targets.py`
- `trading/orders/selection.py`
- `trading/risk/contracts.py`
- `trading/risk/sizing.py`
- `trading/risk/budget.py`
- `trading/execution/broker.py`
- `trading/orders/targets.py`
