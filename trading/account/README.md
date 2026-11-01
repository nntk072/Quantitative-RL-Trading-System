# Account state and limits

`trading/account/` owns broker-neutral balance, equity, realized and open PnL,
session anchors, and account loss-capacity calculations. `AccountState` tracks
the account lifecycle, while `limits.py` exposes pure calculations used by
risk guards.

Be explicit about the equity base and reset boundary for daily and trailing
limits. Training, simulation, and live adapters must use compatible dollar
limits and valuation semantics. Focused tests are in `tests/unit/trading/` and
`tests/unit/simulation/`.
