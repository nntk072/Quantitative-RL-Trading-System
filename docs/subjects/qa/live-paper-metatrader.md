# QA for live, paper, and MetaTrader

**Status:** Five source claims verified at
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. All three entry points implement `--once` and default to paper mode.
   The scripts use trimmed, case-insensitive `false` to request real
   orders. The rule-based launchers reject that mode before login.
2. `integrations/mt5/robot/rl_robot.py::RLRobot` rejects real-order mode
   without the training-account-loss capability. The shipped
   `RiskManager` reports false. The RL entry point logs in before
   constructing the guarded robot. `tests/unit/live/test_rl_robot.py`
   exercises order suppression in paper mode and the capability check.
3. `live_trading_rl.py::resolve_run_config` defaults to the model
   grandparent's `config.yaml`. `resolve_feature_normalization_state`
   requires the two JSON objects beside the config, then validates their
   schema, config and state digests, filename, and feature-cache equality.
   `tests/unit/live/test_live_entrypoint.py` exercises config resolution
   and normalization manifest checks.
4. `live/runtime/contracts.py` defines the strategy tuple and enum values.
   `live/runtime/strategy.py::RLStrategyAdapter` checks the supplied
   provider's schema version during construction.
5. `integrations/mt5/risk_configuration.py::load_live_risk_configuration`
   prefers the training sizing cap and uses the per-trade limit when it is
   absent or null. An absent or null pair leaves the cap unset. The loader
   validates present cap, cadence, sizing, and cost values.

## Document and notebook checks

The revised hub has 163 lines and the title and ten required sections.
Fourteen local Markdown links across the hub and reference resolve. The
hidden notebook target resolves. The hub and reference now specify the
feature-cache equality check, including the all-missing-or-null case, and
the unset risk cap when neither training key supplies a value. Both
clarifications agree with the pinned resolver and loader.

Static notebook checks accepted Tier A, CPU, the deterministic bundled
fixture, subject, owner, matching title and first Markdown heading, the
Python 3 kernel, under-60-seconds target, and forced MyST execution. One
assert-bearing cell has count 1, one saved result for a synthetic HOLD
signal and USD 120 sizing cap, and zero saved errors. Recorded cell time
is 1.474 seconds.

## Evidence limit

The example reads synthetic risk configuration and a fixed signal. Broker
connectivity, account guardrail parity, orders, fills, and profitability
remain unmeasured. QA inspected the stored output without running the
notebook or contacting a terminal.
