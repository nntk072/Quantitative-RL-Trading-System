# Legacy risk-gate semantics and breach trace

## Scope and provenance

This note traces the selected seed-50 A4A/A4B training breach events. The
campaign is `rq1_entry_fsm_pair_seed50_train2025_20261024_policy2m_v1`, source
commit `b93642a368439a7838c3107c25fd4999b32bc028`, fingerprint
`b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4`. The
run configs set `trading_policy.mode: legacy` and a $5,000 daily-loss limit.
The campaign source hashes match the historical `trading/account/state.py`,
`trading/risk/guardrails.py`, `trading/policy/config.py`,
`simulation/environment/episode_runtime.py`, and
`market_data/transforms/sessions.py` versions used for this interpretation.
In particular, `add_session_id()` normalizes the input index to calendar dates,
and the environment resets the account when that ID changes. Trade close events were read from the recovered
`reanalysis_daily_stop_semantics_20261024/*/training/trades.csv`; breach
timestamps and equities were read from the corresponding `breach_events.csv`.

## What the configured gate counted

At the campaign source SHA, `AccountState.close_trade()` added the absolute
value of every negative closed-trade P&L to `daily_loss`; profitable closes did
not reduce that counter. `canonical_daily_loss()` returned this accumulated
counter in `legacy` mode. It did not use the session-start-to-current-equity
difference, and did not include unrealized P&L in that counter. The guardrail
emitted `daily_loss` when this counter reached $5,000.

Therefore, the March `daily_loss` events establish that the configured legacy
gross-loss counter crossed $5,000. They do **not** establish that net account
equity fell $5,000 below its daily anchor or that an FTMO-style net daily-loss
rule was breached. Positive closes shown below were ignored by the legacy
counter.

At the pinned source, `reset_daily()` ran when the environment saw a new
`session_id`; `add_session_id()` assigned IDs from normalized bar-index dates.
That means the anchor followed the dataset's calendar-date boundary, but the
recovered wall-clock timestamps and fixed `Etc/GMT-3` setting do not prove this
was the FTMO 00:00 CE(S)T boundary. The `repeated_payout` equity-based mode
uses the same session anchor, so it also requires timezone/reset validation.

The [FTMO Trading Objectives](https://ftmo.com/en/trading-objectives/)
page, checked 2026-11-01, defines the 2-Step maximum daily loss using account
equity (including open P/L, swaps, and commissions) against a threshold based
on the balance at 00:00 CE(S)T; for $100,000 capital it lists a $5,000 daily
amount. The historical legacy counter is not equivalent. This comparison does not
establish that the recovered input files came from FTMO; the project's reset
anchor is a normalized source-date boundary and is not verified against
00:00 CE(S)T.

## Reconciled closes through the first breach

| Arm | Breach (UTC+03) | Losing closes counted | Gross negative closes | Positive closes excluded | Net realized close P&L | Equity at breach |
|---|---:|---:|---:|---:|---:|---:|
| A4A | 2025-03-06 20:16 | 7 | $5,017.66 | $2,013.38 | −$3,004.28 | $120,356.70 |
| A4B | 2025-03-06 20:32 | 8 | $5,399.25 | $2,009.92 | −$3,389.32 | $115,413.67 |

The counted A4A negative closes were `structure_sl`; A4B had the same sequence
plus one additional `structure_sl` close before its event. The ledgers reconcile
these close amounts to the recorded equity immediately after the final stop
close preceding each breach. They identify the mechanical route to the legacy
counter threshold, not why the policy repeatedly chose entries that reached
structural stops.

## Research interpretation

Keep the original historical gate result intact: both arms failed the
campaign's predeclared strict zero-breach gate under its configured legacy
semantics. Reclassify the March events as **legacy gross-losing-close counter
breaches**, not net daily-equity breaches. A4B also has an independent
2025-10-28 `max_drawdown` event and ends the full aggregate ledger $56.05 below
the $90,000 account floor. A4A ends above that floor but remains economically
negative. Neither result demonstrates an edge.

This distinction is a simulator/account-contract issue. The historical result
must not be retroactively rewritten or rerun under changed semantics. Before
any successor is eligible, the project must choose and test a versioned daily
loss contract against the intended account rule and its midnight timezone,
reconcile equity and loss-counter behavior on deterministic traces, and verify
training/live parity.
The current quote-quality, timestamp-order, schedule, feature, and execution
gates remain independently open. External provider/license retrieval is out
of scope per the user's direction to use current local data only; this package
contains no raw data and makes no rights claim.
