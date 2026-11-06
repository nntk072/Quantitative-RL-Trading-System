# Account state and limits

`trading/account/` owns broker-neutral balance, equity, realized and open PnL,
session anchors, and account loss-capacity calculations. `AccountState` tracks
the account lifecycle, while `limits.py` exposes pure calculations used by
risk guards. Account initialization and monetary updates reject non-finite
values before mutation; initial capital must be positive, and a payout reset
balance cannot be negative.

Daily loss has two independent settings: its measurement basis and its fixed
allowance. The current research default measures the equity change from each
session's opening equity, including open P&L. The allowance is a percentage of
initial account equity, so its percentage reference stays fixed when the
account balance changes. The daily floor is that session's opening equity
minus the allowance. A payout resets the session anchor immediately to
post-payout equity, so the daily floor moves with the payout while the
allowance remains 5% of initial equity. The reset follows the supplied
`session_id` transition during ordinary session changes. The IDs come from
normalized bar-index dates, so this does not establish timezone parity with an
external account's midnight rule.

A payout can withdraw only realized balance above the initial operating
balance. It cannot withdraw initial capital or turn an account loss into a
payout. Repeated-payout mode triggers at its configured profit target and
resets operating balance to the initial amount.

Historical runs may contain a gross realized-loss counter: it sums losing
closed trades without offsetting profitable closes and excludes open P&L. Keep
that historical measure distinct from daily equity loss when interpreting old
artifacts. Selecting a daily-PnL basis is independent of payout or account
lifecycle behavior.

Maximum loss is a separate percentage of initial equity, with its drawdown
rule selected by `ftmo.max_drawdown_mode`:

- `static`: the floor stays at initial equity minus the allowance.
- `eod`: the floor ratchets from the highest completed-session equity.
- `intraday_trailing`: the floor ratchets from the running equity high.

The EOD and intraday floors cannot rise above initial equity. A payout also
locks either trailing maximum-loss floor at initial equity immediately. Equity
exactly at that initial-balance floor is allowed after the reset; any later
equity below it breaches. Static drawdown remains anchored to its fixed
initial-equity floor; equality is allowed and only equity below that floor
fails the account. Daily loss likewise allows equality at its session floor;
any amount below it permanently fails the full evaluation.

Be explicit about the equity base and reset boundary for daily and trailing
limits. Training, simulation, and live adapters must use compatible dollar
limits and valuation semantics. Focused tests are in `tests/unit/trading/` and
`tests/unit/simulation/`.
