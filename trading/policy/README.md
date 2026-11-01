# Trading policy configuration

`trading/policy/` resolves trading-policy settings into a validated value
object and evaluates the repeated-payout policy. The configuration captures
policy choices; account, order, and risk mechanics remain in their domain
packages.

When changing a policy option, update the YAML source of truth, validation, and
training/live risk-parity checks. A policy setting is not evidence that a
research result meets account limits. Focused tests are in
`tests/unit/trading/` and `tests/unit/configuration/`.
