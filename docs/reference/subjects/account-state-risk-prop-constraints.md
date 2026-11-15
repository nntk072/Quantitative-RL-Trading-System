# Account state and risk contract

**Status:** draft
**Source of truth:** `trading/account/account_state.py`; `trading/account/limits.py`; `trading/risk/contracts.py`; `trading/risk/budget.py`; `trading/risk/guardrails.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Versioned risk fields

| Record | Fields | Validation |
|---|---|---|
| `RiskState` | `equity`, `daily_pnl`, `open_risk`, `daily_loss_limit`, `daily_pnl_basis`, `schema_version` | Finite money fields, nonnegative open risk and limit, supported version/basis |
| `RiskDecision` | `allowed`, `risk_amount`, `reason`, `schema_version` | Finite nonnegative amount; denied means zero |
| `RiskBudgetDecision` | `requested_usd`, `approved_usd`, `policy_cap_usd`, `execution_reserve_usd` | Approval is bounded by request and capped capacity less reserve |

`RISK_STATE_SCHEMA_V1` and `RISK_DECISION_SCHEMA_V1` are the pinned record versions. Daily basis values are `session_net_equity`, `legacy_gross_closed_losses`, and `ftmo_midnight_balance` (`trading/risk/contracts.py`).

## Account anchors and floors

- `balance`: realized cash; `equity`: balance plus open PnL (`trading/account/account_state.py`).
- `session_start_equity`: reset anchor for daily equity loss (`trading/account/account_state.py`).
- `daily_floor = session_start_equity - daily_loss_limit` (`trading/account/limits.py`).
- `remaining_daily_capacity = max(0, equity - daily_floor)` (`trading/account/limits.py`).
- `remaining_account_capacity = max(0, equity - account_floor)` (`trading/account/limits.py`).
- Hard breach reasons `daily_loss`, `max_drawdown`, and `trailing_dd` have rollout scope (`trading/risk/guardrails.py`).

See the [subject guide](../../subjects/C_trading_risk_execution/account-state-risk-prop-constraints.md), [risk reference](../risk_and_execution.md), and [glossary](../../glossary.md). Live prop-firm acceptance is **not measured**.
