# Execution, fills, and costs

**Status:** draft
**Use this when:** You need to reconcile an order price with its executable quote, ledger PnL, and fill provenance.

## Summary and use this when

The broker-neutral execution model receives bid/ask quotes, applies side-aware fills and explicit commission, and updates the account. Simulation decides when and where a quote is available, including next-bar and protective-level paths. A reported level alone is insufficient to reconstruct after-cost PnL. Sources: `trading/execution/broker.py`, `trading/execution/costs.py`, `trading/execution/quotes.py`, `simulation/environment/entry_execution_runtime.py`.

- Use this guide when a stop or target price differs from a realized fill.
- Use it when tracing a partial close through account equity.
- Use the [subject reference](../../reference/subjects/execution-fills-costs.md) for exact field and side contracts.
- Use [execution and costs](../../concepts/execution_and_costs.md) for the stage overview.

## Key terms

- [Quote](../../glossary.md)
- [Risk budget](../../glossary.md)
- [R multiple](../../glossary.md)
- [Paper trading](../../glossary.md)

## Explanation

### Quote and side

A `Quote` is `(bid, ask)`. The broker refuses nonfinite, nonpositive, or crossed quotes before account mutation. A long opens at ask and closes at bid; a short opens at bid and closes at ask. Mark-to-market also uses the close side. Source: `trading/execution/broker.py::_validate_quote`, `Broker.open_position`, `close_position`, `mark_to_market`; test: `tests/integration/backtest/test_broker_quote_parity.py`.

`CostModel.fill_price` selects the side. `CostModel.total_cost` contains explicit commission only because spread is already represented by bid/ask execution. Adding the spread again as a fee would double count it. Source: `trading/execution/costs.py::CostModel`; test: `tests/unit/trading/test_cost_model.py`.

`CostModel.bar_quote` treats a close as bid and adds a spread in price units. When source spread arrives as raw spread points, the quote helper converts using `point_size` before it reaches this path. Source: `trading/execution/costs.py::CostModel.bar_quote`; `trading/execution/quotes.py::raw_spread_to_price`, `quote_from_bar_price`; test: `tests/integration/backtest/test_engine_execution_contract.py::test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing`.

### Order and fill transition

`Broker.open_position` refuses an invalid direction, nonpositive or nonfinite lots, or insufficient margin. Required margin is fill price times lots times contract size times margin percentage. On a successful open it books commission and returns a `Position`. Source: `trading/execution/broker.py::Broker.required_margin`, `open_position`; test: `tests/integration/backtest/test_broker_fill_accounting.py`.

`Broker.close_position` accepts a full or positive partial quantity, caps the requested partial at remaining size, computes side-aware gross PnL, subtracts closing commission, and books the result to account balance. A partial keeps the position and updates margin and mark; a completed close sets remaining size and margin to zero. Source: `trading/execution/broker.py::Broker.close_position`; test: `tests/integration/test_position_fill_accounting.py`.

The simulator stamps each fill with its quote source and timing. It records observed tick, bar open/close, or bar-range level provenance so a report can distinguish fill assumptions. On a terminal episode boundary, an open position is liquidated using the configured tick path or final bar close. Source: `simulation/environment/trade_accounting_runtime.py::_stamp_exit`; `simulation/environment/step_accounting_runtime.py::_liquidate_position_at_episode_end`; tests: `tests/integration/backtest/test_engine_execution_contract.py`.

For protective levels, `protective_level_fill_quote`, `bar_stop_trigger_price`, and `bar_stop_fill_quote` define quote-side and gap behavior. Through-tick tests assert the crossing tick is used instead of a later bounce. An OHLC-only path cannot recover real tick order. Source: `trading/execution/quotes.py`; tests: `tests/unit/simulation/test_environment/test_sl_tp_fill.py`, `tests/integration/backtest/test_engine_execution_contract.py`.

### Cost and cashflow attribution

The open commission reduces balance before the first mark. The close commission reduces realized PnL. Spread is paid through executable sides; slippage can shift a selected quote adversely where configured. The position's fill and cashflow fields preserve one lifecycle across partial exits. Source: `trading/execution/broker.py`; `trading/execution/quotes.py`; `simulation/environment/trade_accounting_runtime.py`.

A fill at a protective level is a simulator result under that quote path. Gap-through-stop behavior may be worse than the planned stop, so planned risk and realized loss need separate labels. Source: `trading/execution/quotes.py::bar_stop_fill_quote`; test: `tests/integration/backtest/test_engine_execution_contract.py::test_backtest_gap_stop_fills_at_the_open_or_worse`.

### Why reconciliation needs timing

The decision timestamp, order submission time, fill time, and equity valuation time may differ. A delayed tick fill must use its actual observed fill timestamp. A bar fallback enters at the following bar open and carries that open timestamp. Sources: `simulation/environment/trade_accounting_runtime.py::_stamp_exit`; `simulation/environment/step_action_execution.py`; `simulation/backtest/event_driven_backtest.py::_fill_quote_event`; `simulation/environment/step_accounting_runtime.py::_record_step_accounting`; tests: `tests/integration/backtest/test_engine_execution_contract.py::test_delayed_tick_exit_records_the_actual_fill_timestamp`, `test_bar_fallback_executes_at_next_bar_open_with_open_timestamp`.

## Worked example

