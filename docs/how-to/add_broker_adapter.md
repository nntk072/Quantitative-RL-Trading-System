# Add a broker adapter

Broker-specific code belongs in `integrations/`; decision contracts and
strategy logic remain broker-neutral.

1. Read [`trading/README.md`](../../trading/README.md),
   [`live/README.md`](../../live/README.md), and
   [`integrations/README.md`](../../integrations/README.md).
2. Identify the broker's quote, instrument, order, fill, position, clock, and
   account representations. Document units, timezone, precision, and partial
   fill behavior.
3. Map external values into the existing domain contracts. Keep SDK objects
   out of `trading/`, `decisioning/`, `simulation/`, and `live/` public APIs.
4. Validate provider observation/action schema before translating a decision
   to an order.
5. Implement explicit handling for disconnected feeds, stale quotes, rejected
   orders, partial fills, retries, and duplicate events.
6. Add adapter contract tests with deterministic fake broker responses, then
   integration tests against the supported SDK where available.
7. Verify paper mode, configured risk controls, and shutdown behavior before
   enabling any live order path.

Backtest success does not prove broker execution equivalence. Preserve an
explicit paper/live safety boundary and report any semantics the broker cannot
match.
