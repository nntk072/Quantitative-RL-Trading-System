# Trading policy configuration

`trading/policy/` resolves trading-policy settings into a validated value
object and evaluates the repeated-payout policy. The configuration captures
policy choices; account, order, and risk mechanics remain in their domain
packages.

The `legacy` mode preserves the historical gross-losing-close daily counter:
negative close P&L is accumulated, positive closes do not offset it, and open
P&L is excluded. `repeated_payout` uses the session-start-to-current-equity
daily-loss calculation. A recorded legacy `daily_loss` event therefore does
not by itself show a net daily-equity breach. Both modes reset on the
environment's date-based `session_id`; parity with an external account's
midnight timezone must be checked. Select and name the intended semantics in
research reports; preserve old run results under the semantics that generated
them.

When changing a policy option, update the YAML source of truth, validation, and
training/live risk-parity checks. A policy setting is not evidence that a
research result meets account limits. Focused tests are in
`tests/unit/trading/` and `tests/unit/configuration/`.
