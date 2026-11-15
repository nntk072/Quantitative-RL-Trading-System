# Account state, risk, and prop constraints

**Status:** draft
**Use this when:** You need to follow an account balance or equity change into entry capacity and hard guardrail decisions.

## Summary and use this when

The account ledger holds balance, equity, session anchors, and loss measures. Risk policy converts that state into a permitted dollar amount. Hard account floors can breach a rollout; soft bands shape reward or block an entry without becoming hard breaches. Sources: `trading/account/account_state.py`, `trading/risk/contracts.py`, `trading/risk/budget.py`, `trading/risk/guardrails.py`, `simulation/environment/risk_runtime.py`.

- Use this guide to distinguish realized balance from marked equity.
- Use it to audit a rejected risk request or a loss-floor event.
- Use the [subject reference](../../reference/subjects/account-state-risk-prop-constraints.md) for field and version details.
- Use [risk and account limits](../../concepts/risk_and_account_limits.md) for the broader account flow.

## Key terms

- [Risk budget](../../glossary.md)
- [R multiple](../../glossary.md)
- [Episode](../../glossary.md)
- [Rollout](../../glossary.md)

## Explanation

### Account quantities

`AccountState` initializes balance and equity from a finite positive initial balance. `update_equity` uses balance plus open PnL and refuses nonfinite values before mutation. `close_trade` books realized PnL to balance and clears open PnL; the legacy loss counter accumulates negative closed outcomes. Source: `trading/account/account_state.py::AccountState`; test: `tests/unit/trading/test_risk_policy_contract.py`.

The session-start balance and equity are anchors. `reset_daily` sets new anchors and resets the legacy closed-loss counter. `canonical_daily_loss` follows the selected daily PnL basis; it is not always the legacy counter. Source: `trading/account/account_state.py::reset_daily`, `canonical_daily_loss`, `daily_pnl_basis`; test: `tests/unit/trading/test_risk_policy_contract.py`.

The simple session equity floor is `session_start_equity - daily_loss_limit`. Remaining daily capacity is current equity above that floor, floored at zero. Remaining account capacity is equity above the active account floor, also floored at zero. Source: `trading/account/limits.py::daily_floor`, `remaining_daily_capacity`, `remaining_account_capacity`.

`max_drawdown` on `AccountState` records peak loss relative to initial balance. Separate peak equity and peak end-of-day equity fields support different policies; a peak-equity field must not be read as the static maximum-loss floor. Source: `trading/account/account_state.py::AccountState`, `_update_loss_from_initial`, `record_eod_equity`.

### Risk decision

The pinned `RiskState` wire contract carries equity, daily PnL, open risk, daily-loss limit, selected PnL basis, and schema version. Its constructor rejects nonfinite amounts, negative open risk or limit, and unsupported version/basis. Source: `trading/risk/contracts.py::RiskState`; test: `tests/unit/trading/test_risk_policy_contract.py`.

`RiskDecision` carries allowed, risk amount, optional reason, and version. A denied decision must approve zero risk; all approved amounts are finite and nonnegative. `RiskPolicy` exposes `decide(state, requested_risk)`. Source: `trading/risk/contracts.py::RiskDecision`, `RiskPolicy`; test: `tests/unit/trading/test_risk_policy_contract.py`.

`approve_dynamic_risk` caps the request by the configured maximum fraction, remaining daily capacity, and remaining account capacity. It subtracts the nonnegative modeled execution reserve before approving risk. A zero capacity or exhausted reserve yields zero approval. Source: `trading/risk/budget.py::approve_dynamic_risk`; test: `tests/unit/trading/test_risk.py`.

### Hard and soft rules

`FTMOGuardrails` uses configured percentages of initial equity for hard daily and maximum-loss amounts. The daily amount applies to each session-start anchor. `max_drawdown_mode` distinguishes static, end-of-day, and intraday-trailing account floors. Source: `trading/risk/guardrails.py::FTMOGuardrails`; test: `tests/unit/trading/test_guardrails.py`.

A hard daily-loss, maximum-drawdown, or trailing-drawdown reason maps to rollout breach scope. The environment latches hard breaches across later sessions. Soft thresholds are separate entry/reward pressure and do not by themselves force-close a position or end the rollout. Source: `trading/risk/guardrails.py::guardrail_breach_scope`; `simulation/environment/risk_runtime.py::_check_guardrails`; tests: `tests/unit/trading/test_guardrails.py`.

Payout handling can reanchor the daily session and preserve a locked floor. It must be assessed using the selected mode and actual account snapshots; a payout is not a way to erase a prior hard breach. Source: `trading/account/account_state.py::reset_operating_balance`; `trading/risk/guardrails.py::max_loss_floor_for`; test: `tests/unit/trading/test_guardrails.py::test_payout_reanchors_daily_loss_and_locks_trailing_floor_at_initial`.

### Why the sequence matters

The account first records the after-cost equity path; the policy then checks risk and floors using that path. Using a trade's planned stop loss as if it were the only possible loss would ignore execution gaps and costs. The execution reserve and capacity checks keep the request below modeled account limits; they cannot guarantee actual broker loss is capped. Sources: `trading/account/account_state.py`, `trading/risk/budget.py`, `simulation/environment/risk_runtime.py`.

## Worked example

The paired Tier A notebook uses a fixed synthetic $100,000 account. It marks a $250 open loss, computes the session floor and remaining capacity, checks a reserved risk request, and verifies that a denied `RiskDecision` has zero approved amount. These are contract checks, not prop-firm certification.

