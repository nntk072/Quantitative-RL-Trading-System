# MT5/FTMO 2-Step execution fidelity (opt-in)

**Status: reference/sensitivity model; NOT an MT5 Strategy Tester clone.**
The historical research configuration and output remain unchanged.
Use `config/research/ftmo_2step_mt5_fidelity.yaml` as an explicit overlay,
run matched CPU/real-data trace parity, and compare to independent MT5 results
before making any broker-equivalence or performance assertion.

## Reference contracts

- MT5 market entry buys at Ask/sells at Bid; closes reverse the transacted side.
- Already accepted server-side protective stops/targets do **not** incur EA
  order-submission network delay again. The opt-in simulator and candidate conditional replay match them to the
  first source-ordered triggering quote (including duplicate millisecond ties).
  It remains an idealized quote-based execution: stop gap/slippage, TP order
  queue priority, fill policy, rejects and partial fills require broker traces.
- EA-submitted market orders and modifications still use their configured
  simulated request latency. Do not use server-side mode for unaccepted orders.
- FTMO Challenge **2-Step** daily limit uses the balance at midnight in
  **Europe/Prague** minus 5% of initial capital, checked against current equity.
  The static 10% maximum-loss floor is separate. 1-Step has different rules.
- An observed bar after a Prague date transition is not a genuine midnight
  account snapshot. If an open position crosses the boundary, the strict mode
  raises `FTMOMidnightSnapshotUnavailable` rather than silently taking a late
  balance/equity value. Flat-account transitions need no intervening market
  valuation, but any unaccounted cashflow must still be audited.
- Current risk checks are stepped at observed market/decision events rather
  than every server tick. An intrabar hard-floor excursion may be missed; do
  not claim broker-equivalent hard-loss survival until a continuous tick-driven
  risk monitor and broker comparison are validated.

## Independent reference

Official MT5 (order request latency affects EA trade requests, not already
placed pending-order execution):
https://www.metatrader5.com/en/terminal/help/algotrading/testing

Official MT5 data/real-tick reconstruction and M1 corrections:
https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation

Official MT5 historical tick-flag meanings:
https://www.metatrader5.com/en/terminal/help/trading/market_watch

Official FTMO 2-Step objectives, daily balance anchor and static max loss:
https://ftmo.com/en/trading-objectives/

## Research gates

1. Verify no default behavior or frozen packet changes.
2. Require tick-only execution for server-side protective quote model.
3. Test long/short, SL/TP, exact-touch vs trade-through, crossed/invalid
   quotes, same-timestamp source ordering, gaps and consecutive partial TPs.
4. Verify Prague winter/summer DST and fail-closed open positions at midnight.
5. Run paired `TradingEnv` / `run_backtest` real-tick trace reconciliation.
6. Independently verify MT5-demo symbol metadata (tick value, volume rules,
   contract size, margin, stops level, fill policy, server time, swaps).
7. Keep slippage/queue sensitivity separate from causal quote coverage.
8. Run targeted tests then the repo's prescribed full Ruff/Mypy gates.
9. Label results *simulation sensitivity*, not strategy profit or policy value.
