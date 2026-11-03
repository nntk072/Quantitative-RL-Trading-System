# Account state and limits

`trading/account/` owns broker-neutral balance, equity, realized and open PnL,
session anchors, and account loss-capacity calculations. `AccountState` tracks
the account lifecycle, while `limits.py` exposes pure calculations used by
risk guards. Account initialization and monetary updates reject non-finite
values before mutation; initial capital must be positive, and a payout reset
balance cannot be negative.

Daily-loss semantics depend on account policy mode. The compatibility
`legacy` mode accumulates absolute losses on closed trades, does not offset
profitable closes, and excludes open P&L. `repeated_payout` instead measures
drawdown from the session-start equity anchor, including unrealized P&L. The
event-driven backtest can select that daily PnL basis independently; selecting
it does not enable payout cycles. These
are different risk contracts: do not describe a `legacy` breach as a net
daily-equity or FTMO-style daily-loss breach. Both policy modes currently reset
on the project's date-derived `session_id` in the training environment and
event-driven backtest. A controlled cross-midnight test covers that code-level
parity. The IDs come from normalized bar-index dates, so this does not establish
timezone parity with an external account's midnight rule. Research configs
must choose the intended contract explicitly and validate it against
training/live behavior.

Be explicit about the equity base and reset boundary for daily and trailing
limits. Training, simulation, and live adapters must use compatible dollar
limits and valuation semantics. Focused tests are in `tests/unit/trading/` and
`tests/unit/simulation/`.