```{toctree}
:hidden:

examples/account-state-risk-prop-constraints
```

## Tasks

- Inspect [configuration recipes](../../how-to/configuration_recipes.md) before selecting risk settings.
- Inspect the [risk and execution reference](../../reference/risk_and_execution.md) for sizing and floor units.
- Use [evaluate checkpoint](../../how-to/evaluate_checkpoint.md) for registered evaluation, not this fixture.
- Keep [validation protocol](../../research/validation_protocol.md) rules when reporting outcomes.

## Contract

| Item | Contract | Source |
|---|---|---|
| Balance | Realized account cash after booked fees/PnL | `trading/account/account_state.py::close_trade` |
| Equity | Balance plus current open PnL | `trading/account/account_state.py::update_equity` |
| Daily anchor | Reset at policy session boundary | `trading/account/account_state.py::reset_daily` |
| Daily floor | Session-start equity less daily allowance | `trading/account/limits.py::daily_floor` |
| Risk state | Versioned finite money fields and PnL basis | `trading/risk/contracts.py::RiskState` |
| Decision | Denial implies zero approved risk | `trading/risk/contracts.py::RiskDecision` |
| Dynamic cap | Minimum policy/account capacity less reserve | `trading/risk/budget.py::approve_dynamic_risk` |
| Hard breach | Loss reason has rollout scope | `trading/risk/guardrails.py::guardrail_breach_scope` |

## Verify

- `tests/unit/trading/test_risk_policy_contract.py` verifies versions, selected PnL basis, and invalid amounts.
- `tests/unit/trading/test_guardrails.py` verifies daily equality, floor modes, payout, and soft versus hard checks.
- `tests/unit/trading/test_risk.py` verifies sizing and execution-reserved risk.
- `tests/integration/backtest/test_engine_execution_contract.py` verifies day change and execution interaction.
- Actual prop-firm compliance, live slippage, and sustainable payout outcomes are **not measured** here.

## Limits and common mistakes

- Balance alone misses unrealized adverse movement.
- `daily_loss` is not the only possible daily PnL basis.
- An equality at a floor differs from falling below it; use the tested comparator.
- A soft threshold does not authorize weakening a hard floor.
- `max_drawdown` field naming does not make it a trailing high-water loss.
- Payout reanchoring does not undo a latched hard breach.
- Risk approval is an entry decision, not a fill guarantee.
- Currency amounts and fractions must remain explicit; 0.01 is 1%, not $0.01.

## Review procedure

1. Capture the resolved policy mode and initial account balance.
2. Record balance, marked equity, open PnL, and current session anchor.
3. Record the selected daily PnL basis and its computed value.
4. Derive the active daily allowance from initial balance and settings.
5. Derive the active account floor for the chosen drawdown mode.
6. Check equality and below-floor cases separately.
7. Record existing open risk before a new request.
8. Translate the requested fraction to account currency.
9. Apply the configured policy fraction cap and both remaining capacities.
10. Subtract the modeled execution reserve.
11. Check the versioned `RiskState` and `RiskDecision` fields.
12. Distinguish a soft entry block from a hard breach reason.
13. Preserve the first hard breach and its rollout scope across session resets.
14. Inspect payout and end-of-day snapshots if those modes are active.
15. Reconcile any close with fill price, commission, and account update.

For a reproducible discrepancy, include the session timestamp, risk schema versions, daily PnL basis, initial/session balances, equity, active floors, request, reserve, decision, and breach reason. Synthetic checks establish arithmetic and validation only; empirical policy survival is **not measured**.

## Diagnostic cases

The following cases locate the contract boundary to inspect. They are software checks, not evidence of market outcomes.

| Case | Expected inspection result | Source |
|---|---|---|
| Nonfinite initial balance | Reject construction | `trading/account/account_state.py` |
| Nonfinite open PnL | Reject before mutation | `trading/account/account_state.py` |
| Realized profit | Increase balance | `trading/account/account_state.py` |
| Unrealized loss | Reduce equity while balance remains | `trading/account/account_state.py` |
| New session | Reset daily anchor and legacy counter | `trading/account/account_state.py` |
| Unknown account policy mode | Reject risk-basis lookup | `trading/account/account_state.py` |
| Unsupported daily basis | Reject risk state | `trading/risk/contracts.py` |
| Negative open risk | Reject risk state | `trading/risk/contracts.py` |
| Nonfinite daily limit | Reject risk state | `trading/risk/contracts.py` |
| Denied decision with nonzero risk | Reject decision | `trading/risk/contracts.py` |
| Equity at daily floor | Check strict-below breach rule | `trading/risk/guardrails.py` |
| Equity below daily floor | Record hard breach | `trading/risk/guardrails.py` |
| Soft daily threshold | Do not classify as hard breach | `trading/risk/guardrails.py` |
| Static max-loss mode | Use configured static floor | `trading/risk/guardrails.py` |
| End-of-day floor mode | Use completed-session peak state | `trading/risk/guardrails.py` |
| Intraday trailing mode | Use current peak state | `trading/risk/guardrails.py` |
| Zero daily capacity | Approve zero new risk | `trading/risk/budget.py` |
| Large execution reserve | Reduce approved risk | `trading/risk/budget.py` |
| Payout transition | Reanchor without erasing breach | `trading/account/account_state.py` |
| Hard breach reason | Carry rollout scope | `trading/risk/guardrails.py` |

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `quantitative_trading_engineer`
