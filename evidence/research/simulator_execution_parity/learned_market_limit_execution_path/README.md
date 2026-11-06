# Simulator execution path map

## Scope and finding

This source review traces the current `TradingEnv` and `run_backtest` paths from
an action to quote selection, entry/exit, account changes, and reward/report
outputs. It is a source-level map; it does not claim that every branch has an
independent parity fixture.

Both paths implement immediate or scheduled market execution and a
versioned, action-selected resting-limit order. The shared action contract
selects market or limit and, for limits, supplies bounded ATR offset and TTL.
Limit orders require TickBook chronology, retain a price cap, and produce no
position when no executable quote arrives before expiry. This describes
simulator behavior; it does not establish broker queue priority or local
within-timestamp quote ordering.

## Environment path

1. `TradingEnv.step()` delegates to `transition()`; `_step_untraced()` in
   `simulation/environment/episode_runtime.py` prepares the decision boundary
   and advances market state.
2. `_prepare_action_intent()` decodes the action, setup eligibility, execution
   type, bounded limit offset/TTL, and account guard state. Market orders may
   be immediate or scheduled by `fill_latency_bars`; a selected limit records
   its decision and submission identity, intended price, expiry, setup event,
   selected risk, and geometry.
3. Limit price is derived causally from decision-bar close and ATR, rounded to
   the configured price grid. `resolve_tick_limit_execution()` selects the
   first quote satisfying the configured exact-touch or trade-through rule,
   wait bound, and event-keyed latency. Limit orders fail closed without a
   TickBook.
4. `step_constraints_runtime` checks account/session blocks and source-setup
   validity before a pending limit may fill. It cancels on setup expiry or
   replacement, session/account block, TTL expiry, or rejected entry. A valid
   fill is sized from the intended limit price and must remain within its price
   bound. The shared broker records the actual executable fill.
5. Tick-required market fills use
   `tick_quote_runtime._resolve_randomized_tick_quote` and
   `resolve_tick_execution`; missing or over-age quotes raise
   `TickExecutionUnavailable`, with no candle fallback.
6. `protective_level_runtime._check_sl_tp()` and the shared tick exit resolver
   process stop/target crossings before account guardrails. Scheduled close and
   terminal liquidation have separate runtime paths.
7. `step_accounting_runtime` updates equity and computes reward through
   `episode_runtime._calculate_reward()` after events and accounting.

## Event-driven backtest path

1. `simulation/backtest/event_driven_backtest.run_backtest()` aligns inputs,
   resolves settings, and advances one bar at a time.
2. Each bar resolves cached execution quotes through `_fill_quote_event()` and
   processes stops, targets, account breaches, and session close through
   `protective_events.process_protective_and_account_events()`.
3. The action decoder records the market/limit choice, risk, geometry, and
   setup identity. A resting limit stores its intended price, submission time,
   inclusive TTL expiry, and first eligible TickBook quote; it is canceled when
   its source setup expires or is replaced, on account/session blocks, or at
   expiry. Market orders retain the immediate/scheduled market-fill contract.
4. `policy_actions.apply_policy_action()` applies risk and margin gates and
   sizes limits from their intended price while recording PnL from the actual
   executable fill. Market slippage is applied adversely from configured
   `costs.slippage_points`; limit fills stay price-bounded. Unfinished orders
   are canceled at their terminal boundary.
5. Tick-required market fills use `resolve_tick_execution()` with configured
   latency and maximum quote wait; missing/late quotes fail closed. Limit fills
   use the shared `resolve_tick_limit_execution()` rule and event-keyed latency.
6. Tick protective exits use the shared `resolve_tick_exit()`; the first
   source-ordered tick crossing is selected. For positions with multiple
   structural targets, the backtest advances through active target slots in
   order, closes the configured partial size at each selected target, and
   preserves the remaining position for later stop/target events. Each partial
   close is recorded as its own trade event. `Broker.close_position()` applies
   close-side pricing, charges, and realized PnL to `AccountState`.
7. Per-bar equity and total economic value are recorded by the backtest
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
- Learned market/limit entry and source-setup expiry/replacement:
  `tests/integration/backtest/test_agent_selected_entry_execution.py`.
- Account transitions and guardrails:
  `local_session_account_transition/` and
  `tests/integration/backtest/test_account_transition_parity.py`.

The engines have broad controlled market/limit path coverage, not proof of
identical behavior for every account, reward, or report state. Their bar-only
fallback timing differs; the selected historical runs require TickBook
execution. Feed-wide tie chronology, provider-authoritative time, broker
margin schedules, live account state, and historical policy-to-candidate
linkage remain outside what this source map and its synthetic fixtures
establish. Financing is not modeled in the current intraday cost contract.

Source SHA-256 values for the reviewed composition, runtime, broker, and account
files are in `SOURCE_SHA256SUMS` relative to the repository root.