The paired Tier A notebook opens one long on a fixed quote with commission, marks at a later quote, and closes it. It checks bid/ask sides and final cash balance. This is a deterministic software check, not a fill-quality study.

```{toctree}
:hidden:

examples/execution-fills-costs
```

## Tasks

- Use [add broker adapter](../../how-to/add_broker_adapter.md) when translating this contract to a real provider.
- Use [prepare market data](../../how-to/prepare_market_data.md) to inspect source spread and timestamps.
- Use [evaluate checkpoint](../../how-to/evaluate_checkpoint.md) for registered performance reports.
- Cross-check [stops and targets](stops-targets-multi-tp-exits.md) for proposed protective geometry.

## Contract

| Item | Contract | Source |
|---|---|---|
| Quote | `(bid, ask)`, finite and positive, `ask >= bid` | `trading/execution/broker.py::_validate_quote` |
| Long side | Open ask, close/mark bid | `trading/execution/broker.py::Broker` |
| Short side | Open bid, close/mark ask | `trading/execution/broker.py::Broker` |
| Explicit fee | Commission per lot per side | `trading/execution/costs.py::CostModel.total_cost` |
| Margin | Fill × lots × contract size × margin percentage | `trading/execution/broker.py::Broker.required_margin` |
| Partial | Positive requested size capped at remainder | `trading/execution/broker.py::Broker.close_position` |
| Protective fill | Quote-side and gap-aware helper | `trading/execution/quotes.py::bar_stop_fill_quote` |
| Fill source | Tick versus bar/level attribution | `simulation/environment/trade_accounting_runtime.py::_stamp_exit` |

## Verify

- `tests/unit/trading/test_cost_model.py` verifies fee and quote-side primitives.
- `tests/integration/backtest/test_broker_quote_parity.py` verifies broker quote behavior.
- `tests/integration/backtest/test_broker_fill_accounting.py` verifies cashflow.
- `tests/integration/backtest/test_engine_execution_contract.py` verifies bar, tick, gap, and timestamp paths.
- `tests/integration/test_position_fill_accounting.py` verifies partial lifecycle accounting.
- Real spread distributions, slippage calibration, latency, and broker parity are **not measured** by this guide.

## Limits and common mistakes

- A bar close is not necessarily an executable two-sided quote without spread conversion.
- Spread is embedded in bid/ask sides; do not charge it again as commission.
- A planned stop is not a guaranteed worst-case fill.
- Partial fills change remaining size; avoid charging full-size commission twice.
- A decision time is not always a fill time.
- A recorded tick source and a bar-derived level have different evidence strength.
- Terminal liquidation is a simulation rule, not an exchange order guarantee.

## Review procedure

1. Record direction, lots, contract size, and margin percentage.
2. Check bid, ask, point size, and source spread units.
3. Verify quote validity before any account mutation.
4. Identify order submission and arrival times.
5. Identify whether the chosen quote is tick, bar open, bar close, or protective level.
6. Determine the fill side and any adverse slippage shift.
7. Record open-side commission and post-open balance.
8. Mark open PnL using the close-side quote.
9. On each partial close, record quantity before and after.
10. Recompute gross PnL from actual entry and exit fills.
11. Deduct closing commission once for that fill.
12. Confirm account balance and marked equity follow the ledger.
13. Confirm fill ID, position ID, and timestamps connect the lifecycle.
14. Compare planned risk separately from realized loss.
15. Preserve missing-quote and rejected-order outcomes in any report.

For a reproducible fill mismatch, include the bid/ask pair, source raw spread, point size, slippage setting, order and fill times, position ID, size, both commissions, and before/after account state. A synthetic example checks mechanics only; execution quality is **not measured**.

## Diagnostic cases

The following cases locate the contract boundary to inspect. They are software checks, not evidence of market outcomes.

| Case | Expected inspection result | Source |
|---|---|---|
| Ask below bid | Reject quote | `trading/execution/broker.py` |
| Nonfinite price | Reject quote | `trading/execution/broker.py` |
| Zero lot request | Reject open | `trading/execution/broker.py` |
| Invalid direction | Reject open | `trading/execution/broker.py` |
| Insufficient margin | Reject open | `trading/execution/broker.py` |
| Long open | Fill at ask | `trading/execution/broker.py` |
| Short open | Fill at bid | `trading/execution/broker.py` |
| Long mark | Use bid | `trading/execution/broker.py` |
| Short mark | Use ask | `trading/execution/broker.py` |
| Long close | Use bid | `trading/execution/broker.py` |
| Short close | Use ask | `trading/execution/broker.py` |
| Open commission | Deduct from balance | `trading/execution/broker.py` |
| Close commission | Deduct from close PnL | `trading/execution/broker.py` |
| Spread in bid/ask | Do not duplicate as explicit fee | `trading/execution/costs.py` |
| Partial close | Cap quantity at remainder | `trading/execution/broker.py` |
| Full close | Clear size and margin | `trading/execution/broker.py` |
| Raw spread points | Convert using point size | `trading/execution/quotes.py` |
| Missing bar spread | Use configured default | `trading/execution/costs.py` |
| Protective stop gap | Allow open or worse | `trading/execution/quotes.py` |
| Delayed tick fill | Record actual tick time | `simulation/environment/trade_accounting_runtime.py` |

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `quantitative_trading_engineer`
