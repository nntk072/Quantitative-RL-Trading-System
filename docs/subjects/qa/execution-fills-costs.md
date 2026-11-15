# QA: Execution, fills, costs

**Status:** source claims checked after the owner’s citation correction. Reviewed against source commit `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` on 2026-11-15; no tests or notebooks were rerun by QA.

## Source claims checked

1. Nonfinite, nonpositive, or crossed bid/ask quotes are rejected before account mutation: confirmed in `trading/execution/broker.py::_validate_quote` and the broker call order.
2. Long entry/mark/exit use ask/bid/bid; short entry/mark/exit use bid/ask/ask: confirmed in `trading/execution/broker.py::Broker`.
3. Explicit cost is commission per lot per side; spread is represented by executable quote sides: confirmed in `trading/execution/costs.py::CostModel`.
4. Partial close caps quantity at remainder, books its net PnL once, and updates remaining margin and mark: confirmed in `trading/execution/broker.py::Broker.close_position`.
5. Bar stop fill can use an adverse opening quote after a gap: confirmed in `trading/execution/quotes.py::bar_stop_trigger_price` and `bar_stop_fill_quote`.

## Resolved citation correction

The timing paragraph now cites `simulation/environment/trade_accounting_runtime.py::_stamp_exit`, `simulation/environment/step_action_execution.py`, and `simulation/backtest/event_driven_backtest.py::_fill_quote_event` for fill times, while retaining `simulation/environment/step_accounting_runtime.py::_record_step_accounting` for equity valuation time. The named integration tests exist.

## Document and notebook checks

The hub has 152 lines and all required sections: Summary, Key terms, Explanation, Worked example, Tasks, Contract, Verify, Limits, Review procedure, Diagnostic cases, and Maintainer note. All 10 local Markdown links resolve; the hidden toctree notebook exists. The paired notebook has a title, Tier A/CPU/deterministic data/under-60-second/subject/owner metadata and forced MyST execution. Its one code cell has execution count 1, one saved output, and no saved error. The output reports entry `101.0`, exit `105.0`, realized close PnL `2.0`, and final balance `10000.0`.

The fixture does not measure real spread, latency, slippage, or broker parity. The five checked source anchors are unchanged from the pinned commit in the current checkout; this review does not certify other dirty execution code.
