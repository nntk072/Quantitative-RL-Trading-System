# Live Trading Domain

## Primary Files

| File | Role |
|------|------|
| `live/runtime/strategy.py` | `RLStrategyAdapter` — trained RL policy → MT5 bridge |
| `integrations/mt5/robot/rl_robot.py` | RL robot for MT5 |
| `integrations/mt5/robot/cross_over_robot.py` | Cross-over strategy robot |
| `integrations/mt5/robot/multi_symbol_robot.py` | Multi-symbol robot |
| `integrations/mt5/adapters/data.py` | Data adapter for MT5 |
| `integrations/mt5/adapters/strategy.py` | Strategy adapter for MT5 |
| `integrations/mt5/adapters/trader.py` | Trader adapter for MT5 |
| `integrations/mt5/domain/trader.py` | Domain trader logic |
| `integrations/mt5/domain/risk_manager.py` | Risk manager for live trading |
| `integrations/mt5/domain/signal.py` | Signal data container |
| `integrations/mt5/domain/mt5_connection.py` | MT5 connection management |
| `integrations/mt5/domain/multi_symbol_manager.py` | Multi-symbol management |
| `integrations/mt5/domain/volatility_analyzer.py` | Volatility analysis |
| `integrations/mt5/domain/strategies/*.py` | Rule-based MT5 strategies |
| `integrations/mt5/domain/data_sources/mt5_data.py` | MT5 data source |
| `integrations/mt5/logging_config.py` | Logging configuration |
| `integrations/mt5/risk_configuration.py` | Validated live-risk settings shared by the RL MT5 entry point and risk manager |

## Key Symbols

| Symbol | File | Purpose |
|--------|------|---------|
| `RLStrategyAdapter` | `rl_strategy.py` | Bridge between the trained RL model and MT5 |
| `RLRobot` | `rl_robot.py` | RL-based MT5 robot |
| `RiskManager` | `risk_manager.py` | Live risk management (`live_risk_overrides`) |
| `Signal` | `signal.py` | Trading signal container |

## Direct Dependencies

- `decisioning.DecisionProvider`; `live_trading_rl.py` wraps the loaded SB3
  model at the composition root before constructing the runtime strategy.
- The direct model argument on `RLStrategyAdapter` remains for compatibility.
- `features/pipeline/feature_matrix_builder.py` (feature rebuild for live observations)
- `trading/` signal semantics and `decisioning/observations.py` (the live bridge has no simulation-runtime dependency)

## Consumers (Callers)

- `live_trading_rl.py` (live RL trading entry point)
- `demo_trading.py` is the compatibility entrypoint for
  `integrations/mt5/cli/single_symbol_demo.py`.
- `live_trading.py` is the compatibility entrypoint for
  `integrations/mt5/cli/multi_symbol_trading.py`.

## Tests

| Test File | Covers |
|-----------|--------|
| `tests/test_live/test_rl_robot.py` | RL robot |
| `tests/test_live/test_rl_bridge.py` | RLStrategyAdapter bridge |
| `tests/test_live/test_live_entrypoint.py` | Live entry point |
| `tests/test_live/test_rule_based_strategies.py` | Rule-based strategies |
| `tests/test_live/test_mt5_cli_applications.py` | MT5 command adapters, config resolution, and `--once` lifecycle |

## Do NOT Read For Live Tasks

- `features/technical/indicators.py` (feature implementation detail)
- `simulation/backtest/` (backtest — separate domain)
- `training/` (training — separate domain)
- `evaluation/` (evaluation — separate domain)

## Critical Invariants

1. **Live risk ≈ training risk** — `live_risk_overrides` must stay aligned with `ftmo` dollar limits
2. **Silent divergence is the failure mode** — training under $1000 cap, live under $5000 is a bug
3. **Action semantics must match** — discrete (PPO), continuous (SAC), or
   flag-derived strategy-overlay `Box` coordinates from
  `decisioning/actions.py`; checkpoint schema metadata must match the live
   environment configuration
4. **PAPER_TRADING defaults to true** — no orders placed unless explicitly disabled
5. **Model loading** — must load with same encoder architecture used in training
6. **Risk sizing fails closed** — invalid or unavailable sizing yields no order; never substitute a fixed lot size.
7. **Executable close quotes** — close a long at bid and close a short at ask.
8. **Optional vendor dependency** — importing `integrations.mt5` does not load MetaTrader5; requesting a concrete adapter does.
## Change Map

| Task | Axis | Start file | Contract and focused test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Add a live data or broker adapter | external adapter | `integrations/mt5/adapters/` | live ports; `tests/test_live/test_rl_bridge.py` | adapter and conversion contract tests | provider schema and training workflow |
| Change provider handling | inference runtime | `live/runtime/strategy.py` | `DecisionProvider`; `tests/test_live/test_rl_robot.py` | runtime adapter and schema test | vendor SDK boundary |

## Axis of Change

- **Axis:** live runtime lifecycle, data feeds, and provider selection.
- **Owner:** `live/` owns broker-neutral runtime behavior; `integrations/` owns venue protocols.
- **Stable boundary:** `MarketDataSource`, `DecisionProvider`, and live signal contracts.
- **Expected edit radius:** one runtime port or one adapter with contract tests.
- **Must not depend on:** training workflows or vendor SDK types.

## Verified Source Paths

- `live/runtime/strategy.py`
- `decisioning/contracts.py`
- `decisioning/adapters/sb3.py`
- `decisioning/observations.py`
- `integrations/mt5/adapters/trader.py`
- `integrations/mt5/domain/trader.py`
- `integrations/mt5/risk_configuration.py`
