# Backtest Domain

## Primary Files

| File | Role |
|------|------|
| `simulation/backtest/event_driven_backtest.py` | Event-driven backtest engine |
| `simulation/backtest/runtime.py` | Backtest settings and mutable run-state contracts |
| `simulation/backtest/accounting.py` | Fill identity, cost allocation, and close recording |
| `simulation/backtest/policy_actions.py` | Execute policy-selected backtest actions |
| `simulation/backtest/protective_events.py` | Protective exits, account guardrails, session close, terminal liquidation |
| `trading/execution/broker.py` | Broker: position open/close, fill logic |
| `trading/account/account_state.py` | Account balance, equity, loss, and session-state tracking |
| `trading/execution/costs.py` | Cost model (spread, slippage, commission) |
| `trading/risk/guardrails.py` | FTMO guardrails (daily loss, max drawdown) |
| `trading/risk/sizing.py` | Risk calculations (SL/TP, position sizing) |
| `simulation/backtest/cross_validation/backtrader_runner.py` | Named Backtrader cross-validation command |
| `simulation/backtest/cross_validation/main.py` | Tested legacy CLI forwarding adapter |

## Key Symbols

| Symbol | File | Purpose |
|--------|------|---------|
| `run_backtest()` | `simulation/backtest/__init__.py` | Public event-driven backtest entry point |
| `Broker` | `trading/execution/broker.py` | Position management, fill execution |
| `Position` | `trading/execution/broker.py` | Position data container |
| `AccountState` | `trading/account/account_state.py` | Account equity, balance, margin |
| `CostModel` | `trading/execution/costs.py` | Spread, slippage, commission model |
| `FTMOGuardrails` | `trading/risk/guardrails.py` | FTMO rule enforcement |
| `compute_sl_tp_from_structure()` | `trading/risk/sizing.py` | Structure-aware SL/TP |
| `resolve_tp_target()` | `trading/risk/sizing.py` | TP target resolution |

## Direct Dependencies

- `market_data/loading/ticks.py` (optional TickBook for fill pricing)

## Consumers (Callers)

- `simulation/environment/env.py` (uses engine internally)
- `training/runner/backtest.py` (CLI entry point)
- `evaluation/rollout/episode_rollout.py` (evaluation loop)

## Tests

| Test File | Covers |
|-----------|--------|
| `tests/integration/backtest/test_engine_cross_validation.py` | Engine + cross-validation |
| `tests/unit/trading/test_cost_model.py` | Cost model calculations |
| `tests/unit/trading/test_guardrails.py` | FTMO guardrails |
| `tests/unit/trading/test_risk.py` | Risk calculations |

## Do NOT Read For Backtest Tasks

- `features/` (feature engineering — separate domain)
- `models/` (models — separate domain)
- `training/` (training — separate domain)
- `integrations/mt5/` (live trading — separate domain)

## Fill-Price Semantics

1. **Tick data** (priority): `TickBook.quote_at(fill_instant)` at next bar open
2. **Bar-spread fallback**: `CostModel.bar_quote(close)`
3. **Tick rejection**: If tick quote outside bar `[low, high]` range, reject for bar quote

## Critical Invariants

1. **MT5 spread is in broker points** — must convert via `point_size` (e.g., 0.01 for US100)
2. **Mark-to-market uses bar-close quote** — long @ bid, short @ ask
3. **Guardrail breach blocks new trading** — for the rest of the session (episodic=False)
## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Change replay or fill behavior | execution policy | `simulation/backtest/event_driven_backtest.py` | trading fill semantics; `tests/integration/backtest/` | replay service and parity tests | metric rendering and learner construction |

## Axis of Change

- **Axis:** event replay, fill/cost policy, and account transition.
- **Owner:** simulation owns replay; trading owns account, execution, and risk semantics.
- **Stable boundary:** trading order/execution contracts and the backtest request/result behavior.
- **Expected edit radius:** one execution or replay service with parity/regression tests.
- **Must not depend on:** learner classes, report renderers, or CLI behavior.

## Verified Source Paths

- `simulation/backtest/event_driven_backtest.py`
- `trading/execution/broker.py`
- `tests/integration/backtest/test_engine_cross_validation.py`
