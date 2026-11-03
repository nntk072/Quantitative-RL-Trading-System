# Simulator execution path map

## Scope and finding

This source review traces the current `TradingEnv` and `run_backtest` paths from
an action to quote selection, entry/exit, account changes, and reward/report
outputs. It is a source-level map; it does not claim that every branch has an
independent parity fixture.

Both paths implement immediate or scheduled **market-style execution**. Their
pending-entry records carry direction and a scheduled bar/time, then resolve an
executable quote. The reviewed action and execution paths do not carry an order
type, proposed limit price, or limit-order TTL. Therefore no current limit
entry or maker-fill parity claim is supported. A price-aware candidate model
would need a separate versioned order contract and corresponding fills,
non-fills, expiry, and cancellation evidence.

## Environment path

1. `TradingEnv.step()` delegates to `transition()`; `_step_untraced()` in
   `simulation/environment/episode_runtime.py` prepares the decision boundary
   and advances market state.
2. `_prepare_action_intent()` decodes the action and guard state. When
   `fill_latency_bars > 0`, `_execute_step_action()` records a pending entry
   with direction, risk, scheduled fill index, and decision identity. It has
   no limit-price/order-type field.
3. `step_constraints_runtime` checks prior protective events and account
   guardrails before resolving a pending fill. At the due bar,
   `entry_execution_runtime._try_enter_position()` resolves the quote and
   calls the shared `Broker.open_position()`.
4. Tick-required entries use `tick_quote_runtime._resolve_randomized_tick_quote`
   and `resolve_tick_execution`; missing or over-age quotes raise
   `TickExecutionUnavailable`, with no candle fallback.
5. `protective_level_runtime._check_sl_tp()` and the shared tick exit resolver
   process stop/target crossings before account guardrails. Scheduled close and
   terminal liquidation have separate runtime paths.
6. `step_accounting_runtime` updates equity and computes reward through
   `episode_runtime._calculate_reward()` after events and accounting.

## Event-driven backtest path

1. `simulation/backtest/event_driven_backtest.run_backtest()` aligns inputs,
   resolves settings, and advances one bar at a time.
2. Each bar resolves cached execution quotes through `_fill_quote_event()` and
   processes stops, targets, account breaches, and session close through
   `protective_events.process_protective_and_account_events()`.
3. A delayed entry stores action direction, decision index, scheduled fill
   index/time, and session. At the due bar, `policy_actions.apply_policy_action()`
   sizes the position, applies risk/margin gates, resolves the quote, and calls
   `Broker.open_position()`. An unfinished final pending order is recorded as
   cancelled at data end.
4. Tick-required market fills use `resolve_tick_execution()` with the configured
   latency and maximum quote wait; missing/late quotes fail closed.
5. Tick protective exits use the shared `resolve_tick_exit()`; the first
   source-ordered tick crossing is selected. For positions with multiple
   structural targets, the backtest advances through active target slots in
   order, closes the configured partial size at each selected target, and
   preserves the remaining position for later stop/target events. Each partial
   close is recorded as its own trade event. `Broker.close_position()` applies
   close-side pricing, charges, and realized PnL to `AccountState`.
6. Per-bar equity and total economic value are recorded by the backtest
   composition root; the environment's reward path has no direct backtest
   equivalent.

## Verification links and residual boundaries

- Quote-wait failure parity:
  `quote_wait_gap/` and the paired test in
  `tests/integration/backtest/test_account_transition_parity.py`.
- Stable same-millisecond source-row handling:
  `tied_protective_trigger_order/` and the paired test in the same module.
- Scheduled session close and event-keyed latency:
  `scheduled_session_close/` and
  `tests/integration/backtest/test_risk_lifecycle_characterization.py`.
- Three-target partial lifecycle:
  `tests/integration/backtest/test_multi_target_protective_lifecycle.py`.
- Account transitions and guardrails:
  `local_session_account_transition/` and
  `tests/integration/backtest/test_account_transition_parity.py`.

The two engines intentionally differ in bar-only fallback timing; the selected
historical runs require TickBook execution. Feed-wide tie chronology,
provider-authoritative time, broker margin schedules, live account state, and
policy replay remain outside what this source map and its synthetic fixtures
establish. Financing is not modeled in the current intraday cost contract.

Source SHA-256 values for the reviewed composition, runtime, broker, and account
files are in `SOURCE_SHA256SUMS` relative to the repository root.
